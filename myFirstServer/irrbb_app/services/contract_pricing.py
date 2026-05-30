from __future__ import annotations
from datetime import date
import pandas as pd
from django.db import transaction
from ..models import Banco, ResultadoBalance
from .cashflows import build_cashflows
from .curve import build_curve_from_market
from .eve_calculation import calculate_eve, discount_cashflows, SCENARIO_COLUMNS as EVE_SCENARIO_COLS
from .nii_calculation import calculate_nii

def _process_contracts(banco, curve_df, valuation_date=None):
    activos = {}
    pasivos = {}
    activos_cashflows = {}
    pasivos_cashflows = {}
    if valuation_date is None:
        valuation_date = date.today()
    contratos = banco.contratos.all()
    for contrato in contratos:
        cf = build_cashflows(contrato, curve_df, valuation_date)
        if contrato.activo_pasivo == 'ACTIVO':
            _act_dict(contrato.producto, contrato, cf, activos, activos_cashflows)
        else:
            _act_dict(contrato.producto, contrato, cf, pasivos, pasivos_cashflows)
    _calculate_eve_nii(activos, activos_cashflows, curve_df, valuation_date)
    _calculate_eve_nii(pasivos, pasivos_cashflows, curve_df, valuation_date)
    return (activos, pasivos)

def _act_dict(producto, contrato, cf, dict_obj, dict_cf):
    if producto not in dict_obj:
        dict_obj[producto] = {'count': 0, 'nominal': 0, 'contracts': []}
        dict_cf[producto] = []
    dict_obj[producto]['count'] += 1
    dict_obj[producto]['nominal'] += contrato.nominal
    carrying = None
    contract_pv = None
    mod_duration = None
    approx_duration = None
    if not cf.empty:
        try:
            carrying = abs(float(cf.iloc[0]['rest_start']))
        except Exception:
            carrying = abs(float(contrato.nominal))
        dict_cf[producto].append(cf)
    else:
        carrying = abs(float(contrato.nominal))
        dict_cf[producto] = dict_cf.get(producto, [])
    dict_obj[producto]['contracts'].append({'contract_id': contrato.id, 'carrying': carrying, 'cf': cf, 'nominal': float(contrato.nominal), 'fecha_vencimiento': contrato.fecha_vencimiento, 'frecuencia_cupon': getattr(contrato, 'frecuencia_cupon', 1)})

def _calculate_eve_nii(productos_dict, cashflows_dict, curve_df, valuation_date=None):
    if valuation_date is None:
        valuation_date = date.today()
    for producto in productos_dict:
        if cashflows_dict[producto]:
            cf_grupo = pd.concat(cashflows_dict[producto], ignore_index=True)
            eve_res = calculate_eve(cf_grupo, curve_df)
            nii_res = calculate_nii(cf_grupo, curve_df)
            scenario = {}
            for key, val in eve_res.items():
                scenario[key] = val
            for key, val in nii_res.items():
                scenario[key] = val
            productos_dict[producto]['scenario'] = scenario
            try:
                import numpy as np
                contracts = productos_dict[producto].get('contracts', [])
                total_carrying = 0.0
                weight_sum = 0.0
                weighted_duration = 0.0
                fallback_weight_sum = 0.0
                fallback_weighted_duration = 0.0
                for cmeta in contracts:
                    cf = cmeta.get('cf')
                    carrying = cmeta.get('carrying') or cmeta.get('nominal') or 0.0
                    total_carrying += float(carrying)
                    if cf is not None and (not cf.empty):
                        disc = discount_cashflows(cf, curve_df, 'rate_base_curve')
                        pv = float(disc['pv'].sum())
                        if pv > 0:
                            macaulay = float((disc['year'] * disc['pv']).sum()) / pv
                            rates = np.interp(disc['year'], curve_df['maturity_years'], curve_df['rate_base_curve']) / 10000.0
                            avg_rate = float((disc['pv'] * rates).sum()) / pv if pv else 0.0
                            mod_duration = macaulay / (1 + avg_rate) if 1 + avg_rate != 0 else macaulay
                            weight = pv / (carrying if carrying else 1)
                            weighted_duration += mod_duration * weight
                            weight_sum += weight
                            continue
                    try:
                        fv = cmeta.get('fecha_vencimiento')
                        if fv is not None:
                            years_to_mat = (fv - valuation_date).days / 365.0
                        else:
                            years_to_mat = None
                    except Exception:
                        years_to_mat = None
                    freq = cmeta.get('frecuencia_cupon') or 1
                    try:
                        next_repr = 1.0 / float(freq) if freq and float(freq) > 0 else None
                    except Exception:
                        next_repr = None
                    approx = None
                    if years_to_mat and years_to_mat > 0:
                        approx = years_to_mat
                    if next_repr is not None and (approx is None or next_repr < approx):
                        approx = next_repr
                    if approx is None:
                        approx = 0.0
                    fallback_weighted_duration += approx * float(carrying)
                    fallback_weight_sum += float(carrying)
                if weight_sum > 0:
                    duration = weighted_duration / weight_sum
                elif fallback_weight_sum > 0:
                    duration = fallback_weighted_duration / fallback_weight_sum
                else:
                    duration = 0.0
                productos_dict[producto]['carrying_amount'] = total_carrying
                productos_dict[producto]['duration'] = duration
            except Exception:
                productos_dict[producto]['carrying_amount'] = productos_dict[producto].get('nominal', 0)
                productos_dict[producto]['duration'] = 0.0
        else:
            productos_dict[producto]['scenario'] = {'eve_base': 0, 'eve_parallel_up': 0, 'eve_parallel_down': 0, 'eve_steepener': 0, 'eve_flattener': 0, 'eve_short_up': 0, 'eve_short_down': 0, 'nii_base': 0, 'nii_parallel_up': 0, 'nii_parallel_down': 0}

