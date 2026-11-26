"""Summary of the design chart: mean captured share, bootstrap intervals and marginal values."""
from pathlib import Path
import json, random, statistics as st

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT/'results/trb_theory_20261126'


def boot(xs, reps=10000, seed=7):
    rng = random.Random(seed)
    means = sorted(st.mean(rng.choices(xs, k=len(xs))) for _ in range(reps))
    return means[int(0.025*reps)], means[int(0.975*reps)-1]


def main():
    rows = json.loads((RES/'design_chart_full.json').read_text())['rows']
    assert all(c['resolved'] for r in rows for c in r['cells'])
    out = dict(settings=len(rows), cells={}, marginal={})
    for r in rows:
        r['by'] = {(c['delay'], c['requests']): c for c in r['cells']}
    for delay in (1, 2, 3, 4):
        for q in range(1, 7):
            xs = []
            for r in rows:
                c = r['by'][(delay, q)]
                if c['none'] > c['full']:
                    xs.append(100*(c['none']-c['exact'])/(c['none']-c['full']))
            lo, hi = boot(xs)
            secs = [(r['by'][(delay, q)]['none']-r['by'][(delay, q)]['exact'])*r['slot_minutes']*60/r['n']
                    for r in rows]
            out['cells'][f'{delay},{q}'] = dict(mean=st.mean(xs), low=lo, high=hi, n=len(xs),
                                                 seconds=st.mean(secs),
                                                 zero=sum(x == 0 for x in xs))
        prev = [0.0]*len(rows)
        marg = []
        for q in range(1, 7):
            cur = [100*(r['by'][(delay, q)]['none']-r['by'][(delay, q)]['exact'])
                   / (r['by'][(delay, q)]['none']-r['by'][(delay, q)]['full']) for r in rows]
            marg.append(st.mean(c-p for c, p in zip(cur, prev)))
            prev = cur
        out['marginal'][str(delay)] = marg
    monotone, second = 0, 0
    for r in rows:
        for q in range(1, 7):
            v = [r['by'][(d, q)]['exact'] for d in (1, 2, 3, 4)]
            monotone += any(v[i+1] < v[i] for i in range(3))
        for d in (1, 2, 3, 4):
            v = [r['by'][(d, q)]['exact'] for q in range(1, 7)]
            monotone += any(v[i+1] > v[i] for i in range(5))
        c = r['by']
        g1 = c[(1, 1)]['none']-c[(1, 1)]['exact']
        g2 = c[(1, 1)]['exact']-c[(1, 2)]['exact']
        second += g2 > g1
    increasing = 0
    for r in rows:
        for d in (1, 2):
            v = [r['by'][(d, 1)]['none']]+[r['by'][(d, q)]['exact'] for q in range(1, 7)]
            gain = [v[i]-v[i+1] for i in range(6)]
            increasing += any(gain[i+1] > gain[i] for i in range(5))
    out.update(monotonicity_violations=monotone, second_exceeds_first=second,
               increasing_marginal_conditions=increasing, conditions=2*len(rows))
    (RES/'design_chart_summary.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items() if k != 'cells'}, indent=1))
    for k, v in out['cells'].items():
        print(k, round(v['mean'], 1), round(v['low'], 1), round(v['high'], 1), round(v['seconds'], 1), v['zero'])


if __name__ == '__main__':
    main()
