"""Design chart: captured share of the full-information gain by answer time and request number.

For every US setting in the design file, the exact request policy is solved
for answer times of 1-4 slots and request numbers of 1-6, with the same
request lead as the main comparison. The captured share is
(none - exact) / (none - full).
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
REQUESTS = (1, 2, 3, 4, 5, 6)


def one(job):
    c = json.loads((ROOT/job['input_path']).read_text(encoding='utf-8'))
    n, lag = c['n'], c['lag']
    p = prepare(c['service'], n, (job['cap'],)*len(c['service'][0]), lag)
    lead = lag+2
    row = dict(case_id=job['case_id'], airport=job['airport'], n=n, cap=job['cap'], lag=lag,
               slot_minutes=c['delta'], cells=[])
    started = perf_counter()
    for delay in DELAYS:
        base = RobustReports(p, lead, delay, 1, 1, mode='none', seconds_limit=60)
        none = base.solve()['value']
        full = base.lower(0, (0,)*len(p['paths']), 0)
        for q in REQUESTS:
            cell = dict(delay=delay, requests=q, none=none, full=full)
            try:
                m = BudgetedReports(p, lead, delay, 1, 1, total_requests=q,
                                    seconds_limit=60, state_limit=200000)
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
    (OUT/f'design_chart_{stage}.json').write_text(
        json.dumps(dict(stage=stage, rows=rows, seconds=perf_counter()-start), indent=1),
        encoding='utf-8')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['smoke', 'full'])
    run(ap.parse_args().stage)
