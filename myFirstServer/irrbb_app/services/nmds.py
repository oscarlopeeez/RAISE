from __future__ import annotations
from datetime import date, timedelta
NMD_CAP_YEARS = 4

def is_nmd(producto: str) -> bool:
    if not producto:
        return False
    return 'NMD' in producto.upper()

def effective_maturity(contrato, valuation_date):
    contractual = contrato.fecha_vencimiento
    if not is_nmd(contrato.producto):
        return contractual
    cap = valuation_date + timedelta(days=int(NMD_CAP_YEARS * 365.25))
    return min(contractual, cap)