"""Later-date ADS-B replay at alternative gate-to-runway times."""
import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta
from math import ceil
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

import zurich_experiment as z

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'data/independent_adsb_q1/processed/airport_departures_2025_q1.csv'
AIRPORTS = {'ATL': 'America/New_York', 'CLT': 'America/New_York', 'DFW': 'America/Chicago'}
TRAIN = [date(2025, 1, d) for d in range(3, 19)]
CALIB = [date(2025, 1, 19) + timedelta(days=k) for k in range(19)]
EVAL = [date(2025, 2, 7) + timedelta(days=k) for k in range(53)]


def cases(lag):
    f = pd.read_csv(SRC, usecols=['airport', 'departure_utc'])
    f['utc'] = pd.to_datetime(f.departure_utc, utc=True)
    out = []
    for ap, tz in AIRPORTS.items():
        g = f[f.airport == ap].copy()
        loc = g.utc.dt.tz_convert(ZoneInfo(tz))
        g['day'] = loc.dt.date
        g['minute'] = loc.dt.hour * 60 + loc.dt.minute + loc.dt.second / 60
        by = {d: x for d, x in g.groupby('day')}
        empty = g.iloc[:0]
        for hour in (10, 12, 14, 16, 18):
            donor = [z.profile(by.get(d, empty), hour, lag) for d in TRAIN]
            n = min(sum(c) for c in donor)
            if n < 2:
                continue
            base = [min(n, max(c[j] for c in donor)) for j in range(lag + 30)]
            scores = [max([0] + [min(n, x) - u for x, u in zip(z.profile(by.get(d, empty), hour, lag), base)]) for d in CALIB]
            q = sorted(scores)[ceil(20 * .95) - 1]
            upper = [min(n, u + q) if j >= lag else 0 for j, u in enumerate(base)]
            for d in EVAL:
                act = tuple(min(n, x) for x in z.profile(by.get(d, empty), hour, lag))
                for cap in sorted({n, ceil(n / 4), ceil(n / 8)}, reverse=True):
                    out.append(dict(airport=ap, hour=hour, day=str(d), n=n, cap=cap, lag=lag, upper=upper, actual=act))
    return out


def one(c):
    rows = []
    for delay in (1, 2):
        rows.append(dict({k: c[k] for k in ('airport', 'hour', 'day', 'n', 'cap', 'lag')}, delay=delay,
                         methods={m: z.replay(c['actual'], tuple(c['upper']), c['n'], c['cap'], c['lag'], delay, q, ind)
                                  for m, q, ind in z.METHODS}))
    return rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['smoke', 'full'])
    ap.add_argument('--lags', default='4,6,8')
    a = ap.parse_args()
    result = {}
    for lag in map(int, a.lags.split(',')):
        cs = cases(lag)
        if a.stage == 'smoke':
            cs = [c for c in cs if c['day'] in ('2025-02-07', '2025-03-31') and c['airport'] == 'CLT']
        rows = []
        with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) // 2)) as pool:
            for r in pool.map(one, cs, chunksize=8):
                rows.extend(r)
        s = z.summarize([dict(r, case_id=f"{r['airport']}{r['hour']}", training_range=r['methods']['none'], range90=r['methods']['none']) for r in rows])
        result[lag] = s
        print(lag, json.dumps(s), flush=True)
    out = ROOT / 'results/opdi_trb' / f'us_travel_{a.stage}.json'
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
