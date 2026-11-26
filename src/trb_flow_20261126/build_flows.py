"""Directional departure flows from the ADS-B archive.

A restricted departure flow is the set of departures from one airport whose
destination lies in one compass sector (north, east, south or west, each
90 degrees wide). For each airport, start hour and sector, the calendar set
counts the flow's departures in thirty two-minute intervals on each of the
16 training dates.
"""
from __future__ import annotations
from pathlib import Path
from math import ceil, radians, degrees, sin, cos, atan2
from zoneinfo import ZoneInfo
import argparse, hashlib, json, sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT/'data/independent_adsb/raw/2025_Q1_detailed_github.parquet'
CSV = ROOT/'data/independent_adsb/processed/airport_departures_2025_jan.csv'
DATA = ROOT/'data/trb_flow_20261126'
AIRPORTS = {'ATL': 'America/New_York', 'CLT': 'America/New_York', 'DFW': 'America/Chicago'}
HORIZON, LAG = 36, 6
START_HOURS = (10, 12, 14, 16, 18)
DONOR_DAYS = tuple(range(3, 19))
SECTORS = ('north', 'east', 'south', 'west')
COLS = ['Callsign', 'ICAO_Hex', 'Track_Origin_DateTime_UTC', 'Track_Origin_ApplicableAirports',
        'Track_Origin_Lat', 'Track_Origin_Lon', 'Track_Destination_Lat', 'Track_Destination_Lon',
        'Track_Destination_ApplicableAirports']


def bearing(lat1, lon1, lat2, lon2):
    p1, p2, dl = radians(lat1), radians(lat2), radians(lon2-lon1)
    x = sin(dl)*cos(p2)
    y = cos(p1)*sin(p2)-sin(p1)*cos(p2)*cos(dl)
    return (degrees(atan2(x, y))+360) % 360


def km(lat1, lon1, lat2, lon2):
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2-p1)/2)**2+cos(p1)*cos(p2)*sin(radians(lon2-lon1)/2)**2
    return 2*6371*np.arcsin(np.sqrt(a))


def sector(b):
    return SECTORS[int(((b+45) % 360)//90)]


def extract():
    f = pq.ParquetFile(RAW)
    parts = []
    for g in range(f.num_row_groups):
        t = f.read_row_group(g, columns=COLS).to_pandas()
        for code in AIRPORTS:
            m = t[t.Track_Origin_ApplicableAirports.str.contains(f"'K{code}'", na=False, regex=False)].copy()
            m['airport'] = code
            parts.append(m)
    d = pd.concat(parts, ignore_index=True)
    d['departure_utc'] = pd.to_datetime(d.Track_Origin_DateTime_UTC, utc=True, errors='coerce')
    for c in ('Track_Origin_Lat', 'Track_Origin_Lon', 'Track_Destination_Lat', 'Track_Destination_Lon'):
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d.dropna(subset=['departure_utc', 'Track_Origin_Lat', 'Track_Destination_Lat'])
    d = d[(d.departure_utc >= '2025-01-01') & (d.departure_utc < '2025-02-01')]
    d['distance_km'] = [km(a, b, c, e) for a, b, c, e in zip(d.Track_Origin_Lat, d.Track_Origin_Lon,
                                                             d.Track_Destination_Lat, d.Track_Destination_Lon)]
    d['bearing'] = [bearing(a, b, c, e) for a, b, c, e in zip(d.Track_Origin_Lat, d.Track_Origin_Lon,
                                                              d.Track_Destination_Lat, d.Track_Destination_Lon)]
    d['sector'] = d.bearing.map(sector)
    d = d[d.distance_km >= 50]
    d = d.drop_duplicates(subset=['airport', 'ICAO_Hex', 'departure_utc'])
    out = d[['airport', 'departure_utc', 'Callsign', 'distance_km', 'bearing', 'sector']]
    out.to_csv(DATA/'flow_departures_2025_jan.csv', index=False)
    return out


def profile(times, start_minute):
    raw = np.zeros(HORIZON-LAG, dtype=int)
    for v in times-start_minute:
        s = int(np.floor(v/2.0))
        if 0 <= s < HORIZON-LAG:
            raw[s] += 1
    return [0]*LAG+raw.tolist()


def build(stage):
    path = DATA/'flow_departures_2025_jan.csv'
    d = extract() if not path.exists() else pd.read_csv(path, parse_dates=['departure_utc'])
    jobs, groups = [], []
    for code, tz in AIRPORTS.items():
        a = d[d.airport == code].copy()
        loc = a.departure_utc.dt.tz_convert(ZoneInfo(tz))
        a['date'] = loc.dt.date
        a['minute'] = loc.dt.hour*60+loc.dt.minute+loc.dt.second/60
        for hour in START_HOURS:
            for sec in SECTORS:
                b = a[a.sector == sec]
                service = [profile(b[b.date == pd.Timestamp(f'2025-01-{k:02d}').date()].minute.to_numpy(), hour*60)
                           for k in DONOR_DAYS]
                n = min(sum(s) for s in service)
                share = len(b[(b.minute >= hour*60) & (b.minute < hour*60+60)])/max(1, len(a[(a.minute >= hour*60) & (a.minute < hour*60+60)]))
                groups.append(dict(airport=code, hour=hour, sector=sec, n=int(n), share=share))
                if n < 2:
                    continue
                service = [[min(n, x) for x in s] for s in service]
                key = f'{code}_{hour:02d}_{sec}'
                cid = hashlib.sha256(key.encode()).hexdigest()[:12]
                case = dict(case_id=cid, key=key, airport=code, hour=hour, sector=sec, n=int(n),
                            lag=LAG, delta=2, service=service,
                            donor_days=[f'2025-01-{k:02d}' for k in DONOR_DAYS])
                p = DATA/'cases'/code/f'{cid}.json'
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(case), encoding='utf-8')
                caps = sorted({ceil(n/k) for k in (1, 4, 8)}, reverse=True)
                for cap in caps:
                    for delay in (1, 2):
                        jobs.append(dict(case_id=cid, airport=code, hour=hour, sector=sec, n=int(n), cap=cap,
                                         delay=delay, input_path=p.relative_to(ROOT).as_posix()))
    smoke = [j for j in jobs if j['delay'] == 1][:3]
    (DATA/'design.json').write_text(json.dumps(dict(groups=groups, jobs=jobs, smoke=smoke), indent=1), encoding='utf-8')
    print(json.dumps(dict(groups=len([g for g in groups if g['n'] >= 2]), jobs=len(jobs),
                          sizes=sorted(j['n'] for j in jobs if j['delay'] == 1 and j['cap'] == j['n']))))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['build'])
    build(ap.parse_args().stage)
