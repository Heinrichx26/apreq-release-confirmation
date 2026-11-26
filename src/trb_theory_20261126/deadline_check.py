"""Check the information-deadline theorem on every finite-calendar condition.

For each condition we compute the longest release-limited burst m and the
smallest service-announcement lead L* that reproduces the full-information
release. The theorem states L* <= travel + m.
"""
from pathlib import Path
import json, sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/trb_error_20261030'))
from robust_reports import prepare  # noqa: E402

DATA = ROOT/'data/trb_external_error_20261030'
OUT = ROOT/'results/trb_theory_20261126'


def burst(p):
    h, lag, caps = p['h'], p['lag'], p['caps']
    m = 0
    for ref in p['refs']:
        d = [ref[min(v+lag, h-1)] for v in range(h)]
        for t in range(h):
            room = 0
            for v in range(t+1, h):
                room += caps[v]
                if d[v]-room > d[t]:
                    m = max(m, v-t)
    return m


def threshold(p):
    h, paths = p['h'], p['paths']
    full = []
    for b in p['bounds']:
        u, row = 0, []
        for t in range(h):
            u = max(u, b[t])
            row.append(u)
        full.append(row)
    lead = -1
    for s in range(len(paths)):
        for q in range(s+1, len(paths)):
            diff = [x for x in range(h) if paths[s][x] != paths[q][x]]
            if not diff:
                continue
            kappa = diff[0]
            for t in range(h):
                if full[s][t] != full[q][t]:
                    lead = max(lead, kappa-t)
    return lead


def main():
    design = json.loads((DATA/'design.json').read_text(encoding='utf-8'))
    rows = []
    for job in design['jobs']:
        if job['delay'] != 1:
            continue
        c = json.loads((ROOT/job['input_path']).read_text(encoding='utf-8'))
        p = prepare(c['service'], c['n'], (job['cap'],)*len(c['service'][0]), c['lag'])
        m, star = burst(p), threshold(p)
        rows.append(dict(case_id=job['case_id'], airport=job['airport'], n=c['n'], cap=job['cap'],
                         lag=c['lag'], burst=m, lead_star=star, bound=c['lag']+m,
                         holds=star <= c['lag']+m, tight=star == c['lag']+m,
                         max_count=max(max(x) for x in c['service'])))
    out = dict(settings=len(rows), holds=sum(r['holds'] for r in rows),
               tight=sum(r['tight'] for r in rows),
               no_burst=sum(r['burst'] == 0 for r in rows), rows=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'deadline_check.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
