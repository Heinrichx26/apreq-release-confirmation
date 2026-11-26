"""Checks of the structural results on confirmation value.

1. Additive value and assignment solution under narrow slot-wise ranges.
2. Interaction of confirmations under wide ranges.
3. The four-calendar example: no request, best fixed schedule, adaptive
   policy and full information, all with exact answers.
Post-release excess is measured in aircraft-slots.
"""
from itertools import combinations
from pathlib import Path
import json, random, sys

import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/trb_error_20261030'))
from robust_reports import prepare  # noqa: E402
from budgeted_reports import BudgetedReports  # noqa: E402

OUT = ROOT/'results/trb_theory_20261126'


def excess(lo, hi, lag, known, c, last):
    released, total = None, 0
    for t in range(last+1):
        a = sum(c[x] if known[x] <= t else hi[x] for x in range(t+lag+1))
        released = a if released is None else max(released, a)
        total += released-sum(c[:t+lag+1])
    return total


def schedules(lead, delay, budget, uncertain):
    pairs = [(r, j) for j in uncertain for r in range(max(0, j-lead), j-delay+1)]
    out = [()]
    for k in range(1, budget+1):
        for combo in combinations(pairs, k):
            if len({r for r, _ in combo}) == k and len({j for _, j in combo}) == k:
                out.append(combo)
    return out


def known_of(h, combo, delay):
    known = [x+1 for x in range(h)]
    for r, j in combo:
        known[j] = min(known[j], r+delay)
    return known


def effective(x, a, lag, last):
    lo_t, hi_t = max(a, x-lag, 0), min(x, last)
    return max(0, hi_t-lo_t+1)


def gain(lo, hi, lag, delay, last, r, j):
    return (hi[j]-lo[j])*effective(j, r+delay, lag, last)


def assignment(lo, hi, lag, lead, delay, budget, uncertain, last):
    pairs = [(r, j) for j in uncertain for r in range(max(0, j-lead), j-delay+1)]
    if not pairs:
        return 0
    w = np.array([gain(lo, hi, lag, delay, last, r, j) for r, j in pairs], float)
    rows, ub = [], []
    for r in sorted({r for r, _ in pairs}):
        rows.append([1.0 if p[0] == r else 0.0 for p in pairs]); ub.append(1)
    for j in uncertain:
        rows.append([1.0 if p[1] == j else 0.0 for p in pairs]); ub.append(1)
    rows.append([1.0]*len(pairs)); ub.append(budget)
    res = milp(-w, constraints=LinearConstraint(np.array(rows), -np.inf, np.array(ub, float)),
               integrality=np.ones(len(pairs)), bounds=Bounds(0, 1))
    return round(-res.fun)


def ranges(seed=11, trials=400):
    rng = random.Random(seed)
    narrow = dict(instances=0, schedules=0, additive_mismatch=0, assignment_mismatch=0)
    wide = dict(instances=0, schedules=0, additive_mismatch=0, instances_with_mismatch=0,
                pairs=0, complements=0, substitutes=0, instances_with_complements=0)
    for trial in range(trials):
        h, lag, delay = rng.randint(7, 9), rng.randint(1, 3), rng.randint(1, 2)
        lead, budget = lag+delay+rng.randint(-1, 2), rng.randint(1, 3)
        is_narrow = trial % 2 == 0
        lo, hi = [], []
        for _ in range(h):
            l = rng.randint(2, 4) if is_narrow else rng.randint(0, 2)
            w = rng.choice([0, 1]) if is_narrow else rng.choice([0, 1, 2, 3])
            lo.append(l); hi.append(l+w)
        uncertain = [x for x in range(h) if hi[x] > lo[x]]
        if not uncertain or len(uncertain) > 6:
            continue
        last = h-1-lag
        base = excess(lo, hi, lag, [x+1 for x in range(h)], lo, last)
        rec = narrow if is_narrow else wide
        rec['instances'] += 1
        best, bad = None, 0
        for combo in schedules(lead, delay, budget, uncertain):
            value = base-excess(lo, hi, lag, known_of(h, combo, delay), lo, last)
            additive = sum(gain(lo, hi, lag, delay, last, r, j) for r, j in combo)
            rec['schedules'] += 1
            bad += value != additive
            best = value if best is None else max(best, value)
        rec['additive_mismatch'] += bad
        if is_narrow:
            narrow['assignment_mismatch'] += best != assignment(lo, hi, lag, lead, delay, budget,
                                                                uncertain, last)
        else:
            wide['instances_with_mismatch'] += bad > 0
            single = {}
            comp = 0
            for combo in schedules(lead, delay, budget, uncertain):
                if len(combo) == 1:
                    single[combo[0]] = base-excess(lo, hi, lag, known_of(h, combo, delay), lo, last)
            for combo in schedules(lead, delay, budget, uncertain):
                if len(combo) != 2:
                    continue
                v = base-excess(lo, hi, lag, known_of(h, combo, delay), lo, last)
                s = single[combo[0]]+single[combo[1]]
                wide['pairs'] += 1
                wide['complements'] += v > s
                wide['substitutes'] += v < s
                comp += v > s
            wide['instances_with_complements'] += comp > 0
    return dict(narrow=narrow, wide=wide)


CAL = [[0, 0, 0, 0, 0, 2, 0], [0, 0, 0, 0, 2, 0, 0], [0, 0, 0, 1, 0, 1, 0], [0, 0, 1, 1, 0, 0, 0]]
N, LAG, DELAY, LEAD, Q = 2, 1, 1, 3, 2


def example():
    p = prepare(CAL, N, (2,)*7, LAG)
    h, bounds, refs, paths = p['h'], p['bounds'], p['refs'], p['paths']
    cals = range(len(paths))

    def run(known_slots):
        worst = 0
        for s in cals:
            u, total = 0, 0
            for t in range(h):
                cls = [q for q in cals if all(paths[q][x] == paths[s][x] for x in range(t))
                       and all(paths[q][x] == paths[s][x] for x in known_slots(t))]
                u = max(u, max(bounds[q][t] for q in cls))
                total += u-refs[s][t]
            worst = max(worst, total)
        return worst

    none = run(lambda t: [])
    full = run(lambda t: range(h))
    pairs = [(r, j) for j in range(h) for r in range(max(0, j-LEAD), j-DELAY+1)]
    fixed = none
    for k in range(1, Q+1):
        for combo in combinations(pairs, k):
            if len({r for r, _ in combo}) < k or len({j for _, j in combo}) < k:
                continue
            fixed = min(fixed, run(lambda t, c=combo: [j for r, j in c if r+DELAY <= t]))
    single = min(run(lambda t, r=r, j=j: [j] if r+DELAY <= t else []) for r, j in pairs)
    adaptive = BudgetedReports(p, LEAD, DELAY, 1, 0, total_requests=Q).solve()['value']
    return dict(none=none, best_single=single, best_fixed=fixed, adaptive=adaptive, full=full,
                adaptive_share=(none-adaptive)/(none-full), fixed_share=(none-fixed)/(none-full))


def main():
    out = dict(ranges=ranges(), example=example())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'structure_check.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
