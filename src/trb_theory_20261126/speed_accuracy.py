"""Answer time and answer accuracy on the US calendars.

For every US setting, the exact request policy is solved with answer
times of 1-4 slots, per-answer accuracy bounds of 0-2 takeoffs and four
requests. The captured share is (none - exact) / (none - full).
"""
from __future__ import annotations

from pathlib import Path
from time import perf_counter
import argparse, json, os, sys
from concurrent.futures import ProcessPoolExecutor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/trb_error_20261030'))
from robust_reports import RobustReports, SearchLimit, prepare  # noqa: E402
from budgeted_reports import BudgetedReports  # noqa: E402

DATA = ROOT/'data/trb_external_error_20261030'
OUT = ROOT/'results/trb_theory_20261126'
DELAYS = (1, 2, 3, 4)
ACCURACY = (0, 1, 2)
REQUESTS = 4


def one(job):
    c = json.loads((ROOT/job['input_path']).read_text(encoding='utf-8'))
    n, lag = c['n'], c['lag']
    p = prepare(c['service'], n, (job['cap'],)*len(c['service'][0]), lag)
    lead = lag+2
    row = dict(case_id=job['case_id'], airport=job['airport'], n=n, cap=job['cap'], lag=lag, cells=[])
    started = perf_counter()
    for delay in DELAYS:
        base = RobustReports(p, lead, delay, 1, 0, mode='none', seconds_limit=60)
        none = base.solve()['value']
        full = base.lower(0, (0,)*len(p['paths']), 0)
        for g in ACCURACY:
            cell = dict(delay=delay, accuracy=g, none=none, full=full)
            try:
                m = BudgetedReports(p, lead, delay, 1, g, total_requests=REQUESTS,
                                    independent_errors=True, seconds_limit=120, state_limit=300000)
                cell['exact'] = m.solve()['value']
                cell['resolved'] = True
            except SearchLimit as exc:
                cell.update(resolved=False, reason=str(exc))
            row['cells'].append(cell)
    row['seconds'] = perf_counter()-started
    return row


def run(stage):
    d = json.loads((DATA/'design.json').read_text(encoding='utf-8'))
    jobs = [j for j in d['jobs'] if j['delay'] == 1]
    if stage == 'smoke':
        jobs = jobs[:3]
    os.environ['OMP_NUM_THREADS'] = '1'
    workers = max(1, min(6, (os.cpu_count() or 2)-2))
    rows, start = [], perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i, r in enumerate(pool.map(one, jobs), 1):
            rows.append(r)
            print(json.dumps(dict(done=i, total=len(jobs), seconds=round(perf_counter()-start, 1),
                                  case=r['case_id'])), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/f'speed_accuracy_{stage}.json').write_text(
        json.dumps(dict(stage=stage, rows=rows, seconds=perf_counter()-start), indent=1),
        encoding='utf-8')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['smoke', 'full'])
    run(ap.parse_args().stage)
