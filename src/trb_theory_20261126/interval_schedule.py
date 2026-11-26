"""Confirmation schedules derived from interval service ranges.

The interval model replaces the finite set of service calendars by the
slot-wise range [l_x, h_x]. Under that model the lowest count in every slot
is a worst case for every request policy, and the post-release excess is

    sum_t ( max_{tau<=t} A_tau - A*_t ),

where A_tau is the highest possible cumulative service through tau+travel,
using l for slots known at tau and h otherwise. The schedule minimising this
expression is evaluated in the finite-calendar model with delayed answers and
a shared error allowance.
"""
from __future__ import annotations

from itertools import combinations
from pathlib import Path
from time import perf_counter
import argparse, json, os, sys
from concurrent.futures import ProcessPoolExecutor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/trb_error_20261030'))
sys.path.insert(0, str(ROOT/'src/trb_external_error_20261030'))
from robust_reports import RobustReports, SearchLimit, prepare  # noqa: E402
from budgeted_reports import BudgetedReports  # noqa: E402
from rollout_check import RolloutReports  # noqa: E402
from independent_replay import stress  # noqa: E402

DATA = ROOT/'data/trb_external_error_20261030'
OUT = ROOT/'results/trb_theory_20261126'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def save(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2)+'\n', encoding='utf-8')


def interval_loss(lo, hi, lag, start, known):
    """Worst-case post-release excess in aircraft-slots from decision `start`."""
    h = len(lo)
    released, total = None, 0
    for tau in range(start, h):
        top = min(h-1, tau+lag)
        a = sum(lo[x] if known[x] <= tau else hi[x] for x in range(top+1))
        a_star = sum(lo[:top+1])
        released = a if released is None else max(released, a)
        total += released-a_star
    return total


def plan(lo, hi, lag, lead, delay, start, budget, known):
    """Request set of size <= budget minimising the interval-model excess.

    Each requested slot is sent at its earliest permitted decision that is
    free of other requests (one request per decision).
    """
    h = len(lo)
    candidates = [j for j in range(start+delay, h)
                  if hi[j] > lo[j] and known[j] > max(start, j-lead)+delay]
    best = (interval_loss(lo, hi, lag, start, known), 0, ())
    top = min(budget, len(candidates))
    for k in range(top, 0, -1):
        if best[1]:
            break
        for chosen in combinations(candidates, k):
            used, trial, ok, sends = set(), list(known), True, []
            for j in sorted(chosen):
                r = max(start, j-lead)
                while r in used:
                    r += 1
                if r+delay > j or r+delay >= trial[j]:
                    ok = False
                    break
                used.add(r)
                sends.append((r, j))
                trial[j] = r+delay
            if not ok:
                continue
            value = interval_loss(lo, hi, lag, start, trial)
            if best[1] == 0 or value < best[0]:
                best = (value, k, tuple(sends))
    return best


class IntervalPolicy(BudgetedReports):
    """Send the requests that the interval model schedules for the current decision."""

    def __init__(self, *a, replan=True, **kw):
        super().__init__(*a, **kw)
        self.replan = replan
        self.static = None

    def schedule_for(self, t, spent, pending, queried):
        members = self.members(spent)
        lo = [min(self.paths[s][x] for s in members) for x in range(self.h)]
        hi = [max(self.paths[s][x] for s in members) for x in range(self.h)]
        known = [x+1 for x in range(self.h)]
        for d, j in pending:
            known[j] = min(known[j], d)
        for j in range(self.h):
            if queried >> j & 1:
                known[j] = min(known[j], t)
        return plan(lo, hi, self.p['lag'], self.lead, self.delay, t,
                    self.total_requests-(queried >> self.h), known)

    def value(self, t, e, pending, queried, u):
        if t == self.h:
            return 0
        if perf_counter()-self.started > self.seconds_limit:
            raise SearchLimit('interval policy time allowance reached')
        state = (t, e, pending, queried, u)
        z = self.release(t, e, u)
        if z == self.n:
            self.choice[state] = ()
            return max(sum(self.n-self.p['refs'][s][k] for k in range(t, self.h))
                       for s in self.members(e))
        if self.replan:
            sends = self.schedule_for(t, e, pending, queried)[2]
        else:
            if self.static is None:
                self.static = self.schedule_for(t, e, pending, queried)[2]
            sends = self.static
        allowed = set(j for batch in super().batches(t, e, pending, queried) for j in batch)
        batch = tuple(sorted(j for r, j in sends if r == t and j in allowed))[:self.limit]
        if (queried >> self.h)+len(batch) > self.total_requests:
            batch = ()
        self.choice[state] = batch
        return max(z-r+self.value(t+1, en, pn, an, z)
                   for _, _, en, pn, an, r in self.transitions(t, e, pending, queried, batch))


