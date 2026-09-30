"""Loop rules: avg gives exactly the bound on the measured loop total for a loop that always runs its static
bound and never falls below that total otherwise (T = N * A <= N_max * A); max never falls below avg
(A <= M, the per-run slowest iteration)."""
import numpy as np

from estimation import tree
from estimation.data import Bench, UnitData
from ipoint_schema import Schema, Unit

BOUND, RUNS = 4, 2000


def loop_bench(counts: np.ndarray, seed: int = 0) -> Bench:
    """One loop f.L1 with static bound 4 whose body runs counts[r] times in run r."""
    units = [Unit("f", "function", None, 0, instrumented=True, children=["f.L1"]),
             Unit("f.L1", "loop", "f", 1, instrumented=True, children=["f.L1.body"], bound=BOUND),
             Unit("f.L1.body", "loop_body", "f.L1", 2, instrumented=True)]
    b = Bench.__new__(Bench)
    b.bench, b.schema = "synthetic", Schema("f.c", "", [], {}, "f", 0, units)
    b.by_uid, b.tick_ns = b.schema.by_uid(), 1.0
    runs = np.repeat(np.arange(RUNS), counts)
    body = np.random.default_rng(seed).lognormal(3.0, 0.5, size=len(runs))
    totals = np.bincount(runs, weights=body, minlength=RUNS)
    b.e2e_all = totals + 10.0
    b.smi_runs = np.empty(0, dtype=np.uint64)
    b._clean_e2e_mask = np.ones(RUNS, dtype=bool)
    b.units = {"f": UnitData(b.e2e_all, np.arange(RUNS)),
               "f.L1": UnitData(totals, np.arange(RUNS)),
               "f.L1.body": UnitData(body, runs)}
    return b


def quantile_leaf(samples, uid):
    """Empirical quantiles: scale-equivariant, so N_max * A and T can be compared exactly."""
    return tree.Marginal({p: float(np.quantile(samples, 1 - p, method="higher")) for p in tree.P_GRID_FULL})


def loop_bound(b: Bench, rule: str) -> dict:
    return tree.node_marginal(b, "f.L1", "CHB-IND", "indep", 0, RUNS, tree.P_GRID_FULL, quantile_leaf,
                              10_000, {}, rule).pwcet


def test_constant_count_loop_gives_the_bound_on_the_measured_total():
    b = loop_bench(np.full(RUNS, BOUND))
    got = loop_bound(b, "avg")
    want = quantile_leaf(b.per_run_totals("f.L1.body", 0, RUNS), "f.L1").pwcet
    for p in tree.P_GRID_FULL:
        assert abs(got[p] / want[p] - 1) < 1e-12, (p, got[p], want[p])


def test_variable_count_loop_never_falls_below_the_measured_total():
    counts = np.random.default_rng(1).integers(1, BOUND + 1, size=RUNS)
    b = loop_bench(counts)
    got = loop_bound(b, "avg")
    totals = quantile_leaf(b.per_run_totals("f.L1.body", 0, RUNS), "f.L1").pwcet
    assert all(got[p] >= totals[p] for p in tree.P_GRID_FULL)
    slowest = loop_bound(b, "max")
    assert all(slowest[p] >= got[p] for p in tree.P_GRID_FULL)


def test_function_called_twice_per_run_gives_the_bound_on_its_run_total():
    """Two calls per run enter as a loop over the calls: with a rare slow call, twice the per-call quantile
    falls below the quantile of the run total, whereas the loop rule gives that quantile exactly."""
    g = np.random.default_rng(2)
    calls = np.where(g.random(2 * RUNS) < 0.004, 50.0, 1.0) + g.random(2 * RUNS)
    runs = np.repeat(np.arange(RUNS), 2)
    totals = np.bincount(runs, weights=calls, minlength=RUNS)
    units = [Unit("f", "function", None, 0, instrumented=True, children=["g"]),
             Unit("g", "function", "f", 1, instrumented=True)]
    b = Bench.__new__(Bench)
    b.bench, b.schema = "synthetic", Schema("f.c", "", [], {}, "f", 0, units)
    b.by_uid, b.tick_ns = b.schema.by_uid(), 1.0
    b.e2e_all, b.smi_runs = totals + 10.0, np.empty(0, dtype=np.uint64)
    b._clean_e2e_mask = np.ones(RUNS, dtype=bool)
    b.units = {"f": UnitData(b.e2e_all, np.arange(RUNS)), "g": UnitData(calls, runs)}
    got = tree.node_marginal(b, "f", "CHB-IND", "indep", 0, RUNS, tree.P_GRID_FULL, quantile_leaf,
                             10_000, {}, "avg").pwcet
    want = quantile_leaf(totals, "g").pwcet
    assert 2 * quantile_leaf(calls, "g").pwcet[0.005] < want[0.005]
    for p in tree.P_GRID_FULL:
        assert abs(got[p] / want[p] - 1) < 1e-12, (p, got[p], want[p])


def test_single_unit_program_reports_a_monotone_curve(monkeypatch):
    """A program of one unit reports its leaf through the monotone curve of the composition: the value at the
    largest RESTK test probability is kept, and a dip below it is lifted to the running maximum."""
    b = Bench.__new__(Bench)
    b.bench, b.schema = "synthetic", Schema("f.c", "", [], {}, "f", 0, [Unit("f", "function", None, 0, instrumented=True)])
    b.by_uid, b.tick_ns = b.schema.by_uid(), 1.0
    b.e2e_all, b.smi_runs = np.arange(1.0, RUNS + 1), np.empty(0, dtype=np.uint64)
    b._clean_e2e_mask, b.n_traced = np.ones(RUNS, dtype=bool), RUNS
    b.units = {"f": UnitData(b.e2e_all, np.arange(RUNS))}
    dip = {p: (5.0 if p == 1e-5 else 10.0 / p ** 0.1) for p in tree.P_GRID_FULL}       # 1e-5 below 1e-4
    monkeypatch.setattr(tree, "make_leaf", lambda *a: lambda samples, uid: tree.Marginal(dict(dip)))
    got, _ = tree.decomposed_estimate(b, "CHB-IND", 0, window_size=RUNS)
    assert got[1e-4] == dip[1e-4] and got[1e-5] >= got[1e-4]
    ps = sorted(got, reverse=True)
    assert all(got[a] <= got[b] for a, b in zip(ps, ps[1:]))
