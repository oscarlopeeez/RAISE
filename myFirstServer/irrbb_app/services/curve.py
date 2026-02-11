import numpy as np
import pandas as pd
from .utils import normalize_curve_points

EUR_SHOCKS_BP = {
    "parallel": 225,
    "short": 350,
    "long": 200,
}

class Curve:
    def __init__(self, df_flatcurve):
        self.df_flatcurve = df_flatcurve.copy()
        self.shocks = EUR_SHOCKS_BP
        self.curves = self.calculate_curves()

    def calculate_curves(self):
        S_parallel = self.shocks.get("parallel", 0)
        S_short = self.shocks.get("short", 0)
        S_long = self.shocks.get("long", 0)

        short_shock = S_short * np.exp(-self.df_flatcurve["maturity_years"] / 4)
        long_shock = S_long * (1 - np.exp(-self.df_flatcurve["maturity_years"] / 4))

        curve = self.df_flatcurve.copy()
        curve["rate_base_curve"] = curve["rate_flat_curve"] * 10000

        curve["rate_parallel_up_curve"] = curve["rate_base_curve"] + S_parallel
        curve["rate_parallel_down_curve"] = curve["rate_base_curve"] - S_parallel

        curve["rate_short_up_curve"] = curve["rate_base_curve"] + short_shock
        curve["rate_short_down_curve"] = curve["rate_base_curve"] - short_shock

        curve["rate_steepener_curve"] = (curve["rate_base_curve"] - 0.65 * short_shock + 0.9 * long_shock)
        curve["rate_flattener_curve"] = (curve["rate_base_curve"] + 0.8 * short_shock - 0.6 * long_shock)

        return curve

def build_default_curve():
    default_plazos = ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "10Y"]
    default_rates = [0.02, 0.0225, 0.025, 0.0275, 0.03, 0.032, 0.035, 0.037]
    maturities, rates = normalize_curve_points(default_plazos, default_rates)
    # maturities es del tipo [0.0833,0.25..], rates es del tipo [0.02,0.025..]

    df_flatcurve = pd.DataFrame({"maturity_years": maturities, "rate_flat_curve": rates,})
    
    return Curve(df_flatcurve).curves
