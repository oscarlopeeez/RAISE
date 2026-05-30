import numpy as np
import pandas as pd
from .utils import normalize_curve_points
EUR_SHOCKS_BP = {'parallel': 225, 'short': 350, 'long': 200}
SHOCK_COLUMNS = ['rate_parallel_up_curve', 'rate_parallel_down_curve', 'rate_short_up_curve', 'rate_short_down_curve', 'rate_steepener_curve', 'rate_flattener_curve']

def eba_floor_bp(maturity_years):
    return np.where(maturity_years <= 20, -100 + 5 * maturity_years, 0)

class Curve:

    def __init__(self, df_flatcurve):
        self.df_flatcurve = df_flatcurve.copy()
        self.shocks = EUR_SHOCKS_BP
        self.curves = self.calculate_curves()

    def calculate_curves(self):
        S_parallel = self.shocks.get('parallel', 0)
        S_short = self.shocks.get('short', 0)
        S_long = self.shocks.get('long', 0)
        short_shock = S_short * np.exp(-self.df_flatcurve['maturity_years'] / 4)
        long_shock = S_long * (1 - np.exp(-self.df_flatcurve['maturity_years'] / 4))
        curve = self.df_flatcurve.copy()
        curve['rate_base_curve'] = curve['rate_flat_curve'] * 10000
        curve['rate_parallel_up_curve'] = curve['rate_base_curve'] + S_parallel
        curve['rate_parallel_down_curve'] = curve['rate_base_curve'] - S_parallel
        curve['rate_short_up_curve'] = curve['rate_base_curve'] + short_shock
        curve['rate_short_down_curve'] = curve['rate_base_curve'] - short_shock
        curve['rate_steepener_curve'] = curve['rate_base_curve'] - 0.65 * short_shock + 0.9 * long_shock
        curve['rate_flattener_curve'] = curve['rate_base_curve'] + 0.8 * short_shock - 0.6 * long_shock
        floor = eba_floor_bp(curve['maturity_years'].values)
        for col in SHOCK_COLUMNS:
            curve[col] = np.maximum(curve[col].values, floor)
        return curve

def build_curve_from_market(market_curve):
    tenors = sorted(market_curve.tenors, key=lambda t: t['maturity_years'])
    maturities = [float(t['maturity_years']) for t in tenors]
    rates = [float(t['rate']) for t in tenors]
    df_flatcurve = pd.DataFrame({'maturity_years': maturities, 'rate_flat_curve': rates})
    return Curve(df_flatcurve).curves