def _aggregate_results(activos, pasivos):
    eve_total = {'eve_base': 0, 'eve_parallel_up': 0, 'eve_parallel_down': 0, 'eve_steepener': 0, 'eve_flattener': 0, 'eve_short_up': 0, 'eve_short_down': 0}
    nii_total = {'nii_base': 0, 'nii_parallel_up': 0, 'nii_parallel_down': 0}
    for productos in [activos, pasivos]:
        for producto, datos in productos.items():
            if 'scenario' in datos:
                for key in eve_total:
                    eve_total[key] += datos['scenario'].get(key, 0)
                for key in nii_total:
                    nii_total[key] += datos['scenario'].get(key, 0)
    return (eve_total, nii_total)

def compute_contract_contributions(banco, curve_df, valuation_date):
    contributions = []
    for c in banco.contratos.all():
        cf = build_cashflows(c, curve_df, valuation_date)
        row = {'contract_id': c.id, 'numero_contrato': c.numero_contrato, 'producto': c.producto, 'activo_pasivo': c.activo_pasivo, 'nominal': float(c.nominal), 'tipo_interes': c.tipo_interes, 'tipo_amortizacion': c.tipo_amortizacion, 'fecha_vencimiento': c.fecha_vencimiento.isoformat()}
        if cf.empty:
            for key in EVE_SCENARIO_COLS:
                row[key] = 0.0
        else:
            for key, col in EVE_SCENARIO_COLS.items():
                disc = discount_cashflows(cf, curve_df, col)
                row[key] = float(disc['pv'].sum())
        try:
            nii_res = calculate_nii(cf, curve_df)
            for k, v in nii_res.items():
                row[k] = float(v)
        except Exception:
            row['nii_base'] = row.get('nii_base', 0.0)
            row['nii_parallel_up'] = row.get('nii_parallel_up', 0.0)
            row['nii_parallel_down'] = row.get('nii_parallel_down', 0.0)
        contributions.append(row)
    return contributions

def _curve_snapshot(curve_df):
    cols = ['maturity_years', 'rate_flat_curve', 'rate_base_curve', 'rate_parallel_up_curve', 'rate_parallel_down_curve', 'rate_short_up_curve', 'rate_short_down_curve', 'rate_steepener_curve', 'rate_flattener_curve']
    sub = curve_df[[c for c in cols if c in curve_df.columns]]
    return sub.to_dict(orient='records')

@transaction.atomic
def run_balance_pricing(banco: Banco, uploaded_by=None, valuation_date=None, market_curve=None):
    if valuation_date is None:
        valuation_date = date.today()
    contratos = list(banco.contratos.all())
    if not contratos:
        return None
    if market_curve is None:
        from ..models import MarketCurve
        market_curve = MarketCurve.objects.first()
    if market_curve is None:
        raise RuntimeError('No hay curva de mercado disponible. Ejecuta el comando fetch_ecb_curve para descargar la curva BCE.')
    curve_df = build_curve_from_market(market_curve)
    curve_source = {'type': 'market', 'source': market_curve.source, 'reference_date': market_curve.reference_date.isoformat(), 'fetched_at': market_curve.fetched_at.isoformat(), 'currency': market_curve.currency, 'market_curve_id': market_curve.pk}
    activos, pasivos = _process_contracts(banco, curve_df, valuation_date)
    eve_results, nii_results = _aggregate_results(activos, pasivos)
    contributions = compute_contract_contributions(banco, curve_df, valuation_date)
    metadata = {'curve_source': curve_source, 'curve_snapshot': _curve_snapshot(curve_df), 'contributions': contributions, 'contract_ids': [c.id for c in contratos], 'valuation_date': valuation_date.isoformat(), 'shocks_bp': {'parallel': 225, 'short': 350, 'long': 200}, 'currency': 'EUR'}
    resultado = ResultadoBalance.objects.create(banco=banco, uploaded_by=uploaded_by, valuation_date=valuation_date, tier1_capital=banco.tier1_capital, eve_base=eve_results.get('eve_base', 0), eve_parallel_up=eve_results.get('eve_parallel_up', 0), eve_parallel_down=eve_results.get('eve_parallel_down', 0), eve_steepener=eve_results.get('eve_steepener', 0), eve_flattener=eve_results.get('eve_flattener', 0), eve_short_up=eve_results.get('eve_short_up', 0), eve_short_down=eve_results.get('eve_short_down', 0), nii_base=nii_results.get('nii_base', 0), nii_parallel_up=nii_results.get('nii_parallel_up', 0), nii_parallel_down=nii_results.get('nii_parallel_down', 0), metadata=metadata)
    return {'activos': activos, 'pasivos': pasivos, 'resultado': resultado}