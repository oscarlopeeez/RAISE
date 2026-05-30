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
    for _, row in df.iterrows():
        numero = str(row.get('numerocontrato', '')).strip()
        defaults = dict(producto=row.get('producto', ''), activo_pasivo=str(row.get('activopasivo', '')).upper(), nominal=float(row.get('nominal', 0)), fecha_inicio=pd.to_datetime(row.get('fechainicio')).date(), fecha_vencimiento=pd.to_datetime(row.get('fechavencimiento')).date(), tipo_interes=str(row.get('tipointeres', '')).upper(), tipo_amortizacion=str(row.get('amortizacion', '')).upper(), cupon_spread=normalize_cupon_spread(row.get('cuponspread', 0)), curva_asociada=row.get('curva', curva_default), frecuencia_cupon=int(row.get('frecuencia', 1)))
        _, created = Contrato.objects.update_or_create(banco=banco, numero_contrato=numero, defaults=defaults)
        if created:
            inserted += 1
        else:
            updated += 1
    return {'inserted': inserted, 'updated': updated, 'total': inserted + updated}