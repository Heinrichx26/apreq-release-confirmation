"""Zurich OPDI chronological replay and finite-calendar request comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta
from math import ceil
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for sub in ('trb_error_20261030', 'trb_external_error_20261030', 'trb_information_transfer_20261030'):
    sys.path.insert(0, str(ROOT / 'src' / sub))
from range_release import requirement  # noqa: E402
from robust_reports import physical, prepare, SearchLimit  # noqa: E402
from budgeted_reports import BudgetedReports  # noqa: E402
from independent_panel import TimedLookahead  # noqa: E402
from independent_replay import stress  # noqa: E402

DATA = ROOT / 'data' / 'opdi_trb'
OUT = ROOT / 'results' / 'opdi_trb'
SOURCE = DATA / 'processed' / 'zurich_full.parquet'
TRAIN, CALIB, EVAL = [], [], []


def save(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, indent=2, default=str) + '\n', encoding='utf-8')


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def profile(frame, hour, lag):
    x = np.floor((frame['minute'].to_numpy() - hour * 60) / 2).astype(int)
    return [0] * lag + np.bincount(x[(x >= 0) & (x < 30)], minlength=30).tolist()


def design():
    global TRAIN, CALIB, EVAL
    f = pd.read_parquet(SOURCE)
    f = f[f.airport == 'LSZH'].copy()
    local = f['runway_entry_utc'].dt.tz_convert('Europe/Zurich')
    f['day'] = local.dt.date
    available = sorted(d for d in f['day'].unique() if date(2024, 10, 7) <= d <= date(2024, 12, 5))
    TRAIN, CALIB, EVAL = available[:16], available[16:35], available[35:]
    f['minute'] = local.dt.hour * 60 + local.dt.minute + local.dt.second / 60
    off = f['offblock_utc'].dt.tz_convert('Europe/Zurich').dt.date
    train_taxi = f.loc[off.isin(TRAIN), 'taxi_out_min']
    lag = int(ceil(train_taxi.quantile(.1) / 2))
    byday = {d: g for d, g in f.groupby('day')}
    empty = f.iloc[:0]
    counts = {h: np.mean([sum(profile(byday.get(d, empty), h, 0)) for d in TRAIN]) for h in range(6, 22)}
    hours = sorted(sorted(counts, key=lambda h: (-counts[h], h))[:5])
    jobs, cases = [], []
    for hour in hours:
        donor = [profile(byday.get(d, empty), hour, lag) for d in TRAIN]
        n = min(sum(c) for c in donor)
        base = [min(n, max(c[j] for c in donor)) for j in range(lag + 30)]
        samples = [[min(n, x) for x in profile(byday.get(d, empty), hour, lag)] for d in CALIB]
        scores = [max([0] + [x - u for x, u in zip(c, base)]) for c in samples]
        q = sorted(scores)[ceil(20 * .95) - 1]
        q90 = sorted(scores)[ceil(20 * .90) - 1]
        upper = [min(n, u + q) if j >= lag else 0 for j, u in enumerate(base)]
        upper90 = [min(n, u + q90) if j >= lag else 0 for j, u in enumerate(base)]
        case = dict(case_id=f'LSZH_h{hour:02d}', airport='LSZH', hour=hour, n=n, lag=lag, delta=2,
                    service=[[min(n, x) for x in c] for c in donor], calibration_scores=scores, radius=q, radius90=q90,
                    base_upper=base, calibrated_upper=upper, calibrated_upper90=upper90,
                    evaluations=[dict(day=str(d), actual=[min(n, x) for x in profile(byday.get(d, empty), hour, lag)]) for d in EVAL])
        path = DATA / 'cases' / f'{case["case_id"]}.json'
        save(path, case)
        cases.append(dict(case_id=case['case_id'], hour=hour, n=n, radius=q, radius90=q90))
        for cap in sorted({n, ceil(n / 4), ceil(n / 8)}, reverse=True):
            jobs.append(dict(case_id=case['case_id'], hour=hour, n=n, cap=cap, lag=lag,
                             input_path=path.relative_to(ROOT).as_posix(), input_sha256=sha(path)))
    d = dict(source=SOURCE.relative_to(ROOT).as_posix(), source_sha256=sha(SOURCE), lag_slots=lag,
             training_taxi_p10=float(train_taxi.quantile(.1)), training_taxi_median=float(train_taxi.median()),
             training_dates=[str(x) for x in TRAIN], calibration_dates=[str(x) for x in CALIB],
             evaluation_dates=[str(x) for x in EVAL], hours=hours, training_hour_means=counts, cases=cases, jobs=jobs,
             selection='Hours, group size, travel time and range use training or calibration dates only; all later dates retained')
    save(DATA / 'design.json', d)
    print(json.dumps({k: v for k, v in d.items() if k not in ('jobs', 'training_hour_means')}, indent=1, default=str))
    return d


def replay(actual, upper, n, cap, lag, delay, budget, independent=False):
    h = len(upper)
    caps = (cap,) * h
    early = tuple(min(n, (j + 1) * cap) for j in range(h))
    ref = physical(early, actual, lag)
    leaves = []

    def rq(past, reports):
        if not independent:
            return requirement(upper, n, caps, lag, past, reports, 1)
        changed = list(upper)
        for j, y in reports:
            if y - 1 > upper[j]:
                return None
            changed[j] = min(changed[j], y + 1)
        return requirement(tuple(changed), n, caps, lag, past, (), 0)

    def walk(t, reports, pending, previous, releases, used, requests, exhausted):
        if t == h:
            dep = physical(releases, actual, lag)
            loss = tuple(a - b for a, b in zip(ref, dep))
            leaves.append(dict(post=sum(a - b for a, b in zip(releases, dep)), hold=sum(a - b for a, b in zip(early, releases)),
                               loss=max(loss), short=sum(loss), requests=requests, used=used))
            return
        b = rq(actual[:t], reports)
        invalid = exhausted or b is None
        z = min(n, previous + cap) if invalid else max(previous, b[t])
        target = t + lag + delay
        request = (not invalid) and z < n and requests < budget and target < h
        due = pending + (((t + delay, target),) if request else ())
        arrival = tuple(j for d, j in due if d == t + 1)
        rest = tuple((d, j) for d, j in due if d > t + 1)
        options = [(reports, used)]
        if arrival:
            j = arrival[0]
            options = [(tuple(sorted(reports + ((j, actual[j] + e),))), used + abs(e))
                       for e in range(-(1 - used), 2 - used) if 0 <= actual[j] + e <= n]
        for r, u in options:
            walk(t + 1, r, rest, z, releases + (z,), u, requests + request, invalid)
    walk(0, (), (), 0, (), 0, 0, False)
    return dict(covered=all(a <= u for a, u in zip(actual, upper)), complete=ref[-1] == n,
                preserved=all(r['short'] == 0 for r in leaves), max_loss=max(r['loss'] for r in leaves),
                worst_post=max(r['post'] for r in leaves), min_hold=min(r['hold'] for r in leaves),
                max_requests=max(r['requests'] for r in leaves), histories=len(leaves))


METHODS = [('none', 0, False), ('one', 1, False), ('three', 3, False), ('six', 6, False), ('three_independent', 3, True)]


def chrono_one(task):
    job, days = task
    c = read(ROOT / job['input_path'])
    rows = []
    for v in c['evaluations']:
        if days and v['day'] not in days:
            continue
        for delay in (1, 2):
            rows.append(dict(case_id=c['case_id'], hour=c['hour'], n=c['n'], cap=job['cap'], day=v['day'], delay=delay,
                             methods={m: replay(tuple(v['actual']), tuple(c['calibrated_upper']), c['n'], job['cap'], c['lag'], delay, q, ind)
                                      for m, q, ind in METHODS},
                             training_range=replay(tuple(v['actual']), tuple(c['base_upper']), c['n'], job['cap'], c['lag'], delay, 0),
                             range90=replay(tuple(v['actual']), tuple(c['calibrated_upper90']), c['n'], job['cap'], c['lag'], delay, 0)))
    requirement.cache_clear()
    return rows


def summarize(rows):
    names = [m for m, _, _ in METHODS]
    common = [r for r in rows if all(r['methods'][m]['complete'] and r['methods'][m]['preserved'] for m in names)]
    s = {}
    for m in names:
        s[m] = dict(preserved=sum(r['methods'][m]['preserved'] for r in rows), worst_loss=max(r['methods'][m]['max_loss'] for r in rows),
                    gain_s=float(np.mean([(r['methods']['none']['worst_post'] - r['methods'][m]['worst_post']) * 120 / r['n'] for r in common])) if common else None,
                    hold_s=float(np.mean([r['methods'][m]['min_hold'] * 120 / r['n'] for r in common])) if common else None,
                    mean_requests=float(np.mean([r['methods'][m]['max_requests'] for r in common])) if common else None)
    windows = {(r['case_id'], r['day']): r['methods']['none']['covered'] for r in rows}
    return dict(conditions=len(rows), common=len(common), windows=len(windows), covered=sum(windows.values()), methods=s,
                training_preserved=sum(r['training_range']['preserved'] for r in rows),
                range90_preserved=sum(r['range90']['preserved'] for r in rows))


def chrono(stage):
    d = design() if stage == 'smoke' else read(DATA / 'design.json')
    jobs = d['jobs']
    days = None
    if stage == 'smoke':
        big = max(jobs, key=lambda j: j['n'])
        jobs = [j for j in jobs if j['case_id'] == big['case_id']]
        days = [d['evaluation_dates'][0], d['evaluation_dates'][-1]]
    os.environ['OMP_NUM_THREADS'] = '1'
    rows = []
    t0 = perf_counter()
    with ProcessPoolExecutor(max_workers=max(1, min(4, (os.cpu_count() or 2) // 2))) as pool:
        for block in pool.map(chrono_one, [(j, days) for j in jobs]):
            rows.extend(block)
            print(json.dumps(dict(rows=len(rows), seconds=round(perf_counter() - t0, 1))), flush=True)
    s = summarize(rows)
    s['seconds'] = perf_counter() - t0
    save(OUT / f'chronological_{stage}.json', dict(summary=s, rows=rows))
    print(json.dumps(s, indent=1))


def finite_one(job):
    c = read(ROOT / job['input_path'])
    p = prepare(c['service'], c['n'], (job['cap'],) * len(c['service'][0]), c['lag'])
    row = dict(job, methods={})
    lead = c['lag'] + 2
    for depth in (2, 4, 6):
        rec = {}
        row['methods'][str(depth)] = rec
        try:
            m = TimedLookahead(p, lead, job['delay'], 1, 1, depth=depth, seconds_limit=60, state_limit=400000)
            m.solve()
            chk = stress(m, p)
            assert chk['calendars_with_loss'] == 0
            worst = max(r['worst_postrelease'] for r in chk['records'])
            cap = max(r['worst_requests'] for r in chk['records'])
            ex = BudgetedReports(p, lead, job['delay'], 1, 1, total_requests=cap, seconds_limit=60, state_limit=400000)
            v = ex.solve()
            a = stress(ex, p)
            assert a['calendars_with_loss'] == 0 and max(r['worst_postrelease'] for r in a['records']) == v['value'] <= worst
            rec.update(resolved=True, lookahead=worst * 2 / c['n'], exact=v['value'] * 2 / c['n'], cap=cap,
                       exact_requests=max(r['worst_requests'] for r in a['records']))
        except SearchLimit as e:
            rec.update(resolved=False, reason=str(e))
    return row


def finite(stage):
    d = read(DATA / 'design.json')
    jobs = [dict(j, delay=delay) for j in d['jobs'] for delay in (1, 2)]
    out = []
    for j in list(jobs):
        c = read(ROOT / j['input_path'])
        try:
            prepare(c['service'], c['n'], (j['cap'],) * len(c['service'][0]), c['lag'])
            out.append(j)
        except ValueError:
            pass
    jobs = out
    if stage == 'smoke':
        jobs = jobs[:2]
    rows = []
    with ProcessPoolExecutor(max_workers=max(1, min(4, (os.cpu_count() or 2) // 2))) as pool:
        for r in pool.map(finite_one, jobs):
            rows.append(r)
            print(json.dumps(dict(done=len(rows), total=len(jobs), resolved=all(v['resolved'] for v in r['methods'].values()))), flush=True)
    save(OUT / f'finite_{stage}.json', dict(rows=rows))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('part', choices=['chrono', 'finite'])
    ap.add_argument('stage', choices=['smoke', 'full'])
    a = ap.parse_args()
    chrono(a.stage) if a.part == 'chrono' else finite(a.stage)
