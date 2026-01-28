from __future__ import annotations
from datetime import date
import pandas as pd
from django.db import transaction

from ..models import Banco, ResultadoBalance
from .cashflows import build_cashflows
from .curve import build_default_curve
from .eve_calculation import calculate_eve
from .nii_calculation import calculate_nii

@transaction.atomic
def run_balance_pricing(banco: Banco, uploaded_by=None):
    contratos_qs = banco.contratos.all()
    
    contratos = list(contratos_qs)
    if not contratos:
        return None

    curve_df = build_default_curve()
    valuation_date = date.today()

    cashflow_frames = []
    for contrato in contratos:
        cf = build_cashflows(contrato, curve_df, valuation_date)
        if not cf.empty:
            cashflow_frames.append(cf)

    if not cashflow_frames:
        return None

    cashflows_df = pd.concat(cashflow_frames, ignore_index=True)

    eve_results = calculate_eve(cashflows_df, curve_df)
    nii_results = calculate_nii(cashflows_df, curve_df)

    resultado = ResultadoBalance.objects.create(
        banco = banco,
        uploaded_by = uploaded_by,
        eve_base = abs(eve_results.get("base", 0)),
        eve_parallel_up = abs(eve_results.get("parallel_up", 0)),
        eve_parallel_down = abs(eve_results.get("parallel_down", 0)),
        eve_steepener = abs(eve_results.get("steepener", 0)),
        eve_flattener = abs(eve_results.get("flattener", 0)),
        eve_short_up = abs(eve_results.get("short_up", 0)),
        eve_short_down = abs(eve_results.get("short_down", 0)),
        nii_base = abs(nii_results.get("base", 0)),
        nii_parallel_up = abs(nii_results.get("parallel_up", 0)),
        nii_parallel_down = abs(nii_results.get("parallel_down", 0)),
        metadata={
            "contratos": len(contratos),
            "curve_columns": list(curve_df.columns),
        },
    )

    return {"cashflows": cashflows_df, "eve": eve_results, "nii": nii_results, "resultado": resultado}