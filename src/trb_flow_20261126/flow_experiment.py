"""Policy comparison and design chart on directional departure flows."""
from __future__ import annotations
from pathlib import Path
from time import perf_counter
import argparse, json, os, sys
from concurrent.futures import ProcessPoolExecutor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/trb_theory_20261126'))
sys.path.insert(0, str(ROOT/'src/trb_error_20261030'))
import interval_schedule as iv  # noqa: E402
from robust_reports import RobustReports, SearchLimit, prepare  # noqa: E402
from budgeted_reports import BudgetedReports  # noqa: E402

DATA = ROOT/'data/trb_flow_20261126'
OUT = ROOT/'results/trb_flow_20261126'


def chart(job):
    c = json.loads((ROOT/job['input_path']).read_text(encoding='utf-8'))
    p = prepare(c['service'], c['n'], (job['cap'],)*len(c['service'][0]), c['lag'])
    lead = c['lag']+2
    row = dict(job, cells=[])
    for delay in (1, 2, 3, 4):
        base = RobustReports(p, lead, delay, 1, 1, mode='none', seconds_limit=60)
        none, full = base.solve()['value'], base.lower(0, (0,)*len(p['paths']), 0)
        for q in range(1, 7):
            cell = dict(delay=delay, requests=q, accuracy='shared1', none=none, full=full)
            try:
                cell['exact'] = BudgetedReports(p, lead, delay, 1, 1, total_requests=q, seconds_limit=90,
                                                state_limit=300000).solve()['value']
                cell['resolved'] = True
            except SearchLimit as e:
                cell.update(resolved=False, reason=str(e))
            row['cells'].append(cell)
        base0 = RobustReports(p, lead, delay, 1, 0, mode='none', seconds_limit=60)
        none0 = base0.solve()['value']
        for g in (0, 1, 2):
            cell = dict(delay=delay, requests=4, accuracy=g, none=none0, full=full)
            try:
                cell['exact'] = BudgetedReports(p, lead, delay, 1, g, total_requests=4, independent_errors=True,
                                                seconds_limit=90, state_limit=300000).solve()['value']
                cell['resolved'] = True
            except SearchLimit as e:
                cell.update(resolved=False, reason=str(e))
            row['cells'].append(cell)
    return row


def evaluate(model, p, g):
    model.solve()
    check = iv.stress(model, p, error_allowance=g)
    assert check['calendars_with_loss'] == 0
    return (max(r['worst_postrelease'] for r in check['records']),
            max(r['worst_requests'] for r in check['records']))


def policy(job):
    """Exact recursion, two-step lookahead and index rule with a common request total."""
    c = json.loads((ROOT/job['input_path']).read_text(encoding='utf-8'))
    g, delay = job['gamma'], job['delay']
    p = prepare(c['service'], c['n'], (job['cap'],)*len(c['service'][0]), c['lag'])
    lead = c['lag']+2
    row = dict(job)
    try:
        base = RobustReports(p, lead, delay, 1, g, mode='none', seconds_limit=60)
        row['none'] = base.solve()['value']
        row['full'] = base.lower(0, (0,)*len(p['paths']), 0)
        two = iv.RolloutReports(p, lead, delay, 1, g, depth=2, seconds_limit=90, state_limit=300000)
        row['lookahead2'], budget = evaluate(two, p, g)
        row['budget'] = budget
        ex = BudgetedReports(p, lead, delay, 1, g, total_requests=budget, seconds_limit=90, state_limit=300000)
        row['exact'], row['exact_requests'] = evaluate(ex, p, g)
        ix = iv.IndexPolicy(p, lead, delay, 1, g, total_requests=budget, seconds_limit=300, state_limit=400000)
        row['index'], row['index_requests'] = evaluate(ix, p, g)
        row['resolved'] = True
    except SearchLimit as e:
        row.update(resolved=False, reason=str(e))
    return row


def task(job):
    t = perf_counter()
    if job['kind'] == 'policy':
        r = policy(job)
    else:
        r = chart(job)
    r['kind'] = job['kind']
    r['seconds'] = perf_counter()-t
    return r


def run(stage):
    d = json.loads((DATA/'design.json').read_text(encoding='utf-8'))
    jobs = d['jobs']
    if stage == 'smoke':
        one = [j for j in jobs if j['delay'] == 1]
        jobs = [one[0], max(one, key=lambda j: (j['n'], -j['cap'])),
                max(one, key=lambda j: (j['n'], j['cap']))]
    tasks = [dict(j, kind='policy', gamma=g) for j in jobs for g in (0, 1)]
    tasks += [dict(j, kind='chart') for j in jobs if j['delay'] == 1]
    os.environ['OMP_NUM_THREADS'] = '1'
    workers = max(1, min(6, (os.cpu_count() or 2)-2))
    rows, start = [], perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i, r in enumerate(pool.map(task, tasks), 1):
            rows.append(r)
            print(json.dumps(dict(done=i, total=len(tasks), seconds=round(perf_counter()-start, 1),
                                  kind=r['kind'], case=r['case_id'], cap=r['cap'])), flush=True)
            if stage == 'full' and i % 20 == 0:
                (OUT/'flow_partial.json').write_text(json.dumps(rows), encoding='utf-8')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/f'flow_{stage}.json').write_text(json.dumps(dict(stage=stage, rows=rows,
                                                          seconds=perf_counter()-start), indent=1), encoding='utf-8')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['smoke', 'full'])
    run(ap.parse_args().stage)
