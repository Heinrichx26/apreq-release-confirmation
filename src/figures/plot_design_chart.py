"""Answer time and request number figure from the saved design-chart summary. No experiment is rerun."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT/'results/figures'
RES = ROOT/'results/trb_theory_20261126'
plt.rcParams.update({'font.family': 'DejaVu Serif', 'font.size': 9, 'axes.titlesize': 9.5,
                     'axes.labelsize': 9, 'xtick.labelsize': 8.5, 'ytick.labelsize': 8.5,
                     'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
                     'axes.spines.top': False, 'axes.spines.right': False, 'axes.linewidth': .7})
COLORS = {1: '#245A81', 2: '#478372', 3: '#BF6537', 4: '#7F8C95'}
MARKERS = {1: 'o', 2: 's', 3: '^', 4: 'D'}


def tidy(ax):
    ax.grid(axis='y', color='#D4D8DC', lw=.5, alpha=.7)
    ax.set_axisbelow(True)
    ax.tick_params(length=3, width=.6)


def main():
    s = json.loads((RES/'design_chart_summary.json').read_text())
    q = np.arange(1, 7)
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.75), gridspec_kw={'width_ratios': [1.1, 1]})
    ax = axs[0]
    for d in (1, 2, 3, 4):
        cells = [s['cells'][f'{d},{k}'] for k in q]
        mean = [c['mean'] for c in cells]
        ax.fill_between(q, [c['low'] for c in cells], [c['high'] for c in cells],
                        color=COLORS[d], alpha=.12, lw=0)
        ax.plot(q, mean, color=COLORS[d], marker=MARKERS[d], ms=3.8, lw=1.4,
                label=f'{2*d}-min answers')
    ax.set(xlim=(.7, 6.3), ylim=(0, 85), xticks=q, xlabel='Requests per hour',
           ylabel='Gain captured (%)')
    ax.set_title('(a) Captured gain', pad=5)
    tidy(ax)
    ax = axs[1]
    width = .19
    for i, d in enumerate((1, 2, 3, 4)):
        ax.bar(q+(i-1.5)*width, s['marginal'][str(d)], width, color=COLORS[d], lw=0, alpha=.9)
    ax.set(xlim=(.45, 6.55), ylim=(0, 31), xticks=q, xlabel='Request added',
           ylabel='Added gain (points)')
    ax.set_title('(b) Gain added by each request', pad=5)
    tidy(ax)
    handles, labels = axs[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=4, frameon=False,
               bbox_to_anchor=(.5, .0), handlelength=1.8, columnspacing=1.6, fontsize=8.2)
    fig.subplots_adjust(left=.08, right=.99, top=.9, bottom=.25, wspace=.28)
    for ext in ('pdf', 'svg'):
        fig.savefig(ART/f'answer_time_requests.{ext}', bbox_inches='tight', pad_inches=.03)
    fig.savefig(RES/'answer_time_requests.png', dpi=200, bbox_inches='tight', pad_inches=.03)


if __name__ == '__main__':
    main()
