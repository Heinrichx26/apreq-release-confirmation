"""Exhaustive check of the interval-range theorem on small instances.

For slot-wise service ranges, exact answers, unsaturated runway queue and a
release limit that never binds, the theorem states:
  (a) the lowest count in every slot is a worst case for every fixed schedule;
  (b) the best adaptive policy has the same worst-case loss as the best fixed
      schedule (no value of adaptivity);
  (c) that loss equals sum_t max_{tau<=t}[A_tau] - A*_t evaluated at the
      lowest counts.
Loss is post-release time in excess of the full-information release.
"""
from functools import lru_cache
from itertools import combinations, product
import json, random
from pathlib import Path

OUT = Path(__file__).resolve().parents[2]/'results/trb_theory_20261126'


def loss_fixed(lo, hi, lag, known, c):
    h = len(lo)
    released, total = None, 0
    for tau in range(h):
        top = min(h-1, tau+lag)
        a = sum(c[x] if known[x] <= tau else hi[x] for x in range(top+1))
        released = a if released is None else max(released, a)
        total += released-sum(c[:top+1])
    return total


def fixed_schedules(h, lead, delay, budget, uncertain):
    """All fixed schedules: at most one request per decision, each slot once."""
    pairs = [(r, j) for j in uncertain for r in range(max(0, j-lead), j-delay+1)
             if r+delay <= j]
    out = [()]
    for k in range(1, budget+1):
        for combo in combinations(pairs, k):
            rs = [r for r, _ in combo]
            js = [j for _, j in combo]
            if len(set(rs)) == k and len(set(js)) == k:
                out.append(combo)
    return out


def known_of(h, combo, delay):
    known = [x+1 for x in range(h)]
    for r, j in combo:
        known[j] = min(known[j], r+delay)
    return known


def adaptive(lo, hi, lag, lead, delay, budget):
    h = len(lo)

    @lru_cache(None)
    def value(tau, revealed, pending, released, used):
        # revealed: tuple of values or -1
        if tau == h:
            return -sum(sum(revealed[:min(h-1, t+lag)+1]) for t in range(h))
        rev = list(revealed)
        a = sum(rev[x] if rev[x] >= 0 else hi[x] for x in range(min(h-1, tau+lag)+1))
        u = a if released is None else max(released, a)
        options = [()]
        cands = [j for j in range(tau+delay, min(h, tau+lead+1))
                 if rev[j] < 0 and lo[j] < hi[j] and all(j != q for _, q in pending)]
        if used < budget:
            options += [(j,) for j in cands]
        best = None
        for batch in options:
            pend = pending+tuple((tau+delay, j) for j in batch)
            due = [j for d, j in pend if d == tau+1]
            rest = tuple((d, j) for d, j in pend if d > tau+1)
            reveal = [j for j in set(due+[tau]) if rev[j] < 0]
            worst = None
            for vals in product(*[range(lo[j], hi[j]+1) for j in reveal]):
                nxt = list(rev)
                for j, v in zip(reveal, vals):
                    nxt[j] = v
                v = u+value(tau+1, tuple(nxt), rest, u, used+len(batch))
                worst = v if worst is None else max(worst, v)
            best = worst if best is None else min(best, worst)
        return best

    return value(0, tuple(-1 if lo[x] < hi[x] else lo[x] for x in range(h)), (), None, 0)


def main(trials=300, seed=7):
    rng = random.Random(seed)
    rows, failures = [], 0
    for trial in range(trials):
        h = rng.randint(6, 8)
        lag = rng.randint(1, 3)
        delay = rng.randint(1, 2)
        lead = lag+delay+rng.randint(-1, 2)
        budget = rng.randint(1, 2)
        lo, hi = [], []
        for x in range(h):
            l = rng.randint(0, 2)
            w = rng.choice([0, 0, 1, 2])
            lo.append(l)
            hi.append(l+w)
        uncertain = [x for x in range(h) if hi[x] > lo[x]]
        if len(uncertain) > 5:
            continue
        schedules = fixed_schedules(h, lead, delay, budget, uncertain)
        grid = list(product(*[range(lo[x], hi[x]+1) for x in range(h)]))
        fixed_best, worst_is_low = None, True
        for combo in schedules:
            known = known_of(h, combo, delay)
            at_low = loss_fixed(lo, hi, lag, known, lo)
            sup = max(loss_fixed(lo, hi, lag, known, c) for c in grid)
            worst_is_low &= sup == at_low
            fixed_best = at_low if fixed_best is None else min(fixed_best, at_low)
        adapt = adaptive(lo, hi, lag, lead, delay, budget)
        ok = worst_is_low and adapt == fixed_best
        failures += not ok
        rows.append(dict(h=h, lag=lag, delay=delay, lead=lead, budget=budget, lo=lo, hi=hi,
                         fixed=fixed_best, adaptive=adapt, worst_is_low=worst_is_low, ok=ok))
    result = dict(instances=len(rows), failures=failures, rows=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'interval_theorem_check.json').write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(json.dumps(dict(instances=len(rows), failures=failures)))


if __name__ == '__main__':
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
