"""Loop rule avg: a loop that always runs its static bound gives exactly the bound on the measured
loop total, and with fewer iterations the bound never falls below that total (T = N * A <= N_max * A)."""
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
    # the per-instance rule (every iteration as slow as the per-iteration tail) is larger still here
    inst = loop_bound(b, "inst")
    assert all(inst[p] >= got[p] for p in tree.P_GRID_FULL if p <= 0.1)
