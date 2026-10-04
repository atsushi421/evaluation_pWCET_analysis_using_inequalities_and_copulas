"""A 3-part node is composed by MC on the whole probability grid, not only the tail. A node that runs in only
some runs is coupled over those runs."""
import numpy as np
from scipy import stats

from estimation import tree
from estimation.data import Bench, UnitData
from ipoint_schema import Schema, Unit


def test_node_that_runs_in_some_runs_is_coupled_over_those_runs():
    """g (self time and callee h, independent) runs in about half of the runs; the zeros of the other runs would
    make its parts look strongly dependent."""
    n = 2000
    rng = np.random.default_rng(0)
    on = np.flatnonzero(rng.random(n) < 0.5)
    g_self, h = rng.lognormal(3.0, 0.5, len(on)), rng.lognormal(3.0, 0.5, len(on))
    units = [Unit("f", "function", None, 0, instrumented=True, children=["g"]),
             Unit("g", "function", "f", 1, instrumented=True, children=["h"]),
             Unit("h", "function", "g", 2, instrumented=True)]
    b = Bench.__new__(Bench)
    b.bench, b.schema = "synthetic", Schema("f.c", "", [], {}, "f", 0, units)
    b.by_uid, b.tick_ns = b.schema.by_uid(), 1.0
    b.e2e_all, b.smi_runs, b._clean_e2e_mask = np.ones(n), np.empty(0, dtype=np.uint64), np.ones(n, dtype=bool)
    b.units = {"f": UnitData(b.e2e_all, np.arange(n)), "g": UnitData(g_self + h, on, g_self), "h": UnitData(h, on)}
    leaf = lambda s, uid: tree.Marginal({p: float(np.quantile(s, 1 - p, method="higher")) for p in tree.P_GRID_FULL})
    meta = {}
    tree.node_marginal(b, "g", "CHB-COP", "cop", 0, n, tree.P_GRID_FULL, leaf, 10_000, meta)
    assert abs(meta["g"]["tau"]) < 0.1, meta["g"]


def test_three_part_indep_node_covers_body_and_tail():
    parts = [tree.Marginal({p: float(stats.expon.isf(p)) for p in tree.P_GRID_FULL}) for _ in range(3)]
    X = np.random.default_rng(0).exponential(size=(1000, 3))
    q, info = tree.compose_parts(parts, X, "indep", tree.P_GRID_FULL, n_mc=2_000_000, seed=1)
    ps = sorted(q, reverse=True)
    assert all(q[a] <= q[b] for a, b in zip(ps, ps[1:]))            # monotone in p
    icdf = parts[0].icdf()                                          # flat below the median by design
    u = np.random.default_rng(2).uniform(size=(4_000_000, 3))
    ref = np.sort(icdf(u).sum(axis=1))
    for p in (0.5, 0.1, 1e-2, 1e-3, 1e-4):
        want = ref[int(np.ceil((1 - p) * len(ref))) - 1]
        assert abs(q[p] / want - 1) < 0.03, (p, q[p], want)
    assert "body" in info["composition"]
