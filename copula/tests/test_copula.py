"""Tests for the copula subpackage (run from the repository root: .venv/bin/python -m pytest copula/tests)."""
import math

import numpy as np
import pyvinecopulib as pv
import pytest
from scipy.stats import t as student_t

from copula import families, select, vine, compose

F = pv.BicopFamily


def bicop(fam, rot, *params):
    return pv.Bicop(family=fam, rotation=rot, parameters=np.array(params, dtype=float).reshape(-1, 1))


@pytest.mark.parametrize("fam,rot,params", [
    (F.gaussian, 0, (0.7,)), (F.student, 0, (0.7, 3.0)), (F.clayton, 0, (2.0,)), (F.clayton, 180, (2.0,)),
    (F.gumbel, 0, (2.0,)), (F.gumbel, 90, (2.0,)), (F.frank, 0, (5.0,)), (F.joe, 0, (2.5,)),
    (F.bb1, 0, (0.5, 1.5)), (F.bb6, 0, (2.0, 1.5)), (F.bb7, 0, (2.0, 1.5)), (F.bb8, 0, (3.0, 0.8)),
    (F.bb8, 0, (3.0, 1.0)), (F.tawn, 0, (0.9, 0.5, 3.0)), (F.tawn, 180, (0.9, 0.5, 3.0)),
])
def test_tail_dependence_matches_cdf_diagonal(fam, rot, params):
    b = bicop(fam, rot, *params)
    lo, up = families.tail_dependence(fam, rot, b.parameters)
    # the tail concentration converges to lambda as q -> 1; the CDF loses precision beyond 1 - 1e-6
    # (BB8 with delta = 1 already at 1e-6), so accept agreement at either level
    ok = False
    for eps in (1e-4, 1e-6):
        lo_num, up_num = families.tail_concentration(b, 1.0 - eps)
        ok = ok or (abs(up - up_num) < 0.05 and abs(lo - lo_num) < 0.05)
    assert ok, (lo, up, families.tail_concentration(b, 1.0 - 1e-4), families.tail_concentration(b, 1.0 - 1e-6))


def test_student_t_cdf():
    for x in (-3.0, -0.5, 0.0, 1.2, 4.0):
        for nu in (2.5, 4.0, 10.0):
            assert families.student_t_cdf(x, nu) == pytest.approx(student_t.cdf(x, nu), abs=1e-9)


@pytest.mark.parametrize("fam,rot,params", [
    (F.clayton, 90, (2.0,)), (F.clayton, 270, (2.0,)), (F.gumbel, 180, (2.0,)),
    (F.tawn, 0, (0.6, 0.9, 3.0)), (F.tawn, 90, (0.6, 0.9, 3.0)), (F.tawn, 270, (0.3, 0.9, 2.0)),
    (F.student, 0, (-0.4, 5.0)), (F.bb1, 180, (0.5, 1.5)),
])
def test_swap_arguments(fam, rot, params):
    b = bicop(fam, rot, *params)
    s = vine.swap_arguments(b)
    u = pv.Bicop(family=F.gaussian, parameters=np.array([[0.3]])).simulate(2000, seeds=[1])
    assert np.allclose(b.pdf(u), s.pdf(np.asfortranarray(u[:, ::-1])), rtol=1e-8, atol=1e-10)


def test_swap_arguments_tll():
    u = bicop(F.tawn, 90, 0.3, 0.9, 2.0).simulate(3000, seeds=[2])
    b = pv.Bicop(family=F.tll)
    b.fit(u, controls=pv.FitControlsBicop(family_set=[F.tll]))
    s = vine.swap_arguments(b, u)
    assert s.family == F.tll
    assert abs(s.loglik(np.asfortranarray(u[:, ::-1])) - b.loglik(u)) < 0.05 * abs(b.loglik(u))


def test_select_recovers_gumbel_and_upper_tail():
    u = bicop(F.gumbel, 0, 2.0).simulate(4000, seeds=[1, 2, 3])
    cands, winners = select.select_all_criteria(u, pool="par", cv_folds=3)
    assert winners["bic"].label == "gumbel"
    assert winners["mbic"].label == "gumbel"
    for crit, w in winners.items():
        assert w.lambda_u > 0.35, (crit, w.label)
    assert winners["bic"].lambda_u == pytest.approx(2 - 2 ** 0.5, abs=0.08)
    sel = select.select(u, pool="vc15", criterion="aic")
    assert sel.label in ("gumbel", "joe", "clayton180", "student")


def test_select_independence():
    rng = np.random.default_rng(3)
    u = pv.to_pseudo_obs(rng.uniform(size=(3000, 2)))
    sel = select.select(u, pool="par", criterion="bic", indep_alpha=0.05)
    assert sel.independent_by_test and sel.bicop.family == F.indep
    sel2 = select.select(u, pool="par", criterion="bic")
    assert sel2.bicop.family == F.indep
    sel3 = select.select(u, pool="vc15", criterion="bic", indep_alpha=0.05)
    assert sel3.bicop.family == F.indep and sel3.candidates == []


