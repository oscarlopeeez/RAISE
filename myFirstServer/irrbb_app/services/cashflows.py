from datetime import date
import pandas as pd
from .utils import interpolate_rate, year_fraction_30_360

def generate_payment_dates(fecha_inicio: date, fecha_vencimiento: date, frecuencia_cupon: int):
    if frecuencia_cupon <= 0:
        frecuencia_cupon = 1

    meses_por_periodo = int(12 / frecuencia_cupon)
    fechas = []
    actual = pd.to_datetime(fecha_inicio)
    fin = pd.to_datetime(fecha_vencimiento)

    while actual < fin:
        actual = actual + pd.DateOffset(months=meses_por_periodo)
        if actual > fin:
            actual = fin
        fechas.append(actual)
    return fechas

def effective_rate(contract, curve_df):
    if contract.tipo_interes == contract.FIJO:
        return float(contract.cupon_spread)
    #si es variable
    n_years = (contract.fecha_vencimiento - contract.fecha_inicio).days / 365
    if n_years <= 0:
        n_years = 0.01

    base_rate_bp = interpolate_rate(curve_df, "rate_base_curve", n_years)
    base_rate = base_rate_bp / 10000
    return base_rate + float(contract.cupon_spread)


def build_cashflows(contract, curve_df, valuation_date = None):
    if valuation_date is None:
        valuation_date = date.today()

    payment_dates = generate_payment_dates(contract.fecha_inicio, contract.fecha_vencimiento, contract.frecuencia_cupon)

    if len(payment_dates) == 0:
        return pd.DataFrame() #no quedan flujos por generar

    n_periods = len(payment_dates)
    freq = contract.frecuencia_cupon
    if freq <= 0:
        freq = 1
    period_rate = effective_rate(contract, curve_df) / freq #tasa por periodo

    if contract.activo_pasivo == contract.ACTIVO:
        sign = 1
    else:
        sign = -1

    rows = []
    nom_rest = contract.nominal
    if contract.tipo_amortizacion == contract.FRANCESA: #cuota fija 
        cuota = nom_rest * period_rate / (1 - (1 + period_rate) ** (-n_periods))
        amort_per_period = None

    elif contract.tipo_amortizacion == contract.ALEMANA: #amortizacion fija
        cuota = None
        amort_per_period = nom_rest / n_periods
    else: #bullet (todo al final)
        cuota = None
        amort_per_period = 0

    last_date = pd.to_datetime(contract.fecha_inicio)
    
    #recorro fechas de pago y genero flujos
    for i, pay_date in enumerate(payment_dates, start=1): 
        year_frac = year_fraction_30_360(last_date.date(), pay_date.date())

        dias = (pay_date.date() - valuation_date).days
        if dias < 0:
            t = 0
        else:
            t = dias / 360

        if contract.tipo_amortizacion == contract.FRANCESA:
            interest = nom_rest * period_rate
            principal = cuota - interest
        elif contract.tipo_amortizacion == contract.ALEMANA:
            interest = nom_rest * period_rate
            principal = amort_per_period
        else: #bullet
            interest = nom_rest * period_rate
            if i == n_periods:
                principal = nom_rest
            else:
                principal = 0

        nom_rest_after = nom_rest - principal
        if nom_rest_after < 0:
            nom_rest_after = 0

        rows.append(
            {
                "contract_id": contract.id,
                "payment_date": pay_date.date(),
                "period_start": last_date.date(),
                "period_end": pay_date.date(),
                "year_fraction": year_frac,
                "year": t,
                "rest_start": nom_rest * sign,
                "interest": interest * sign,
                "principal": principal * sign,
                "cashflow": (interest + principal) * sign,
                "rate_per_period": period_rate,
                "is_floating": 1 if contract.tipo_interes == contract.VARIABLE else 0,
                "activo_pasivo": contract.activo_pasivo,
            }
        )

        nom_rest = nom_rest_after
        last_date = pay_date

    return pd.DataFrame(rows)