class IndexPolicy(BudgetedReports):
    """Request the available slot with the largest range width times effective decisions."""

    def value(self, t, e, pending, queried, u):
        if t == self.h:
            return 0
        if perf_counter()-self.started > self.seconds_limit:
            raise SearchLimit('index policy time allowance reached')
        state = (t, e, pending, queried, u)
        z = self.release(t, e, u)
        if z == self.n:
            self.choice[state] = ()
            return max(sum(self.n-self.p['refs'][s][k] for k in range(t, self.h))
                       for s in self.members(e))
        members = self.members(e)
        lag = self.p['lag']
        best, batch = 0, ()
        for cand in super().batches(t, e, pending, queried):
            if len(cand) != 1:
                continue
            j = cand[0]
            width = max(self.paths[s][j] for s in members)-min(self.paths[s][j] for s in members)
            score = width*max(0, min(lag+1, j-(t+self.delay)+1))
            if score > best:
                best, batch = score, cand
        self.choice[state] = batch
        return max(z-r+self.value(t+1, en, pn, an, z)
                   for _, _, en, pn, an, r in self.transitions(t, e, pending, queried, batch))


def evaluate(model, p):
    model.solve()
    check = stress(model, p)
    assert check['calendars_with_loss'] == 0
    return (max(r['worst_postrelease'] for r in check['records']),
            max(r['worst_requests'] for r in check['records']))


def shuffled(c, job, lead, delay, budget, copies=2):
    """Exact recursion after permuting counts across dates within each slot."""
    import random
    rng = random.Random(job['case_id']+str(job['cap'])+str(delay))
    out, tries = [], 0
    while len(out) < copies and tries < 400:
        tries += 1
        cols = list(zip(*c['service']))
        cols = [rng.sample(col, len(col)) for col in cols]
        paths = [list(r) for r in zip(*cols)]
        try:
            p = prepare(paths, c['n'], (job['cap'],)*len(paths[0]), c['lag'])
        except ValueError:
            continue
        none = RobustReports(p, lead, delay, 1, 1, mode='none', seconds_limit=60)
        v_none = none.solve()['value']
        v_full = none.lower(0, (0,)*len(p['paths']), 0)
        exact = BudgetedReports(p, lead, delay, 1, 1, total_requests=budget, seconds_limit=60, state_limit=200000)
        v_exact, used = evaluate(exact, p)
        out.append(dict(none=v_none, full=v_full, exact=v_exact, budget=budget, used=used, tries=tries))
    return out


def one(job):
    c = read(ROOT/job['input_path'])
    n, lag, delay = c['n'], c['lag'], job['delay']
    p = prepare(c['service'], n, (job['cap'],)*len(c['service'][0]), lag)
    lead = lag+2
    row = dict(case_id=job['case_id'], airport=job['airport'], n=n, cap=job['cap'],
               delay=delay, lag=lag, slot_minutes=c['delta'],
               windows=len(job.get('represented_windows', [1])))
    started = perf_counter()
    try:
        none = RobustReports(p, lead, delay, 1, 1, mode='none', seconds_limit=60)
        row['none'] = none.solve()['value']
        row['full'] = none.lower(0, (0,)*len(p['paths']), 0)
        two = RolloutReports(p, lead, delay, 1, 1, depth=2, seconds_limit=60, state_limit=200000)
        row['lookahead2'], budget = evaluate(two, p)
        row['budget'] = budget
        exact = BudgetedReports(p, lead, delay, 1, 1, total_requests=budget,
                                seconds_limit=60, state_limit=200000)
        row['exact'], row['exact_requests'] = evaluate(exact, p)
        m = IndexPolicy(p, lead, delay, 1, 1, total_requests=budget, seconds_limit=300, state_limit=400000)
        row['index'], row['index_requests'] = evaluate(m, p)
        row['resolved'] = True
    except SearchLimit as exc:
        row.update(resolved=False, reason=str(exc))
    row['seconds'] = perf_counter()-started
    return row


def run(stage):
    d = read(DATA/'design.json')
    jobs = d['smoke'] if stage == 'smoke' else d['jobs']
    os.environ['OMP_NUM_THREADS'] = '1'
    workers = max(1, min(6, (os.cpu_count() or 2)-2))
    rows, start = [], perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i, r in enumerate(pool.map(one, jobs), 1):
            rows.append(r)
            print(json.dumps(dict(done=i, total=len(jobs), seconds=round(perf_counter()-start, 1),
                                  case=r['case_id'], resolved=r['resolved'])), flush=True)
    save(OUT/f'interval_{stage}.json', dict(stage=stage, rows=rows, seconds=perf_counter()-start))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['smoke', 'full'])
    run(ap.parse_args().stage)




