"""Plot APREQ evidence from saved result files. No experiment is imported or rerun."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'results/figures'
OUT = ROOT / 'results/opdi_trb/figures'
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family': 'DejaVu Serif', 'font.size': 9, 'axes.titlesize': 9.5,
                     'axes.labelsize': 9, 'xtick.labelsize': 8.5, 'ytick.labelsize': 8.5,
                     'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
                     'axes.spines.top': False, 'axes.spines.right': False, 'axes.linewidth': .7})
BLUE, ORANGE, GREEN, GREY = '#245A81', '#BF6537', '#478372', '#7F8C95'


def read(p):
    return json.loads((ROOT / p).read_text(encoding='utf-8'))


def tidy(ax):
    ax.grid(axis='y', color='#D4D8DC', lw=.5, alpha=.7)
    ax.set_axisbelow(True)
    ax.tick_params(length=3, width=.6)


def save(fig, name):
    for ext in ('pdf', 'svg'):
        fig.savefig(ART / f'{name}.{ext}', bbox_inches='tight', pad_inches=.03)
    fig.savefig(OUT / f'{name}.png', dpi=200, bbox_inches='tight', pad_inches=.03)
    plt.close(fig)


def lookahead_figure():
    us = read('results/trb_external_error_20261030/full.json')['rows']
    zr = read('results/opdi_trb/finite_full.json')['rows']
    us_lag, zr_lag = 6, 2
    savings = {}
    for region, rows, conv in (('us', us, lambda m, k: (m[k]['lookahead']['minutes'] - m[k]['exact']['minutes']) * 60),
                               ('zr', zr, lambda m, k: (m[k]['lookahead'] - m[k]['exact']) * 60)):
        for delay in (1, 2):
            for depth in ('2', '4', '6'):
                savings[region, delay, depth] = np.array([max(0., conv(r['methods'], depth)) for r in rows if r['delay'] == delay])
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.75), gridspec_kw={'width_ratios': [1, 1, 1.12]})
    rng = np.random.default_rng(7)
    for ax, region, title in ((axs[0], 'us', '(a) ATL, CLT and DFW'), (axs[1], 'zr', '(b) Zurich')):
        for i, depth in enumerate(('2', '4', '6')):
            for j, (delay, color) in enumerate(((1, BLUE), (2, ORANGE))):
                v = savings[region, delay, depth]
                x = i + (j - .5) * .34
                ax.scatter(x + rng.uniform(-.07, .07, len(v)), v, s=7, color=color, alpha=.35, lw=0)
                ax.plot([x - .13, x + .13], [v.mean()] * 2, color=color, lw=2.3, solid_capstyle='butt')
        ax.set_xticks(range(3), ['2', '4', '6'])
        ax.set_xlabel('Lookahead steps')
        ax.set_title(title, pad=5)
        tidy(ax)
    axs[0].set_ylabel('Exact saving (s/aircraft)')
    axs[0].set_ylim(-8, 250)
    axs[1].set_ylim(-2, 40)
    ax = axs[2]
    for region, lag, marker in (('us', us_lag, 'o'), ('zr', zr_lag, 's')):
        for delay, color in ((1, BLUE), (2, ORANGE)):
            xs, ys = [], []
            for depth in ('2', '4', '6'):
                v = savings[region, delay, depth]
                xs.append(int(depth) - (lag + delay))
                ys.append(100 * np.mean(v < 1e-9))
            ax.plot(xs, ys, marker=marker, color=color, lw=1.2, ms=4.5, mfc='white' if region == 'zr' else color)
    ax.axvline(0, color=GREY, lw=.8, ls='--')
    ax.axvspan(0, 3.6, color=GREEN, alpha=.07, lw=0)
    ax.set(xlim=(-6.6, 3.6), ylim=(55, 103), xlabel='Lookahead margin (slots)',
           ylabel='Conditions at optimum (%)')
    ax.set_title('(c) Lookahead span', pad=5)
    tidy(ax)
    handles = [Line2D([], [], color=BLUE, lw=2, label='2-min answer'), Line2D([], [], color=ORANGE, lw=2, label='4-min answer'),
               Line2D([], [], color='k', marker='o', lw=0, ms=4.5, label='United States'),
               Line2D([], [], color='k', marker='s', mfc='white', lw=0, ms=4.5, label='Zurich')]
    fig.legend(handles=handles, loc='lower center', ncol=4, frameon=False, bbox_to_anchor=(.5, -.015),
               handlelength=1.8, columnspacing=1.6)
    fig.subplots_adjust(left=.08, right=.985, top=.9, bottom=.31, wspace=.4)
    save(fig, 'request_lookahead_comparison')


def information_figure():
    tr = read('results/opdi_trb/us_travel_full.json')
    zc = read('results/opdi_trb/chronological_full.json')['summary']
    settings = [('ATL/CLT/DFW, 8 min', tr['4'], BLUE, '-'), ('ATL/CLT/DFW, 12 min', tr['6'], BLUE, '--'),
                ('ATL/CLT/DFW, 16 min', tr['8'], BLUE, ':'), ('Zurich, 4 min', zc, ORANGE, '-')]
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.85), gridspec_kw={'width_ratios': [1.25, 1]})
    for label, s, color, ls in settings:
        m = s['methods']
        xs = [m[k]['mean_requests'] for k in ('none', 'one', 'three', 'six')]
        ys = [m[k]['gain_s'] for k in ('none', 'one', 'three', 'six')]
        axs[0].plot(xs, ys, ls=ls, marker='o', ms=3.8, color=color, lw=1.4, label=label)
    axs[0].set(xlabel='Mean confirmations issued', ylabel='Added gate holding (s/aircraft)', xlim=(-.2, 6.3), ylim=(-6, 195))
    axs[0].set_title('(a) Confirmations and gate holding', pad=5)
    x = np.arange(len(settings))
    sep = [s['methods']['three_independent']['gain_s'] for _, s, _, _ in settings]
    sha = [s['methods']['three']['gain_s'] for _, s, _, _ in settings]
    cols = [c for _, _, c, _ in settings]
    axs[1].bar(x - .19, sep, .36, color=cols, alpha=.35, edgecolor=cols, lw=.8)
    axs[1].bar(x + .19, sha, .36, color=cols, edgecolor=cols, lw=.8)
    for xi, a, b in zip(x, sep, sha):
        axs[1].text(xi + .19, b + 1.5, f'+{b - a:.1f}', ha='center', fontsize=7.8)
    axs[1].set_xticks(x, ['US\n8 min', 'US\n12 min', 'US\n16 min', 'Zurich\n4 min'])
    axs[1].set(ylabel='Added gate holding (s/aircraft)', ylim=(0, 86))
    axs[1].set_title('(b) Three confirmations', pad=5)
    for ax in axs:
        tidy(ax)
    h0, l0 = axs[0].get_legend_handles_labels()
    h1 = [Patch(fc=GREY, alpha=.35, ec=GREY, label='Separate errors'), Patch(fc=GREY, ec=GREY, label='Shared allowance')]
    fig.legend(handles=h0 + h1, loc='lower center', ncol=3, frameon=False, bbox_to_anchor=(.5, -.01),
               handlelength=2.0, columnspacing=1.4, fontsize=8.2)
    fig.subplots_adjust(left=.08, right=.99, top=.9, bottom=.33, wspace=.3)
    save(fig, 'information_value_transfer')


if __name__ == '__main__':
    lookahead_figure()
    information_figure()
    print('figures written')



