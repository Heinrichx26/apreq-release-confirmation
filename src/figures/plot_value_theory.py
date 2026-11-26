"""Information deadline and value-capture figure from saved results. No experiment is rerun."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT/'results/figures'
ART.mkdir(parents=True, exist_ok=True)
RES = ROOT/'results/trb_theory_20261126'
plt.rcParams.update({'font.family': 'DejaVu Serif', 'font.size': 9, 'axes.titlesize': 9.5,
                     'axes.labelsize': 9, 'xtick.labelsize': 8.5, 'ytick.labelsize': 8.5,
                     'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
                     'axes.spines.top': False, 'axes.spines.right': False, 'axes.linewidth': .7})
BLUE, ORANGE, GREEN, GREY = '#245A81', '#BF6537', '#478372', '#7F8C95'
AIR = {'ATL': ('o', BLUE), 'CLT': ('s', ORANGE), 'DFW': ('^', GREEN)}


def tidy(ax):
    ax.grid(axis='y', color='#D4D8DC', lw=.5, alpha=.7)
    ax.set_axisbelow(True)
    ax.tick_params(length=3, width=.6)


def main():
    dl = json.loads((RES/'deadline_check.json').read_text())['rows']
    rows = json.loads((RES/'interval_full.json').read_text())['rows']
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw={'width_ratios': [1, 1.35]})
    ax = axs[0]
    counts = {}
    for r in dl:
        key = (r['airport'], 2*r['bound'], 2*r['lead_star'])
        counts[key] = counts.get(key, 0)+1
    offsets = {'ATL': -.35, 'CLT': 0, 'DFW': .35}
    for (air, x, y), n in counts.items():
        m, c = AIR[air]
        ax.scatter(x+offsets[air], y, s=14+9*n, marker=m, color=c, alpha=.8, lw=.4, edgecolor='white')
    ax.plot([11, 27], [11, 27], color=GREY, lw=.9, ls='--')
    ax.text(18.6, 19.4, 'notice = bound', color=GREY, fontsize=8, ha='right', va='center')
    ax.set(xlim=(10.5, 27.5), ylim=(10.5, 20.5), xlabel='Travel plus release-limited burst (min)',
           ylabel='Required notice (min)')
    ax.set_title('(a) Information deadline', pad=5)
    tidy(ax)
    ax = axs[1]
    valued = [r for r in rows if r['none'] > r['full'] and r['budget'] > 0]
    rng = np.random.default_rng(5)
    methods = (('exact', 'Exact', BLUE), ('lookahead2', 'Two-step', ORANGE), ('index', 'Index rule', GREY))
    for i, delay in enumerate((1, 2)):
        group = [r for r in valued if r['delay'] == delay]
        for j, (k, _, color) in enumerate(methods):
            v = 100*np.array([(r['none']-r[k])/(r['none']-r['full']) for r in group])
            x = i+(j-1)*.27
            ax.scatter(x+rng.uniform(-.06, .06, len(v)), v, s=7, color=color, alpha=.35, lw=0)
            ax.plot([x-.1, x+.1], [v.mean()]*2, color=color, lw=2.4, solid_capstyle='butt')
    ax.set_xticks([0, 1], ['2-min answer', '4-min answer'])
    ax.set(ylim=(-3, 103), ylabel='Full-information gain captured (%)')
    ax.set_title('(b) Value captured with about five requests', pad=5)
    tidy(ax)
    handles = [Line2D([], [], color=AIR[a][1], marker=AIR[a][0], lw=0, ms=5, label=a) for a in AIR]
    handles += [Line2D([], [], color=c, lw=2.2, label=l) for _, l, c in methods]
    fig.legend(handles=handles, loc='lower center', ncol=6, frameon=False, bbox_to_anchor=(.5, -.01),
               handlelength=1.6, columnspacing=1.3, fontsize=8.2)
    fig.subplots_adjust(left=.08, right=.99, top=.9, bottom=.27, wspace=.3)
    for ext in ('pdf', 'svg'):
        fig.savefig(ART/f'information_deadline_value.{ext}', bbox_inches='tight', pad_inches=.03)
    fig.savefig(RES/'information_deadline_value.png', dpi=200, bbox_inches='tight', pad_inches=.03)


if __name__ == '__main__':
    main()
