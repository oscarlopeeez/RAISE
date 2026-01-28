import pandas as pd
from ..models import Contrato


def load_contracts_from_excel(archivo, banco, curva):
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.lower()

    for i, row in df.iterrows():
        c = Contrato()
        c.banco = banco
        c.numero_contrato = row.get('numerocontrato', '')
        c.producto = row.get('producto', '')
        c.activo_pasivo = str(row.get('activopasivo', '')).upper()
        c.nominal = row.get('nominal', 0)
        c.fecha_inicio = pd.to_datetime(row.get('fechainicio')).date()
        c.fecha_vencimiento = pd.to_datetime(row.get('fechavencimiento')).date()
        c.tipo_interes = str(row.get('tipointeres', '')).upper()
        c.tipo_amortizacion = str(row.get('amortizacion', '')).upper()
        c.cupon_spread = row.get('cuponspread', 0)
        c.curva_asociada = row.get('curva', curva)
        c.frecuencia_cupon = row.get('frecuencia', 1)
        c.save()

    return len(df)

def validate_contracts_excel(archivo):
    errors = []
    columns_required = ['numerocontrato', 'producto', 'activopasivo', 'nominal', 'fechainicio',
                        'fechavencimiento', 'tipointeres', 'amortizacion', 'cuponspread', 'curva', 'frecuencia']
    
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.lower()

    #Verificar columnas requeridas
    columns_error = []
    for col in columns_required:
        if col not in df.columns:
            columns_error.append(f"{col} ")
    if len(columns_error) > 0:
        errors.append("Columnas requeridas faltantes: " + ', '.join(columns_error))
        return False, errors
    
    # Validar cada fila
    for i, row in df.iterrows():
        num_fila = i + 2

        # Validar NumeroContrato
        try:
            if pd.isna(row.get('numerocontrato')):
                errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: NumeroContrato está vacío.")
        except (ValueError, TypeError):
            errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: NumeroContrato está vacío.")
        
        # Validar Producto
        try:
            if str(row.get('activopasivo')).upper() not in ['ACTIVO', 'PASIVO']:
                errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: ActivoPasivo debe ser 'ACTIVO' o 'PASIVO'.")
        except (ValueError, TypeError):
            errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: ActivoPasivo debe ser 'ACTIVO' o 'PASIVO'.")

        # Validar nominal
        try:
            nominal = float(row.get('nominal'))
            if nominal < 0:
                errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: Nominal debe ser un número positivo.")
        except (ValueError, TypeError):
            errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: Nominal debe ser un número válido.")

        # Validar fechas
        try:
            start_date = pd.to_datetime(row.get('fechainicio'))
            finish_date = pd.to_datetime(row.get('fechavencimiento'))
            if start_date >= finish_date:
                errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: FechaInicio debe ser anterior a FechaVencimiento.")
        except (ValueError, TypeError):
            errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: Fechas no válidas.")
        
        # Validar TipoInteres
        try:
            if str(row.get('tipointeres')).upper() not in ['FIJO', 'VARIABLE']:
                errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: TipoInteres debe ser 'FIJO' o 'VARIABLE'.")
        except (ValueError, TypeError):
            errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: TipoInteres debe ser 'FIJO' o 'VARIABLE'.")
        
        # Validar Amortizacion
        try:
            if str(row.get('amortizacion')).upper() not in ['FRANCESA', 'ALEMANA', 'BULLET']:
                errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: Amortizacion debe ser 'FRANCESA', 'ALEMANA' o 'BULLET'.")
        except (ValueError, TypeError):
            errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: Amortizacion debe ser 'FRANCESA', 'ALEMANA' o 'BULLET'.")
        
        # Validar CuponSpread
        try:
            if float(row.get('cuponspread')) < 0:
                errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: CuponSpread debe ser un número positivo.")
        except (ValueError, TypeError):
            errors.append(f"Fila {num_fila}, {row.get('numerocontrato')}: CuponSpread debe ser un número válido.")
    
    return len(errors) == 0, errors