"""A leaf whose bound is +inf from grid point p_inf on carries mass p_inf at +inf (step convention),
a composition is +inf exactly where that mass reaches p (the onset does not move up by a grid step
per composition level), and the exact bivariate composition terminates."""
import numpy as np
import pyvinecopulib as pv
from scipy import stats

from copula import compose as cc
from estimation import tree


def test_inf_tail_composes_finitely_above_its_mass():
    fin = {p: float(stats.expon.isf(p)) for p in tree.P_GRID_FULL}
    inf_below = {p: (v if p >= 1e-6 else np.inf) for p, v in fin.items()}    # +inf from 5e-7 on
    a, b = tree.Marginal(fin), tree.Marginal(inf_below)
    icdf, cdf = b.icdf(), b.cdf()
    assert np.isfinite(icdf(np.array([1 - 6e-7]))[0]) and np.isinf(icdf(np.array([1 - 5e-7]))[0])
    assert cdf(np.array([1e9]))[0] == 1 - 5e-7                # mass 5e-7 above every finite x
    q = cc.exact_sum_quantiles(pv.Bicop(), a.cdf(), a.icdf(), cdf, icdf, tree.P_GRID_FULL)
    assert np.isfinite(q[1e-6]) and np.isinf(q[5e-7]) and np.isinf(q[1e-10])
    assert q[1e-6] >= stats.expon.isf(1e-6)                   # the finite part is still bounded
    # composing again keeps the onset at 5e-7 (no compounding)
    c = tree.Marginal(q)
    q2 = cc.exact_sum_quantiles(pv.Bicop(), a.cdf(), a.icdf(), c.cdf(), c.icdf(), tree.P_GRID_FULL)
    assert np.isfinite(q2[1e-6]) and np.isinf(q2[5e-7])
    q3, info = tree.compose_parts([a, b, a], np.random.default_rng(0).exponential(size=(500, 3)),
                                  "indep", tree.P_GRID_FULL, n_mc=2_000_000, seed=1)
    assert np.isfinite(q3[1e-4]) and np.isinf(q3[1e-10])


def test_non_monotone_curve_is_made_conservative_and_monotone():
    """A dip at a smaller p (v(5e-7) < v(1e-6)) must not put mass 1e-6 above the curve's maximum."""
    fin = {p: float(stats.expon.isf(p)) for p in tree.P_GRID_FULL}
    dip = dict(fin); dip[1e-6] = fin[1e-6] * 1.5                    # bound at 1e-6 above the ones below
    m = tree.Marginal(dip)
    icdf, cdf = m.icdf(), m.cdf()
    u = np.array([1 - 1e-6, 1 - 5e-7, 1 - 1e-8])
    assert np.all(np.diff(icdf(u)) >= 0) and icdf(u)[0] == dip[1e-6]     # monotone, never below per-p
    assert cdf(np.array([dip[1e-6] + 1]))[0] >= 1 - 5e-7                  # mass above the max is not 1e-6
    a = tree.Marginal(fin)
    q = cc.exact_sum_quantiles(pv.Bicop(), a.cdf(), a.icdf(), cdf, icdf, tree.P_GRID_TAIL)
    assert np.isfinite(q[1e-6]) and q[1e-6] >= dip[1e-6]


def test_body_bound_does_not_leak_into_the_tail():
    """Above P_TOP the curve is the running minimum from P_TOP (a k = 1 Markov bound at p = 1e-3 is
    replaced by the validated bound at 1e-4); below P_TOP the running maximum from P_TOP."""
    fin = {p: float(stats.expon.isf(p)) for p in tree.P_GRID_FULL}
    bad = dict(fin); bad[1e-3] = 100 * fin[1e-4]; bad[2e-3] = 50 * fin[1e-4]; bad[5e-7] = 0.5 * fin[1e-6]
    alphas, v = cc.monotone_curve(bad)
    c = dict(zip(alphas, v))
    assert all(v[i] >= v[i + 1] for i in range(len(v) - 1))                # non-increasing in p
    assert c[1e-3] == c[2e-3] == fin[5e-4] and c[1e-4] == fin[1e-4]        # body: min over [P_TOP, p]
    assert c[5e-4] == fin[5e-4] and c[1e-2] == fin[1e-2]                    # untouched where already monotone
    assert c[1e-5] == fin[1e-5] and c[1e-6] == fin[1e-6]                    # tail: max, no leak from 1e-3
    assert c[5e-7] == fin[1e-6] and c[1e-10] == fin[1e-10]                  # dip raised, rest kept
    assert dict(tree.monotone_pwcet(bad)) == c