def test_subset_pools():
    u = bicop(F.gumbel, 0, 1.5).simulate(1000, seeds=[7])
    cands = select.fit_candidates(u, pool="all")
    labels_vc15 = {c.label for c in select.subset(cands, "vc15")}
    assert "indep" not in labels_vc15 and "bb1" not in labels_vc15 and "gumbel" in labels_vc15
    assert {c.label for c in select.subset(cands, "par")} <= {c.label for c in cands}


def test_native_matrix_roundtrip():
    rng = np.random.default_rng(0)
    C = np.array([[1, 0.7, 0.5, 0.3], [0.7, 1, 0.6, 0.4], [0.5, 0.6, 1, 0.5], [0.3, 0.4, 0.5, 1]])
    X = rng.standard_normal((3000, 4)) @ np.linalg.cholesky(C).T
    U = pv.to_pseudo_obs(X)
    v = vine.fit_vine_native(U, pool=[F.gaussian, F.indep], criterion="bic")
    v2 = pv.Vinecop.from_structure(matrix=v.matrix, pair_copulas=v.pair_copulas)
    assert v2.loglik(U) == pytest.approx(v.loglik(U), abs=1e-6)


def test_custom_vine_matches_native_gaussian():
    rng = np.random.default_rng(1)
    C = np.array([[1, 0.7, 0.5, 0.3], [0.7, 1, 0.6, 0.4], [0.5, 0.6, 1, 0.5], [0.3, 0.4, 0.5, 1]])
    X = rng.standard_normal((4000, 4)) @ np.linalg.cholesky(C).T
    U = pv.to_pseudo_obs(X)
    fit = vine.fit_vine(U, pool=[F.gaussian, F.indep], criterion="bic")
    native = vine.fit_vine_native(U, pool=[F.gaussian, F.indep], criterion="bic")
    assert vine.edge_sets_of_fit(fit) == vine.edge_sets(native)
    assert fit.vinecop.loglik(U) == pytest.approx(native.loglik(U), rel=1e-3)
    assert fit.edge_loglik == pytest.approx(fit.vinecop.loglik(U), rel=1e-9)


def _asymmetric_vine():
    """5-dim vine with rotated and asymmetric pair copulas (exercises orientation handling)."""
    structure = pv.RVineStructure.from_order([1, 2, 3, 4, 5])
    pcs = [
        [bicop(F.clayton, 90, 2.0), bicop(F.tawn, 0, 0.4, 0.9, 3.0), bicop(F.gumbel, 180, 2.0), bicop(F.joe, 270, 2.5)],
        [bicop(F.frank, 0, 4.0), bicop(F.clayton, 0, 1.5), bicop(F.gaussian, 0, -0.5)],
        [bicop(F.bb1, 180, 0.5, 1.5), pv.Bicop()],
        [bicop(F.gumbel, 90, 1.5)],
    ]
    return pv.Vinecop.from_structure(structure=structure, pair_copulas=pcs)


@pytest.mark.parametrize("criterion", ["bic", "tcf", "hybrid"])
def test_custom_vine_asymmetric(criterion):
    truth = _asymmetric_vine()
    U = truth.simulate(3000, seeds=[11])
    fit = vine.fit_vine(U, pool="par", criterion=criterion, indep_alpha=0.05)
    assert fit.dim == 5 and fit.vinecop.dim == 5
    assert fit.edge_loglik == pytest.approx(fit.vinecop.loglik(U), rel=1e-9)
    V = fit.vinecop.simulate(20000, seeds=[3])
    for i in range(5):
        for j in range(i + 1, 5):
            tau_fit = pv.wdm(np.ascontiguousarray(V[:, i]), np.ascontiguousarray(V[:, j]), "ktau")
            tau_true = pv.wdm(np.ascontiguousarray(U[:, i]), np.ascontiguousarray(U[:, j]), "ktau")
            assert tau_fit == pytest.approx(tau_true, abs=0.08)


def test_custom_vine_bic_close_to_native_asymmetric():
    truth = _asymmetric_vine()
    U = truth.simulate(4000, seeds=[5])
    fit = vine.fit_vine(U, pool="par", criterion="bic")
    native = vine.fit_vine_native(U, pool="par", criterion="bic")
    assert vine.edge_sets_of_fit(fit)[0] == vine.edge_sets(native)[0]
    assert fit.vinecop.loglik(U) == pytest.approx(native.loglik(U), rel=0.02)


