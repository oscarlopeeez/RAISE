from datetime import date
import pandas as pd
from django.db import transaction
from ..models import Contrato
VALID_ACTIVOPASIVO = {'ACTIVO', 'PASIVO'}
VALID_TIPOINTERES = {'FIJO', 'VARIABLE'}
VALID_AMORTIZACION = {'FRANCESA', 'ALEMANA', 'BULLET'}

def normalize_cupon_spread(value):
    v = float(value)
    if abs(v) > 1:
        v = v / 100.0
    return v

def _row_identity(row, num_fila):
    numero = str(row.get('numerocontrato', '')).strip()
    return numero or f'fila {num_fila}'

def _required_text(row, field, num_fila):
    value = row.get(field, '')
    text = '' if pd.isna(value) else str(value).strip()
    if not text:
        raise ValueError(f'Fila {num_fila}: {field} vacío.')
    return text

def _optional_text(row, field):
    value = row.get(field, '')
    return '' if pd.isna(value) else str(value).strip()

def _required_choice(row, field, allowed, num_fila):
    value = _required_text(row, field, num_fila).upper()
    if value not in allowed:
        raise ValueError(f'Fila {num_fila}: {field} debe ser {", ".join(sorted(allowed))}.')
    return value

def _required_float(row, field, num_fila, positive=False):
    value = row.get(field)
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'Fila {num_fila}: {field} no es un número válido.')
    if positive and number <= 0:
        raise ValueError(f'Fila {num_fila}: {field} debe ser positivo.')
    return number

def _required_date(row, field, num_fila):
    value = row.get(field)
    try:
        return pd.to_datetime(value).date()
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f'Fila {num_fila}: {field} no es una fecha válida.')

def _required_int(row, field, num_fila, minimum=None, maximum=None):
    value = row.get(field)
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'Fila {num_fila}: {field} no es un entero válido.')
    if minimum is not None and number < minimum:
        raise ValueError(f'Fila {num_fila}: {field} debe ser mayor o igual que {minimum}.')
    if maximum is not None and number > maximum:
        raise ValueError(f'Fila {num_fila}: {field} debe ser menor o igual que {maximum}.')
    return number

def validate_contracts_excel(archivo):
    errors = []
    columns_required = ['numerocontrato', 'producto', 'activopasivo', 'nominal', 'fechainicio', 'fechavencimiento', 'tipointeres', 'amortizacion', 'cuponspread', 'curva', 'frecuencia']
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.lower()
    missing = [c for c in columns_required if c not in df.columns]
    if missing:
        errors.append('Columnas requeridas faltantes: ' + ', '.join(missing))
        return (False, errors)
    nums = df['numerocontrato'].astype(str)
    dup_mask = nums.duplicated(keep=False)
    if dup_mask.any():
        dup_values = sorted(set(nums[dup_mask].tolist()))
        errors.append(f"NumeroContrato duplicado en el Excel: {', '.join(dup_values[:10])}{('...' if len(dup_values) > 10 else '')}")
    today = date.today()
    for i, row in df.iterrows():
        num_fila = i + 2
        ident = row.get('numerocontrato', '?')
        if pd.isna(row.get('numerocontrato')) or str(row.get('numerocontrato')).strip() == '':
            errors.append(f'Fila {num_fila}: NumeroContrato vacío.')
            continue
        if str(row.get('activopasivo', '')).upper() not in VALID_ACTIVOPASIVO:
            errors.append(f"Fila {num_fila} ({ident}): ActivoPasivo debe ser 'ACTIVO' o 'PASIVO'.")
        try:
            nominal = float(row.get('nominal'))
            if nominal <= 0:
                errors.append(f'Fila {num_fila} ({ident}): Nominal debe ser positivo.')
        except (ValueError, TypeError):
            errors.append(f'Fila {num_fila} ({ident}): Nominal no es un número válido.')
        try:
            start_date = pd.to_datetime(row.get('fechainicio')).date()
            finish_date = pd.to_datetime(row.get('fechavencimiento')).date()
            if start_date >= finish_date:
                errors.append(f'Fila {num_fila} ({ident}): FechaInicio debe ser anterior a FechaVencimiento.')
            if finish_date <= today:
                errors.append(f'Fila {num_fila} ({ident}): FechaVencimiento ({finish_date}) ya ha pasado.')
        except (ValueError, TypeError, AttributeError):
            errors.append(f'Fila {num_fila} ({ident}): Fechas no válidas.')
        if str(row.get('tipointeres', '')).upper() not in VALID_TIPOINTERES:
            errors.append(f"Fila {num_fila} ({ident}): TipoInteres debe ser 'FIJO' o 'VARIABLE'.")
        if str(row.get('amortizacion', '')).upper() not in VALID_AMORTIZACION:
            errors.append(f"Fila {num_fila} ({ident}): Amortizacion debe ser 'FRANCESA', 'ALEMANA' o 'BULLET'.")
        try:
            spread = normalize_cupon_spread(row.get('cuponspread'))
            if spread < 0 or spread > 0.5:
                errors.append(f'Fila {num_fila} ({ident}): CuponSpread {spread:.4f} fuera de rango razonable (0 - 50%).')
        except (ValueError, TypeError):
            errors.append(f'Fila {num_fila} ({ident}): CuponSpread no es un número válido.')
        try:
            freq = int(row.get('frecuencia'))
            if freq <= 0 or freq > 12:
                errors.append(f'Fila {num_fila} ({ident}): Frecuencia debe estar entre 1 y 12.')
        except (ValueError, TypeError):
            errors.append(f'Fila {num_fila} ({ident}): Frecuencia no es un entero válido.')
    return (len(errors) == 0, errors)

@transaction.atomic
def load_contracts_from_excel(archivo, banco, curva_default='EURIBOR'):
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.lower()
    inserted = 0
    updated = 0
    for i, row in df.iterrows():
        num_fila = i + 2
        numero = _required_text(row, 'numerocontrato', num_fila)
        try:
            defaults = dict(
                producto=_required_text(row, 'producto', num_fila),
                activo_pasivo=_required_choice(row, 'activopasivo', VALID_ACTIVOPASIVO, num_fila),
                nominal=_required_float(row, 'nominal', num_fila, positive=True),
                fecha_inicio=_required_date(row, 'fechainicio', num_fila),
                fecha_vencimiento=_required_date(row, 'fechavencimiento', num_fila),
                tipo_interes=_required_choice(row, 'tipointeres', VALID_TIPOINTERES, num_fila),
                tipo_amortizacion=_required_choice(row, 'amortizacion', VALID_AMORTIZACION, num_fila),
                cupon_spread=normalize_cupon_spread(_required_float(row, 'cuponspread', num_fila)),
                curva_asociada=_optional_text(row, 'curva') or curva_default,
                frecuencia_cupon=_required_int(row, 'frecuencia', num_fila, minimum=1, maximum=12),
            )
        except ValueError as exc:
            raise ValueError(f'Fila {num_fila} ({numero}): {exc}') from exc
        if defaults['fecha_inicio'] >= defaults['fecha_vencimiento']:
            raise ValueError(f'Fila {num_fila} ({numero}): fechaInicio debe ser anterior a fechaVencimiento.')
        _, created = Contrato.objects.update_or_create(banco=banco, numero_contrato=numero, defaults=defaults)
        if created:
            inserted += 1
        else:
            updated += 1
    return {'inserted': inserted, 'updated': updated, 'total': inserted + updated}