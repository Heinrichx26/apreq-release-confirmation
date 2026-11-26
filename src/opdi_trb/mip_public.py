"""Direct scenario MIP versus request recursion on ADS-B and Zurich windows."""
import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from math import ceil
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/trb_error_20261030'))
sys.path.insert(0, str(ROOT / 'src/trb_calibrated_20261030'))
from robust_reports import prepare, RobustReports  # noqa: E402
from scenario_mip import ScenarioMIP  # noqa: E402

OUT = ROOT / 'results/opdi_trb'


def windows():
    rows = []
    for ap in ('ATL', 'CLT', 'DFW'):
        for p in sorted((ROOT / 'data/trb_external_error_20261030/cases' / ap).glob('*.json')):
            c = json.loads(p.read_text(encoding='utf-8'))
            try:
                prepare(c['service'], c['n'], (ceil(c['n'] / 4),) * len(c['service'][0]), c['lag'])
            except ValueError:
                continue
            rows.append(dict(airport=ap, path=str(p.relative_to(ROOT)), day=c['day'], hour=c['hour']))
            break
    for p in sorted((ROOT / 'data/opdi_trb/cases').glob('*.json')):
        c = json.loads(p.read_text(encoding='utf-8'))
        try:
            prepare(c['service'], c['n'], (ceil(c['n'] / 4),) * len(c['service'][0]), c['lag'])
        except ValueError:
            continue
        rows.append(dict(airport='LSZH', path=str(p.relative_to(ROOT)), day='training', hour=c['hour']))
        break
    return [dict(r, delay=d) for r in rows for d in (1, 2)]


def one(r):
    c = json.loads((ROOT / r['path']).read_text(encoding='utf-8'))
    p = prepare(c['service'], c['n'], (ceil(c['n'] / 4),) * len(c['service'][0]), c['lag'])
    t = perf_counter()
    m = RobustReports(p, c['lag'] + 2, r['delay'], 1, 1, seconds_limit=60, state_limit=500000)
    dp = m.solve()
    dp['end_to_end_seconds'] = perf_counter() - t
    assert m.verify()['passed']
    t = perf_counter()
    mip = ScenarioMIP(p, c['lag'] + 2, r['delay'], 1, 1, seconds_limit=60).solve()
    mip['end_to_end_seconds'] = perf_counter() - t
    if mip['resolved']:
        assert mip['value'] == dp['value']
    return dict(r, n=c['n'], dp=dp, mip=mip)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['smoke', 'full'])
    stage = ap.parse_args().stage
    jobs = windows()
    if stage == 'smoke':
        jobs = [j for j in jobs if j['airport'] == 'LSZH'][:1]
    with ProcessPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(one, jobs))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'mip_{stage}.json').write_text(json.dumps(dict(rows=rows), indent=2, default=str), encoding='utf-8')
    for r in rows:
        print(r['airport'], r['delay'], r['n'], r['dp']['value'], round(r['dp']['end_to_end_seconds'], 2),
              r['mip'].get('resolved'), r['mip'].get('value'), r['mip'].get('dual_bound'), round(r['mip']['end_to_end_seconds'], 2),
              r['mip'].get('scenarios'), r['mip'].get('variables'))
