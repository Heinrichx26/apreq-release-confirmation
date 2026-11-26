"""Summaries, paired tests and the LaTeX table for the value-capture comparison."""
from pathlib import Path
import json, random, statistics as st
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT/'results/trb_theory_20261126'
TAB = ROOT/'results/tables'


def share(r, k):
    return (r['none']-r[k])/(r['none']-r['full'])


def boot(xs, reps=10000, seed=3):
    rng = random.Random(seed)
    means = sorted(st.mean(rng.choices(xs, k=len(xs))) for _ in range(reps))
    return means[int(0.025*reps)], means[int(0.975*reps)-1]


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0]*len(ps), 0
    for rank, i in enumerate(order):
        run = max(run, min(1, (len(ps)-rank)*ps[i]))
        adj[i] = run
    return adj


def main():
    rows = json.loads((RES/'interval_full.json').read_text())['rows']
    assert all(r['resolved'] for r in rows)
    valued = [r for r in rows if r['none'] > r['full'] and r['budget'] > 0]
    out, tests = {}, []
    for delay in (1, 2):
        group = [r for r in valued if r['delay'] == delay]
        block = dict(conditions=len(group))
        for k in ('exact', 'lookahead2', 'index'):
            xs = [share(r, k) for r in group]
            lo, hi = boot(xs)
            block[k] = dict(mean=st.mean(xs), low=lo, high=hi, minimum=min(xs))
        for k in ('lookahead2', 'index'):
            gap = [(r[k]-r['exact'])*r['slot_minutes']*60/r['n'] for r in group]
            nonzero = [g for g in gap if g]
            p = wilcoxon(nonzero, alternative='greater').pvalue if nonzero else 1.0
            block[k+'_gap'] = dict(mean_seconds=st.mean(gap), maximum_seconds=max(gap),
                                  ties=len(gap)-len(nonzero), p=p)
            tests.append((delay, k, p))
        block['requests'] = st.mean(r['budget'] for r in group)
        out[str(delay)] = block
    adjusted = holm([p for _, _, p in tests])
    for (delay, k, _), a in zip(tests, adjusted):
        out[str(delay)][k+'_gap']['holm'] = a
    deadline = json.loads((RES/'deadline_check.json').read_text())
    out['deadline'] = {k: v for k, v in deadline.items() if k != 'rows'}
    out['ranges'] = range_statistics()
    (RES/'value_capture_summary.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    write_table(out)
    print(json.dumps(out, indent=1))


def range_statistics():
    """Slot-wise ranges of the training calendars used in the comparison."""
    design = json.loads((ROOT/'data/trb_external_error_20261030/design.json').read_text())
    seen, slots, zero, narrow, widths = set(), 0, 0, 0, []
    for job in design['jobs']:
        if job['input_path'] in seen:
            continue
        seen.add(job['input_path'])
        cal = json.loads((ROOT/job['input_path']).read_text())['service']
        h = len(cal[0])
        lo = [min(s[x] for s in cal) for x in range(h)]
        hi = [max(s[x] for s in cal) for x in range(h)]
        slots += h
        zero += sum(v == 0 for v in lo)
        narrow += 2*max(b-a for a, b in zip(lo, hi)) <= min(lo)
        widths += [b-a for a, b in zip(lo, hi)]
    return dict(calendar_sets=len(seen), slots=slots, zero_lower=zero, narrow_sets=narrow,
                mean_width=st.mean(widths))


def write_table(out):
    def pct(b):
        return f"{100*b['mean']:.1f} [{100*b['low']:.1f}, {100*b['high']:.1f}]"
    lines = [r'\begin{table}[!htbp]', r'\centering',
             r'\caption{Share of the full-information gate-holding gain captured with the same requests.}',
             r'\label{tab:value_capture}', r'\tablefont',
             r'\begin{tabular}{@{}lrrrrr@{}}', r'\toprule',
             r'Answer & Conditions & Requests & Exact & Two-step & Index \\',
             r'(min) & & (mean) & (\%) & lookahead (\%) & rule (\%) \\', r'\midrule']
    for delay, minutes in (('1', 2), ('2', 4)):
        b = out[delay]
        lines.append(f"{minutes} & {b['conditions']} & {b['requests']:.1f} & "
                     f"\\textbf{{{pct(b['exact'])}}} & {pct(b['lookahead2'])} & {pct(b['index'])} \\\\")
    lines.append(r'\midrule')
    for delay, minutes in (('1', 2), ('2', 4)):
        b = out[delay]
        lines.append(f"{minutes} & \\multicolumn{{2}}{{l}}{{Exact saving (s/aircraft)}} & -- & "
                     f"{b['lookahead2_gap']['mean_seconds']:.1f} & {b['index_gap']['mean_seconds']:.1f} \\\\")
    lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
    TAB.mkdir(parents=True, exist_ok=True)
    (TAB/'value_capture.tex').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
