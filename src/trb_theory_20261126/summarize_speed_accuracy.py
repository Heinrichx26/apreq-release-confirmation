"""Summarize the answer-time and answer-accuracy experiment and write its table."""
from __future__ import annotations
from pathlib import Path
import json, random, statistics as st

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT/'results/trb_theory_20261126'
TAB = ROOT/'article/trb_apreq/tables'


def boot(xs, reps=10000, seed=11):
    rng = random.Random(seed)
    m = sorted(st.mean(rng.choice(xs) for _ in xs) for _ in range(reps))
    return m[int(0.025*reps)], m[int(0.975*reps)-1]


def main():
    d = json.loads((RES/'speed_accuracy_full.json').read_text(encoding='utf-8'))
    cells, solved, total = {}, 0, 0
    for r in d['rows']:
        for c in r['cells']:
            total += 1
            solved += c['resolved']
            gain = c['none']-c['full']
            if gain > 0:
                cells.setdefault((c['delay'], c['accuracy']), []).append((c['none']-c['exact'])/gain)
    out = dict(conditions=total, solved=solved, cells={})
    for (dl, g), xs in sorted(cells.items()):
        lo, hi = boot(xs)
        out['cells'][f'{2*dl}min_pm{g}'] = dict(mean=st.mean(xs), low=lo, high=hi, n=len(xs))
    wins = {}
    for dl in (2, 3, 4):
        k = n = 0
        for r in d['rows']:
            c = {(x['delay'], x['accuracy']): x for x in r['cells']}
            if c[dl, 0]['none']-c[dl, 0]['full'] <= 0:
                continue
            n += 1
            k += c[dl, 0]['exact'] < c[1, 1]['exact']
        wins[f'exact_{2*dl}min_beats_2min_pm1'] = [k, n]
    out['wins'] = wins
    (RES/'speed_accuracy_summary.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    rows = []
    for dl in (1, 2, 3, 4):
        vals = [out['cells'][f'{2*dl}min_pm{g}']['mean']*100 for g in (0, 1, 2)]
        best = max(vals)
        txt = [(r'\textbf{%.1f}' % v) if v == best else '%.1f' % v for v in vals]
        rows.append(f'{2*dl} & ' + ' & '.join(txt) + r' \\')
    lines = [r'\begin{table}[!htbp]', r'\centering',
             r'\caption{Mean share (\%) of the full-information gain captured with four requests, by answer time and answer accuracy.}',
             r'\label{tab:speed_accuracy}', r'\tablefont', r'\begin{tabular}{@{}lrrr@{}}', r'\toprule',
             r'Answer time (min) & Exact & Within one aircraft & Within two aircraft \\', r'\midrule',
             *rows, r'\bottomrule', r'\end{tabular}', r'\end{table}']
    (TAB/'speed_accuracy.tex').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
