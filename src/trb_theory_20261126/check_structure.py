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


def residual_widths(lo, hi, combo, delay, gamma):
    """Width left after each answer, in the worst case for an error of at most gamma."""
    w = [b-a for a, b in zip(lo, hi)]
    for _, j in combo:
        w[j] = min(w[j], 2*gamma)
    return w


def inexact_excess(lo, hi, lag, combo, delay, gamma, c, y, last):
    """Post-release excess when answers y_j satisfy |y_j - c_j| <= gamma."""
    arrive = {j: r+delay for r, j in combo}
    released, total = None, 0
    for t in range(last+1):
        a = 0
        for x in range(t+lag+1):
            if x+1 <= t:
                a += c[x]
            elif x in arrive and arrive[x] <= t:
                a += min(hi[x], y[x]+gamma)
            else:
                a += hi[x]
        released = a if released is None else max(released, a)
        total += released-sum(c[:t+lag+1])
    return total


def formula(lo, hi, lag, combo, delay, gamma, last):
    """Equation for the worst-case excess with residual widths after answers."""
    arrive = {j: r+delay for r, j in combo}
    res = residual_widths(lo, hi, combo, delay, gamma)
    total = 0
    for t in range(last+1):
        best = None
        for tau in range(t+1):
            w = sum((res[x] if x in arrive and arrive[x] <= tau else hi[x]-lo[x])
                    for x in range(tau, tau+lag+1))
            v = w-sum(lo[x] for x in range(tau+lag+1, t+lag+1))
            best = v if best is None else max(best, v)
        total += best
    return total


def inexact(seed=5, trials=250):
    """Worst case over counts and answers equals the residual-width equation."""
    from itertools import product
    rng = random.Random(seed)
    rec = dict(instances=0, schedules=0, mismatch=0, worst_not_lowest=0, single_value_checks=0,
               single_value_mismatch=0)
    for _ in range(trials):
        h, lag, delay, gamma = rng.randint(5, 6), rng.randint(1, 2), 1, rng.randint(0, 1)
        narrow = rng.random() < 0.5
        lo = [rng.randint(3, 4) if narrow else rng.randint(0, 1) for _ in range(h)]
        hi = [a+rng.choice([0, 1, 2] if not narrow else [0, 1]) for a in lo]
        uncertain = [x for x in range(h) if hi[x] > lo[x]]
        if not uncertain or len(uncertain) > 4:
            continue
        last = h-1-lag
        rec['instances'] += 1
        for combo in schedules(lag+delay, delay, 2, uncertain):
            worst, at_lowest = None, None
            for c in product(*[range(lo[x], hi[x]+1) for x in range(h)]):
                ys = [range(max(0, c[x]-gamma), c[x]+gamma+1) if x in dict((j, r) for r, j in combo)
                      else [c[x]] for x in range(h)]
                for y in product(*ys):
                    v = inexact_excess(lo, hi, lag, combo, delay, gamma, c, y, last)
                    worst = v if worst is None else max(worst, v)
                    if list(c) == lo:
                        at_lowest = v if at_lowest is None else max(at_lowest, v)
            rec['schedules'] += 1
            rec['mismatch'] += worst != formula(lo, hi, lag, combo, delay, gamma, last)
            rec['worst_not_lowest'] += worst != at_lowest
            if narrow and len(combo) == 1 and 2*max(b-a for a, b in zip(lo, hi)) <= min(lo):
                r, j = combo[0]
                none = formula(lo, hi, lag, (), delay, gamma, last)
                pred = max(0, hi[j]-lo[j]-2*gamma)*effective(j, r+delay, lag, last)
                rec['single_value_checks'] += 1
                rec['single_value_mismatch'] += none-worst != pred
    return rec


def worst_case(lo, hi, lag, arrive, gamma, last):
    """Worst-case excess by enumeration; arrive maps interval -> answer decision,
    gamma maps interval -> accuracy bound of its answer."""
    from itertools import product
    worst = None
    for c in product(*[range(lo[x], hi[x]+1) for x in range(len(lo))]):
        ys = [range(max(0, c[x]-gamma[x]), c[x]+gamma[x]+1) if x in arrive else [c[x]]
              for x in range(len(lo))]
        for y in product(*ys):
            released, total = None, 0
            for t in range(last+1):
                a = 0
                for x in range(t+lag+1):
                    if x+1 <= t:
                        a += c[x]
                    elif x in arrive and arrive[x] <= t:
                        a += min(hi[x], y[x]+gamma[x])
                    else:
                        a += hi[x]
                released = a if released is None else max(released, a)
                total += released-sum(c[:t+lag+1])
            worst = total if worst is None else max(worst, total)
    return worst


