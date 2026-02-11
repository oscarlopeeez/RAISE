import numpy as np
import pandas as pd

SCENARIO_COLUMNS = {
    "eve_base": "rate_base_curve",
    "eve_parallel_up": "rate_parallel_up_curve",
    "eve_parallel_down": "rate_parallel_down_curve",
    "eve_short_up": "rate_short_up_curve",
    "eve_short_down": "rate_short_down_curve",
    "eve_steepener": "rate_steepener_curve",
    "eve_flattener": "rate_flattener_curve",
}

# valor presente de los flujos de caja bajo diferentes escenarios de curva de tasas
def discount_cashflows(cashflows_df, curve_df, curve_column): 
    df = cashflows_df.copy()
    rates = np.interp(df["year"], curve_df["maturity_years"], curve_df[curve_column]) / 10000
    df["pv"] = df["cashflow"] / np.power(1 + rates, df["year"]) # PV = CF / (1+r)^t
    return df


def calculate_eve(cashflows_df, curve_df):
    results = {}

    for scenario, col in SCENARIO_COLUMNS.items():
        discoun_pv = discount_cashflows(cashflows_df, curve_df, col)
        results[scenario] = float(discoun_pv["pv"].sum()) # EVE total de cada escenario

    return results