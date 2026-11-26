"""Summarize the directional-flow experiment: deadlines, policies, design chart."""
from __future__ import annotations
from pathlib import Path
import json, sys, random, statistics as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/trb_error_20261030'))
sys.path.insert(0, str(ROOT/'src/trb_theory_20261126'))
from robust_reports import prepare  # noqa: E402
from deadline_check import burst, threshold  # noqa: E402
from scipy.stats import wilcoxon  # noqa: E402

DATA = ROOT/'data/trb_flow_20261126'
RES = ROOT/'results/trb_flow_20261126'
TAB = ROOT/'article/trb_apreq/tables'


def boot(xs, reps=10000, seed=5):
    rng = random.Random(seed)
    m = sorted(st.mean(rng.choice(xs) for _ in xs) for _ in range(reps))
    return m[int(.025*reps)], m[int(.975*reps)-1]


def main():
    design = json.loads((DATA/'design.json').read_text(encoding='utf-8'))
    groups = [g for g in design['groups'] if g['n'] >= 2]
    dl = []
    for job in design['jobs']:
        if job['delay'] != 1:
            continue
        c = json.loads((ROOT/job['input_path']).read_text(encoding='utf-8'))
        p = prepare(c['service'], c['n'], (job['cap'],)*len(c['service'][0]), c['lag'])
        m, s = burst(p), threshold(p)
        dl.append(dict(m=m, star=s, bound=c['lag']+m, cap=job['cap'], n=c['n']))
    rows = json.loads((RES/'flow_full.json').read_text(encoding='utf-8'))['rows']
    pol = [r for r in rows if r['kind'] == 'policy']
    out = dict(groups=len(groups), settings=len(dl),
               sizes=[min(g['n'] for g in groups), max(g['n'] for g in groups)],
               share=[min(g['share'] for g in groups), st.mean(g['share'] for g in groups),
                      max(g['share'] for g in groups)],
               deadline=dict(holds=sum(r['star'] <= r['bound'] for r in dl),
                             tight=sum(r['star'] == r['bound'] for r in dl),
                             no_burst=sum(r['m'] == 0 for r in dl),
                             star_equals_lag=sum(r['star'] == 6 for r in dl),
                             star_max=max(r['star'] for r in dl)),
               policy_conditions=len(pol), unresolved=sum(not r['resolved'] for r in pol), cells={})
    for g in (0, 1):
        for d in (1, 2):
            rs = [r for r in pol if r['gamma'] == g and r['delay'] == d and r['budget'] > 0
                  and r['none'] > r['full']]
            cell = dict(n=len(rs), budget=st.mean(r['budget'] for r in rs))
            for k in ('exact', 'lookahead2', 'index'):
                xs = [(r['none']-r[k])/(r['none']-r['full']) for r in rs]
                lo, hi = boot(xs)
                cell[k] = dict(mean=st.mean(xs), low=lo, high=hi)
            for k in ('lookahead2', 'index'):
                diff = [r[k]-r['exact'] for r in rs]
                cell[f'p_{k}'] = float(wilcoxon(diff, alternative='greater', zero_method='zsplit').pvalue)
                cell[f'better_than_{k}'] = sum(x > 0 for x in diff)
            out['cells'][f'gamma{g}_{2*d}min'] = cell
    ps = sorted((v, k) for k, c in out['cells'].items() for v in (c['p_lookahead2'], c['p_index']))
    m = len(ps)
    out['holm_max'] = max(min(1, (m-i)*p) for i, (p, _) in enumerate(ps))
    (RES/'flow_summary.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    def f(c, k):
        return 100*c[k]['mean']
    lines = [r'\begin{table}[!htbp]', r'\centering',
             r'\caption{Share of the full-information gain captured in directional departure flows.}',
             r'\label{tab:flow_capture}', r'\tablefont', r'\begin{tabular}{@{}llrrrrr@{}}', r'\toprule',
             r'Answers & Answer & Settings & Requests & Exact & Two-step & Index \\',
             r' & (min) & & (mean) & (\%) & lookahead (\%) & rule (\%) \\',
             r'\midrule']
    for g, lab in ((0, 'Exact'), (1, 'One error')):
        for d in (1, 2):
            c = out['cells'][f'gamma{g}_{2*d}min']
            vals = [f(c, k) for k in ('exact', 'lookahead2', 'index')]
            txt = []
            for k, v in zip(('exact', 'lookahead2', 'index'), vals):
                s = '%.1f [%.1f, %.1f]' % (v, 100*c[k]['low'], 100*c[k]['high'])
                txt.append(r'\textbf{%s}' % s if v == max(vals) else s)
            lines.append(f"{lab if d == 1 else ''} & {2*d} & {c['n']} & {c['budget']:.1f} & " + ' & '.join(txt) + r' \\')
    lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
    (TAB/'flow_capture.tex').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items()}, indent=1))


if __name__ == '__main__':
    main()