def timing(seed=23, trials=400):
    """Corollary 1(a) for general ranges: value of one answer versus arrival and accuracy."""
    rng = random.Random(seed)
    rec = dict(instances=0, values=0, early_differs=0, later_gains=0, after_positive=0,
               accuracy_gains=0, covered_positive=0)
    for _ in range(trials):
        h, lag = rng.randint(5, 6), rng.randint(1, 2)
        lo = [rng.randint(0, 2) for _ in range(h)]
        hi = [a+rng.choice([0, 1, 2, 3]) for a in lo]
        last = h-1-lag
        cand = [x for x in range(lag, last+1) if hi[x] > lo[x]]
        if not cand or sum(hi[x] > lo[x] for x in range(h)) > 4:
            continue
        x = rng.choice(cand)
        others = {}
        rest = [j for j in range(h) if j != x and hi[j] > lo[j]]
        if rest and rng.random() < 0.6:
            j = rng.choice(rest)
            others[j] = rng.randint(max(0, j-lag-1), j)
        g0 = {j: 0 for j in others}
        base = worst_case(lo, hi, lag, others, g0, last)
        rec['instances'] += 1
        w = hi[x]-lo[x]
        table = {}
        for gamma in (0, 1, 2):
            for a in range(max(0, x-lag-2), x+2):
                arr = dict(others); arr[x] = a
                gm = dict(g0); gm[x] = gamma
                table[gamma, a] = base-worst_case(lo, hi, lag, arr, gm, last)
                rec['values'] += 1
        for gamma in (0, 1, 2):
            arrivals = sorted(a for g, a in table if g == gamma)
            early = [table[gamma, a] for a in arrivals if a <= x-lag]
            rec['early_differs'] += len(set(early)) > 1
            for a, b in zip(arrivals, arrivals[1:]):
                rec['later_gains'] += table[gamma, b] > table[gamma, a]
            rec['after_positive'] += sum(table[gamma, a] != 0 for a in arrivals if a > x)
            if 2*gamma >= w:
                rec['covered_positive'] += sum(table[gamma, a] != 0 for a in arrivals)
        for a in {a for _, a in table}:
            rec['accuracy_gains'] += (table[1, a] > table[0, a]) + (table[2, a] > table[1, a])
    return rec


def returns(seed=17, trials=600):
    """Concave returns under narrow ranges; increasing returns under bursty ranges."""
    rng = random.Random(seed)
    narrow = dict(instances=0, concavity_violations=0)
    bursty = dict(instances=0, increasing_marginal=0, second_exceeds_first=0)
    for trial in range(trials):
        h, lag, delay = rng.randint(7, 9), rng.randint(1, 3), 1
        lead = lag+delay+rng.randint(0, 2)
        if trial % 2 == 0:
            lo = [rng.randint(4, 6) for _ in range(h)]
            hi = [a+rng.choice([0, 1, 2]) for a in lo]
        else:
            lo = [0]*h
            hi = [rng.choice([0, 0, 1, 2, 3]) for _ in range(h)]
        uncertain = [x for x in range(h) if hi[x] > lo[x]]
        if len(uncertain) < 3 or len(uncertain) > 6:
            continue
        last = h-1-lag
        if trial % 2 == 0:
            if 2*max(b-a for a, b in zip(lo, hi)) > min(lo):
                continue
            v = [assignment(lo, hi, lag, lead, delay, q, uncertain, last) if q else 0
                 for q in range(0, 5)]
            narrow['instances'] += 1
            narrow['concavity_violations'] += any(v[q+1]-v[q] > v[q]-v[q-1] for q in range(1, 4))
        else:
            base = excess(lo, hi, lag, [x+1 for x in range(h)], lo, last)
            best = [0]*4
            for combo in schedules(lead, delay, 3, uncertain):
                k = len(combo)
                best[k] = max(best[k], base-excess(lo, hi, lag, known_of(h, combo, delay), lo, last))
            for k in range(1, 4):
                best[k] = max(best[k], best[k-1])
            bursty['instances'] += 1
            bursty['increasing_marginal'] += any(best[q+1]-best[q] > best[q]-best[q-1]
                                                 for q in range(1, 3))
            bursty['second_exceeds_first'] += best[2]-best[1] > best[1]
    return dict(narrow=narrow, bursty=bursty)


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
    out = dict(ranges=ranges(), example=example(), inexact=inexact(), returns=returns(),
               timing=timing())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'structure_check.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
