"""Build manuscript tables from stored result files; no experiment is rerun."""
import json
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
TAB = ROOT / 'results' / 'tables'
def load(p): return json.loads((ROOT / p).read_text(encoding='utf-8'))

us = load('results/trb_external_error_20261030/summary.json')['lookahead']
zr = load('results/opdi_trb/finite_full.json')['rows']
def zsum(depth, delay):
    rr = [r for r in zr if r['delay'] == delay]
    la = np.mean([r['methods'][depth]['lookahead'] for r in rr]); ex = np.mean([r['methods'][depth]['exact'] for r in rr])
    sv = np.mean([(r['methods'][depth]['lookahead'] - r['methods'][depth]['exact']) * 60 for r in rr])
    imp = sum((r['methods'][depth]['lookahead'] - r['methods'][depth]['exact']) > 1e-9 for r in rr)
    return la, ex, sv, imp, len(rr)
lines = [r'\begin{table}[!htbp]', r'\centering', r'\caption{Exact request selection relative to finite lookahead.}',
         r'\label{tab:finite_two_regions}', r'\tablefont', r'\begin{tabular}{@{}llrrrr@{}}', r'\toprule',
         r'Region & Response & Steps & Lookahead & Exact & Saving \\',
         r' & (min) & & (min/aircraft) & (min/aircraft) & (s/aircraft) \\', r'\midrule']
def fmt(la, ex, sv, imp, n):
    a = f'{la:.3f}'; b = f'{ex:.3f}'
    if abs(la - ex) < 1e-9: a = r'\textbf{' + a + '}'
    b = r'\textbf{' + b + '}'
    s = f'{sv:.1f} ({imp}/{n})'
    return a, b, s
for region, resp in (('United States', '2'), ('United States', '4')):
    for depth in ('2', '4', '6'):
        v = us[depth][resp]
        a, b, s = fmt(v['lookahead_minutes'], v['exact_minutes'], v['saved_seconds'], v['strictly_improved'], v['conditions'])
        lines.append(f'{region if depth=="2" else ""} & {resp if depth=="2" else ""} & {depth} & {a} & {b} & {s} \\\\')
lines.append(r'\midrule')
for delay, resp in ((1, '2'), (2, '4')):
    for depth in ('2', '4', '6'):
        a, b, s = fmt(*zsum(depth, delay))
        lines.append(f'{"Zurich" if depth=="2" else ""} & {resp if depth=="2" else ""} & {depth} & {a} & {b} & {s} \\\\')
lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
(TAB / 'finite_two_regions.tex').write_text('\n'.join(lines) + '\n', encoding='utf-8')

tr = load('results/opdi_trb/us_travel_full.json'); zc = load('results/opdi_trb/chronological_full.json')['summary']
rows = [('United States', '8', tr['4']), ('', '12', tr['6']), ('', '16', tr['8']), ('Zurich', '4', zc)]
lines = [r'\begin{table}[!htbp]', r'\centering', r'\caption{Additional gate holding from delayed confirmations on later dates.}',
         r'\label{tab:range_information_transfer}', r'\tablefont', r'\begin{tabular}{@{}llrrrrr@{}}', r'\toprule',
         r'Region & Travel & \multicolumn{4}{c}{Gain over no request (s/aircraft)} & Preserved \\', r'\cmidrule(lr){3-6}',
         r' & (min) & One & Three & Three, separate errors & Six & (three) \\', r'\midrule']
for reg, tv, s in rows:
    m = s['methods']
    lines.append(f"{reg} & {tv} & {m['one']['gain_s']:.1f} & \\textbf{{{m['three']['gain_s']:.1f}}} & {m['three_independent']['gain_s']:.1f} & {m['six']['gain_s']:.1f} & {m['three']['preserved']:,}/{s['conditions']:,} \\\\")
lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
(TAB / 'range_information_transfer.tex').write_text('\n'.join(lines) + '\n', encoding='utf-8')

mip = load('results/opdi_trb/mip_full.json')

lines = [r'\begin{table}[!htbp]', r'\centering', r'\caption{Exact request recursion and the direct scenario MIP solved by HiGHS.}',
         r'\label{tab:direct_scenario_comparison}', r'\tablefont', r'\begin{tabular}{@{}lrrrrrr@{}}', r'\toprule',
         r'Airport & Group & Response & \multicolumn{2}{c}{Recursion} & \multicolumn{2}{c}{HiGHS, 60 s limit} \\',
         r'\cmidrule(lr){4-5}\cmidrule(lr){6-7}',
         r' & size & (min) & Optimum & Time (s) & Bound & Variables \\', r'\midrule']
for r in mip['rows']:
    opt = 2 * r['dp']['value']; m = r['mip']
    bound = 'none' if m['dual_bound'] is None else f"{2*m['dual_bound']:.0f}"
    if m['resolved']:
        bound = r'\textbf{' + f"{2*m['value']:.0f}" + '} (solved)'
    lines.append(f"{r['airport']} & {r['n']} & {2*r['delay']} & \\textbf{{{opt}}} & {r['dp']['end_to_end_seconds']:.2f} & {bound} & {m['variables']:,} \\\\")
lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
(TAB / 'direct_scenario_comparison.tex').write_text('\n'.join(lines) + '\n', encoding='utf-8')