def test_compose_comonotonic_and_independent():
    rng = np.random.default_rng(0)
    x = rng.exponential(size=200_000)
    y = rng.exponential(size=200_000)
    probs = [1e-2, 1e-3]
    icdfs = [compose.icdf_from_samples(x), compose.icdf_from_samples(y)]
    como = compose.compose("comono", icdfs, probs, n_samples=400_000, chunk=100_000, seed=1)
    qx = compose.empirical_quantiles(x, probs)
    qy = compose.empirical_quantiles(y, probs)
    for p in probs:
        assert como.quantiles[p] == pytest.approx(qx[p] + qy[p], rel=0.05)
    ind = compose.compose("indep", icdfs, probs, n_samples=2_000_000, chunk=500_000, seed=2)
    # sum of two Exp(1) is Gamma(2): survival (1 + x) e^{-x}
    from scipy.stats import gamma
    for p in probs:
        assert ind.quantiles[p] == pytest.approx(gamma.ppf(1 - p, 2), rel=0.05)
    assert ind.quantiles[1e-2] < como.quantiles[1e-2]


def test_compose_with_bicop_and_pwcet_dict():
    g = bicop(F.gumbel, 0, 3.0)
    curve = {1e-1: 1.0, 1e-2: 2.0, 1e-3: 3.0, 1e-4: 4.0}
    icdf = compose.icdf_from_pwcet_dict(curve)
    res = compose.compose(g, [icdf, icdf], [1e-2, 1e-3], n_samples=300_000, chunk=100_000)
    # each unit is capped at 4.0 (its p = 1e-4 value), so the sum lies in [2, 8]
    assert 2.0 <= res.quantiles[1e-2] <= 8.0 + 1e-9
    assert res.quantiles[1e-3] >= res.quantiles[1e-2]


def test_independence_test_pvalue_uniform_under_null():
    rng = np.random.default_rng(5)
    ps = [select.independence_test(pv.to_pseudo_obs(rng.uniform(size=(500, 2))))[2] for _ in range(200)]
    assert 0.01 < np.mean(np.array(ps) < 0.05) < 0.12


def test_load_unit_matrix_aligns_runs(tmp_path):
    from copula import study_selection as st
    units = tmp_path / "units"
    units.mkdir()
    # unit a: two samples in run 0, one in runs 1 and 2; unit b: runs 0, 2, 3
    np.save(units / "a.npy", np.array([10, 5, 7, 9], dtype=np.int64))
    np.save(units / "a.run.npy", np.array([0, 0, 1, 2], dtype=np.int64))
    np.save(units / "b.npy", np.array([1, 2, 3], dtype=np.int64))
    np.save(units / "b.run.npy", np.array([0, 2, 3], dtype=np.int64))
    runs, X = st.load_unit_matrix(str(tmp_path), ["a", "b"])
    assert runs.tolist() == [0, 2]
    assert X.tolist() == [[15.0, 1.0], [9.0, 2.0]]


def test_exact_sum_quantiles_independent_exponentials():
    from scipy.stats import gamma
    cdf = lambda x: 1.0 - np.exp(-np.asarray(x, dtype=float))
    icdf = lambda u: -np.log1p(-np.asarray(u, dtype=float))
    q = compose.exact_sum_quantiles(pv.Bicop(), cdf, icdf, cdf, icdf, [1e-2, 1e-4, 1e-6])
    for p, v in q.items():
        assert v == pytest.approx(gamma.ppf(1 - p, 2), rel=2e-4)


def test_exact_sum_quantiles_comonotonic_limit():
    # a Gumbel copula with a huge parameter is almost comonotonic: q(X+Y) ~ q(X) + q(Y)
    from scipy.special import ndtr, ndtri
    cdf = lambda x: ndtr(np.log(np.maximum(np.asarray(x, dtype=float), 1e-300)))
    icdf = lambda u: np.exp(ndtri(np.asarray(u, dtype=float)))
    g = bicop(F.gumbel, 0, 40.0)
    q = compose.exact_sum_quantiles(g, cdf, icdf, cdf, icdf, [1e-3, 1e-5])
    for p, v in q.items():
        assert v == pytest.approx(2 * icdf(1 - p), rel=0.03)


def test_exact_sum_quantiles_matches_monte_carlo():
    from scipy.special import ndtr, ndtri
    cdf = lambda x: ndtr(np.log(np.maximum(np.asarray(x, dtype=float), 1e-300)))
    icdf = lambda u: np.exp(ndtri(np.asarray(u, dtype=float)))
    g = bicop(F.clayton, 180, 2.0)
    exact = compose.exact_sum_quantiles(g, cdf, icdf, cdf, icdf, [1e-2, 1e-3])
    mc = compose.compose(g, [icdf, icdf], [1e-2, 1e-3], n_samples=4_000_000, chunk=1_000_000, seed=9)
    for p in (1e-2, 1e-3):
        assert exact[p] == pytest.approx(mc.quantiles[p], rel=0.02)
