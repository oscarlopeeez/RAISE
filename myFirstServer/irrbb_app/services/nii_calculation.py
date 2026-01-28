import numpy as np
import pandas as pd

SCENARIO_COLUMNS = {
    "nii_base": "rate_base_curve",
    "nii_parallel_up": "rate_parallel_up_curve",
    "nii_parallel_down": "rate_parallel_down_curve",
}


def calculate_nii(cashflows_df: pd.DataFrame, curve_df: pd.DataFrame, horizon_years = 1.0):
    df = cashflows_df[cashflows_df["year"] <= horizon_years].copy()
    results = {}
    if len(df) == 0: # no hay flujos
        for name in SCENARIO_COLUMNS:
            results[name] = 0.0
        return results

    maturities = curve_df["maturity_years"].to_numpy()
    base_rate = np.interp(df["year"], maturities, curve_df["rate_base_curve"]) / 10000

    for scenario, col in SCENARIO_COLUMNS.items():
        scenario_rate = np.interp(df["year"], maturities, curve_df[col]) / 10000
        r = scenario_rate - base_rate

        # solo intereses variables
        repricing = df["rest_start"] * r * df["year_fraction"] * df["is_floating"]
        total_interest = df["interest"] + repricing
        results[scenario] = float(total_interest.sum())

    return results
