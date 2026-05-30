from __future__ import annotations
from datetime import date

def portfolio_stats(banco):
    contratos = list(banco.contratos.all())
    if not contratos:
        return None
    today = date.today()
    activos = [c for c in contratos if c.activo_pasivo == 'ACTIVO']
    pasivos = [c for c in contratos if c.activo_pasivo == 'PASIVO']
    nominal_act = sum((c.nominal for c in activos))
    nominal_pas = sum((c.nominal for c in pasivos))
    nominal_total = nominal_act + nominal_pas
    nominal_fijo = sum((c.nominal for c in contratos if c.tipo_interes == 'FIJO'))
    nominal_var = sum((c.nominal for c in contratos if c.tipo_interes == 'VARIABLE'))

    def weighted_term(group, nominal):
        if not nominal:
            return 0.0
        return sum(((c.fecha_vencimiento - today).days / 365.25 * c.nominal for c in group)) / nominal
    productos = {}
    for c in contratos:
        p = productos.setdefault(c.producto, {'n_activos': 0, 'n_pasivos': 0, 'nom_activos': 0.0, 'nom_pasivos': 0.0})
        if c.activo_pasivo == 'ACTIVO':
            p['n_activos'] += 1
            p['nom_activos'] += c.nominal
        else:
            p['n_pasivos'] += 1
            p['nom_pasivos'] += c.nominal
    productos_list = sorted(({'producto': k, 'n_activos': v['n_activos'], 'n_pasivos': v['n_pasivos'], 'nom_activos': v['nom_activos'], 'nom_pasivos': v['nom_pasivos'], 'gap': v['nom_activos'] - v['nom_pasivos']} for k, v in productos.items()), key=lambda x: -(x['nom_activos'] + x['nom_pasivos']))
    amortizacion = {}
    for c in contratos:
        amortizacion[c.tipo_amortizacion] = amortizacion.get(c.tipo_amortizacion, 0.0) + c.nominal
    amortizacion_list = sorted(({'tipo': k, 'nominal': v, 'pct': v / nominal_total * 100 if nominal_total else 0} for k, v in amortizacion.items()), key=lambda x: -x['nominal'])
    frecuencia = {}
    for c in contratos:
        frecuencia[c.frecuencia_cupon] = frecuencia.get(c.frecuencia_cupon, 0) + 1
    frecuencia_list = sorted(({'freq': k, 'count': v} for k, v in frecuencia.items()), key=lambda x: x['freq'])
    return {'n_contratos': len(contratos), 'n_activos': len(activos), 'n_pasivos': len(pasivos), 'nominal_activos': nominal_act, 'nominal_pasivos': nominal_pas, 'gap': nominal_act - nominal_pas, 'nominal_fijo': nominal_fijo, 'nominal_variable': nominal_var, 'pct_fijo': nominal_fijo / nominal_total * 100 if nominal_total else 0, 'pct_variable': nominal_var / nominal_total * 100 if nominal_total else 0, 'plazo_medio_activos': weighted_term(activos, nominal_act), 'plazo_medio_pasivos': weighted_term(pasivos, nominal_pas), 'productos': productos_list, 'amortizacion': amortizacion_list, 'frecuencia': frecuencia_list}