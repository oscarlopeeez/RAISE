from __future__ import annotations
from datetime import date
import pandas as pd
from django.db import transaction

from ..models import Banco, ResultadoBalance
from .cashflows import build_cashflows
from .curve import build_default_curve
from .eve_calculation import calculate_eve
from .nii_calculation import calculate_nii

def _process_contracts(banco, curve_df):
    activos = {}
    pasivos = {}
    activos_cashflows = {}
    pasivos_cashflows = {}

    valuation_date = date.today()
    contratos = banco.contratos.all()

    for contrato in contratos:
        cf = build_cashflows(contrato, curve_df, valuation_date)
        
        if contrato.activo_pasivo == "ACTIVO":
            _act_dict(contrato.producto, contrato, cf, activos, activos_cashflows)
        else:
            _act_dict(contrato.producto, contrato, cf, pasivos, pasivos_cashflows)
    
    _calculate_eve_nii(activos, activos_cashflows, curve_df)
    _calculate_eve_nii(pasivos, pasivos_cashflows, curve_df)
    
    return activos, pasivos

def _act_dict(producto, contrato, cf, dict_obj, dict_cf):
    if producto not in dict_obj:
        dict_obj[producto] = {"count": 0, "nominal": 0}
        dict_cf[producto] = []
    dict_obj[producto]["count"] += 1
    dict_obj[producto]["nominal"] += contrato.nominal
    if not cf.empty:
        dict_cf[producto].append(cf)

def _calculate_eve_nii(productos_dict, cashflows_dict, curve_df):
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

            productos_dict[producto]["scenario"] = scenario
        else:
            productos_dict[producto]["scenario"] = {
                "eve_base": 0, "eve_parallel_up": 0, "eve_parallel_down": 0,
                "eve_steepener": 0, "eve_flattener": 0, "eve_short_up": 0, "eve_short_down": 0,
                "nii_base": 0, "nii_parallel_up": 0, "nii_parallel_down": 0
            }

def _aggregate_results(activos, pasivos):
    eve_total = {"eve_base": 0, "eve_parallel_up": 0, "eve_parallel_down": 0,
        "eve_steepener": 0, "eve_flattener": 0, "eve_short_up": 0, "eve_short_down": 0}
    
    nii_total = {"nii_base": 0, "nii_parallel_up": 0, "nii_parallel_down": 0}

    for productos in [activos, pasivos]:
        for producto, datos in productos.items():
            if "scenario" in datos:
                for key in eve_total:
                    eve_total[key] += datos["scenario"].get(key, 0)
                for key in nii_total:
                    nii_total[key] += datos["scenario"].get(key, 0)

    return eve_total, nii_total

@transaction.atomic
def run_balance_pricing(banco: Banco, uploaded_by=None):
    contratos_qs = banco.contratos.all()
    
    contratos = list(contratos_qs)
    if not contratos:
        return None

    curve_df = build_default_curve()
    
    activos, pasivos = _process_contracts(banco, curve_df)
    
    eve_results, nii_results = _aggregate_results(activos, pasivos)

    resultado = ResultadoBalance.objects.create(
        banco = banco,
        uploaded_by = uploaded_by,
        eve_base = eve_results.get("eve_base", 0),
        eve_parallel_up = eve_results.get("eve_parallel_up", 0),
        eve_parallel_down = eve_results.get("eve_parallel_down", 0),
        eve_steepener = eve_results.get("eve_steepener", 0),
        eve_flattener = eve_results.get("eve_flattener", 0),
        eve_short_up = eve_results.get("eve_short_up", 0),
        eve_short_down = eve_results.get("eve_short_down", 0),
        nii_base = nii_results.get("nii_base", 0),
        nii_parallel_up = nii_results.get("nii_parallel_up", 0),
        nii_parallel_down = nii_results.get("nii_parallel_down", 0),
    )

    return {"activos": activos, "pasivos": pasivos, "resultado": resultado}