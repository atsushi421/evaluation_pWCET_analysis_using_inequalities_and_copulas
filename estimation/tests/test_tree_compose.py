"""A 3-part node is composed by MC on the whole probability grid, not only the tail."""
import numpy as np
from scipy import stats

from estimation import tree


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
