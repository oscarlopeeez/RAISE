from __future__ import annotations
import csv
import io
import os
import ssl
import urllib.request
import urllib.error
from datetime import date, datetime
try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = ssl.create_default_context()
if os.environ.get('RAISE_ECB_INSECURE') == '1':
    _SSL_CONTEXT = ssl._create_unverified_context()
TENORS = [('3M', 0.25), ('6M', 0.5), ('1Y', 1.0), ('2Y', 2.0), ('3Y', 3.0), ('5Y', 5.0), ('7Y', 7.0), ('10Y', 10.0), ('15Y', 15.0), ('20Y', 20.0), ('30Y', 30.0)]
BASE_URL_TEMPLATE = 'https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_{tenor}?format=csvdata&lastNObservations={lastN}'
TIMEOUT = 10

def _fetch_tenor(label, lastN=1):
    url = BASE_URL_TEMPLATE.format(tenor=label, lastN=lastN)
    req = urllib.request.Request(url, headers={'User-Agent': 'RAISE-IRRBB/1.0'})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CONTEXT) as r:
        return r.read().decode('utf-8')

def _parse_csv_rows(text):
    rows = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        time = row.get('TIME_PERIOD')
        val = row.get('OBS_VALUE')
        if time and val:
            try:
                rows.append((time, float(val)))
            except ValueError:
                continue
    return rows

def fetch_ecb_curve():
    points = []
    ref_date = None
    errors = []
    lookback = int(os.environ.get('RAISE_ECB_LOOKBACK_N', '1'))
    target_date_env = os.environ.get('RAISE_ECB_TARGET_DATE')
    target_date = None
    if target_date_env:
        if target_date_env.upper() == 'TODAY':
            target_date = date.today()
        else:
            try:
                target_date = datetime.strptime(target_date_env, '%Y-%m-%d').date()
            except ValueError:
                target_date = None
    for label, years in TENORS:
        try:
            text = _fetch_tenor(label, lastN=lookback)
            rows = _parse_csv_rows(text)
            chosen_time = None
            chosen_value = None
            if target_date is not None:
                for tp, val in rows:
                    try:
                        tp_date = datetime.strptime(tp, '%Y-%m-%d').date()
                    except ValueError:
                        continue
                    if tp_date == target_date:
                        chosen_time = tp
                        chosen_value = val
                        break
                if chosen_value is None:
                    errors.append(f'{label}: no observación para {target_date}')
                    continue
            elif rows:
                chosen_time, chosen_value = rows[0]
            else:
                errors.append(f'{label}: no observación')
                continue
            if chosen_value is None:
                errors.append(f'{label}: no observación válida')
                continue
            if chosen_time and (not ref_date):
                try:
                    ref_date = datetime.strptime(chosen_time, '%Y-%m-%d').date()
                except ValueError:
                    pass
            points.append({'label': label, 'maturity_years': years, 'rate': chosen_value / 100.0})
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            errors.append(f'{label}: {e}')
            continue
    if not points:
        raise RuntimeError('No se pudo obtener ningún tenor del BCE: ' + '; '.join(errors))
    if ref_date is None:
        ref_date = date.today()
    return (ref_date, points, errors)