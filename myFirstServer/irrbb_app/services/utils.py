import re
from datetime import date

import numpy as np


def tenor_to_years(tenor): #6M a 0,5años
    tenor = tenor.upper().strip()  #limpio espacios y pongo mayusculas

    unidad = tenor[-1] 
    numero = float(tenor[:-1]) 

    if unidad == "M":     
        return numero / 12 
    elif unidad == "Y":    
        return numero
    else:
        raise ValueError("Tenor no válido. Usa M o Y")


def normalize_curve_points(plazos, tipos): 
    años = []

    for p in plazos:
        años.append(tenor_to_years(p))

    return años, tipos


def year_fraction_30_360(fecha_inicio, fecha_fin):
    d1 = min(fecha_inicio.day, 30)
    d2 = min(fecha_fin.day, 30)

    m1 = fecha_inicio.month
    m2 = fecha_fin.month

    y1 = fecha_inicio.year
    y2 = fecha_fin.year

    dias = 360*(y2-y1) + 30*(m2-m1) + (d2-d1)

    return dias / 360


def interpolate_rate(curve_df, column, year_value):
    maturities = curve_df["maturity_years"].to_numpy()
    rates = curve_df[column].to_numpy()
    return float(np.interp(year_value, maturities, rates))
