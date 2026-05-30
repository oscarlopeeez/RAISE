from __future__ import annotations
from datetime import date, timedelta
BUCKETS = [('≤ 1M', 0, 30), ('1M-3M', 30, 90), ('3M-6M', 90, 180), ('6M-1Y', 180, 365), ('1Y-2Y', 365, 730), ('2Y-5Y', 730, 1825), ('5Y-10Y', 1825, 3650), ('> 10Y', 3650, 10 ** 9)]

def days_to_repricing(contrato, valuation_date):
    venc = (contrato.fecha_vencimiento - valuation_date).days
    if contrato.tipo_interes == 'FIJO':
        return max(venc, 0)
    freq = max(contrato.frecuencia_cupon or 1, 1)
    meses = 12 / freq
    dias = int(round(meses * 30))
    return max(0, min(dias, venc))

def gap_analysis(banco, valuation_date=None):
    if valuation_date is None:
        valuation_date = date.today()
    contratos = list(banco.contratos.all())
    if not contratos:
        return None
    rows = []
    cum_gap = 0
    total_act = sum((c.nominal for c in contratos if c.activo_pasivo == 'ACTIVO'))
    total_pas = sum((c.nominal for c in contratos if c.activo_pasivo == 'PASIVO'))
    for label, lo, hi in BUCKETS:
        act = 0.0
        pas = 0.0
        n_act = 0
        n_pas = 0
        for c in contratos:
            d = days_to_repricing(c, valuation_date)
            if lo <= d < hi:
                if c.activo_pasivo == 'ACTIVO':
                    act += c.nominal
                    n_act += 1
                else:
                    pas += c.nominal
                    n_pas += 1
        gap = act - pas
        cum_gap += gap
        rows.append({'bucket': label, 'activos': act, 'pasivos': pas, 'gap': gap, 'gap_acumulado': cum_gap, 'n_act': n_act, 'n_pas': n_pas})
    return {'rows': rows, 'total_activos': total_act, 'total_pasivos': total_pas, 'gap_total': total_act - total_pas, 'valuation_date': valuation_date}