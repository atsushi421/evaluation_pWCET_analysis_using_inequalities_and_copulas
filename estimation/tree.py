"""Composition of unit-level marginals over the timing schema (Section IV.C).

Every instrumented container node is the sum of its self time and its
effective children (nearest instrumented descendants); the parts are joined
by a copula fitted on their per-run totals (pool ``par``, criterion BIC,
Kendall-tau independence pre-test), by the independence coupling, or by the
comonotonic coupling. A loop body enters its loop's sum as the static
iteration bound times a bound on the per-run average iteration time (loop
rule ``avg``: T = N * A <= N_max * A, the leaf estimator runs on the per-run
averages A; the body's internals are not composed). Loop rule ``inst`` (the
method name suffixed ``@inst``) instead scales the body's per-instance
marginal by the bound, i.e. every iteration as slow as the tail
(comonotonic across iterations). The alternatives of a branch enter as their
pointwise max envelope. Bivariate nodes are composed
exactly (numerical integration, no MC noise); higher-dimensional nodes by
chunked Monte-Carlo through the fitted R-vine: the tail (p <= 1e-3) from
n_mc samples, the body from N_MC_BODY samples, merged into one monotone
quantile curve.
"""
import hashlib
import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pyvinecopulib as pv

from copula import compose as ccompose
from copula import select as cselect
from copula import vine as cvine

from . import chb, evt
from .data import WINDOW, Bench

P_GRID_FULL = (0.5, 0.3, 0.2, 0.1, 0.05, 0.02, 0.01, 5e-3, 2e-3, 1e-3,
               5e-4, 2e-4, 1e-4, 5e-5, 2e-5, 1e-5, 5e-6, 2e-6, 1e-6,
               5e-7, 2e-7, 1e-7, 1e-8, 1e-9, 1e-10)
P_GRID_TAIL = (1e-3, 5e-4, 2e-4, 1e-4, 5e-5, 2e-5, 1e-5, 5e-6, 2e-6, 1e-6)
P_EVAL = (1e-4, 1e-5, 1e-6)
LOOP_RULES = ("avg", "inst")
P_MC_SPLIT = 1e-3        # compose() keeps the top max(p) * n samples, so the body gets its own run
assert ccompose.P_TOP == max(chb.P_TEST)     # the monotonization rule pivots on the validated p
N_MC_BODY = 1_000_000


def monotone_pwcet(pwcet: dict) -> dict:
    """The per-p bounds made non-increasing in p (copula.compose.monotone_curve: running minimum
    from the largest RESTK test probability upward, running maximum from it downward), the same
    curve the composition uses; reported for the end-to-end estimators for consistency."""
    alphas, values = ccompose.monotone_curve(pwcet)
    return dict(zip((float(a) for a in alphas), (float(v) for v in values)))


def _seed(*key) -> np.random.Generator:
    h = hashlib.sha256("/".join(str(k) for k in key).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


@dataclass
class Marginal:
    pwcet: dict
    meta: dict = field(default_factory=dict)
    icdf_fn: Callable | None = None
    cdf_fn: Callable | None = None

    def icdf(self) -> Callable:
        return self.icdf_fn or ccompose.icdf_from_pwcet_dict(self.pwcet)

    def cdf(self) -> Callable:
        if self.cdf_fn is not None:
            return self.cdf_fn
        alphas, values = ccompose.monotone_curve(self.pwcet)      # non-increasing in alpha
        xs = values[::-1]
        ps = (1.0 - alphas)[::-1]
        # +inf entries (from p_inf on) are mass p_inf above every finite x; the CDF jumps to
        # 1 - p_inf at the last finite value (same step convention as icdf_from_pwcet_dict)
        finite = np.isfinite(xs)
        right = float(1.0 - alphas[~np.isfinite(values)].max()) if not finite.all() else float(ps[-1])
        xs, ps = xs[finite], ps[finite]

        def cdf(x):
            return np.interp(np.asarray(x, dtype=float), xs, ps, left=0.0, right=right)
        return cdf


def scale_marginal(m: Marginal, mult: int) -> Marginal:
    if mult == 1:
        return m
    icdf0, cdf0 = m.icdf(), m.cdf()
    return Marginal({p: v * mult for p, v in m.pwcet.items()},
                    {"scaled_by": mult, "inner": m.meta},
                    icdf_fn=lambda u: mult * icdf0(u),
                    cdf_fn=lambda x: cdf0(np.asarray(x, dtype=float) / mult))


def envelope_marginal(ms: list[Marginal], branch: str) -> Marginal:
    icdfs = [m.icdf() for m in ms]
    cdfs = [m.cdf() for m in ms]
    pwcet = {p: max(m.pwcet[p] for m in ms) for p in ms[0].pwcet}
    return Marginal(pwcet, {"branch": branch, "alternatives": [m.meta for m in ms]},
                    icdf_fn=lambda u: np.max([f(u) for f in icdfs], axis=0),
                    cdf_fn=lambda x: np.min([f(x) for f in cdfs], axis=0))


def constant_marginal(value: float, probs, note: str) -> Marginal:
    return Marginal({p: value for p in probs}, {"constant": value, "note": note},
                    icdf_fn=lambda u: np.full_like(np.asarray(u, dtype=float), value),
                    cdf_fn=lambda x: (np.asarray(x, dtype=float) >= value).astype(float))


# ------------------------------------------------------------ leaves

# The leaf of a unit depends on the method only through its family prefix (the seed is keyed on it),
# so CHB-COP, CHB-IND and CHB-COMONO of one window share their leaves within a process.
_LEAF_CACHE: dict = {}


def make_leaf(method: str, bench: str, window: int):
    """Leaf estimator by decomposed-method name: CHB-*, MEMIK-COP, EVT-COP."""
    family = method.split("-")[0]

    def leaf(samples, uid: str) -> Marginal:
        key = (bench, window, uid, family, hashlib.sha1(np.ascontiguousarray(samples).tobytes()).hexdigest())
        if key not in _LEAF_CACHE:
            _LEAF_CACHE[key] = _leaf(samples, uid)
        return _LEAF_CACHE[key]

    def _leaf(samples, uid: str) -> Marginal:
        rng = _seed(bench, window, uid, family)
        if len(samples) == 0:
            return constant_marginal(0.0, P_GRID_FULL, f"{uid}: no instance in window")
        if method.startswith("CHB"):
            r = chb.chb_leaf(samples, P_GRID_FULL, rng)
            return Marginal(r.pwcet, {"uid": uid, **r.detail})
        if method == "MEMIK-COP":
            r = chb.memik_leaf(samples, P_GRID_FULL, rng)
            return Marginal(r.pwcet, {"uid": uid, **r.detail})
        if method == "EVT-COP":
            fit = evt.pot_fit(samples)
            return Marginal({p: fit.quantile(p) for p in P_GRID_FULL},
                            {"uid": uid, **fit.detail}, icdf_fn=fit.icdf, cdf_fn=fit.cdf)
        raise ValueError(method)
    return leaf


# ------------------------------------------------------------ composition

def _fit_model(X: np.ndarray, mode: str, seed: int):
    d = X.shape[1]
    if mode == "comono":
        return "comono", {"model": "comono"}
    if mode == "indep":
        return (pv.Bicop() if d == 2 else "indep"), {"model": "indep"}
    X = X.astype(np.float64, copy=True)
    degenerate = [int(i) for i in range(d) if np.ptp(X[:, i]) == 0]
    for i in degenerate:
        # a constant column has no rank information (Kendall's tau is undefined);
        # replacing it by noise makes the fit treat the part as independent
        X[:, i] = np.random.default_rng(seed + i).standard_normal(len(X))
    U = cselect.pseudo_obs(X)
    extra = {"degenerate_cols": degenerate} if degenerate else {}
    pool, alpha = "par", 0.05
    if mode.startswith("fam:"):
        # family-fixed sensitivity (E2-5): every pair copula from one family (BIC picks the
        # rotation), no independence pre-test
        pool, alpha = [getattr(pv.BicopFamily, mode[4:])], None
    if d == 2:
        sel = cselect.select(U, pool=pool, criterion="bic", indep_alpha=alpha, seed=seed)
        return sel.bicop, {"model": sel.label, "tau": sel.tau, "indep_pvalue": sel.indep_pvalue, **extra}
    fit = cvine.fit_vine(U, pool=pool, criterion="bic", indep_alpha=alpha)
    return fit.vinecop, {"model": "rvine", "edges": fit.edges(), **extra}


def compose_parts(parts: list[Marginal], X: np.ndarray, mode: str, probs,
                  n_mc: int, seed: int) -> tuple[dict, dict]:
    icdfs = [m.icdf() for m in parts]
    if mode == "comono":
        one = np.array([1.0])
        q = {p: float(sum(f(one * (1.0 - p))[0] for f in icdfs)) for p in probs}
        return q, {"model": "comono"}
    model, minfo = _fit_model(X, mode, seed)
    if isinstance(model, pv.Bicop) and len(parts) == 2:
        q = ccompose.exact_sum_quantiles(model, parts[0].cdf(), icdfs[0], parts[1].cdf(), icdfs[1], probs)
        minfo["composition"] = "exact"
        return {p: float(v) for p, v in q.items()}, minfo
    tail = [p for p in probs if p <= P_MC_SPLIT]
    body = [p for p in probs if p > P_MC_SPLIT]
    q = {}
    if tail:
        q.update(ccompose.compose(model, icdfs, tail, n_samples=n_mc, seed=seed).quantiles)
    if body:
        q.update(ccompose.compose(model, icdfs, body, n_samples=N_MC_BODY, seed=seed + 1).quantiles)
    # two MC runs can cross at the split; the running max keeps the curve
    # monotone and only moves values up
    out, run = {}, -np.inf
    for p in sorted(q, reverse=True):
        run = max(run, float(q[p]))
        out[p] = run
    minfo["composition"] = f"mc n={n_mc}" + (f" (body n={N_MC_BODY})" if body else "")
    return out, minfo


def _multiplicity(bench: Bench, parent_uid: str, child_uid: str, lo: int, hi: int) -> int:
    pc = bench.per_run_counts(parent_uid, lo, hi)
    cc = bench.per_run_counts(child_uid, lo, hi)
    present = pc > 0
    if not present.any():
        return 1
    return int(np.ceil((cc[present] / pc[present]).max())) or 1


def loop_avg_marginal(bench: Bench, body_uid: str, bound: int, lo: int, hi: int, leaf,
                      meta_sink: dict) -> tuple[Marginal, np.ndarray]:
    """Loop rule avg: the leaf bound on the per-run average iteration time, scaled by the static
    bound; returns the part and its per-run column for the copula fit (the average, 0 when the
    loop did not iterate). Runs without an iteration are left out of the marginal, which can only
    raise it."""
    clean = bench.window_clean_runs(lo, hi)
    c = bench.per_run_counts(body_uid, lo, hi)[clean]
    t = bench.per_run_totals(body_uid, lo, hi)[clean]
    has = c > 0
    m = leaf(t[has] / c[has], body_uid + ".avg")
    meta_sink[body_uid + ".avg"] = {**m.meta, "n_runs": int(has.sum()), "count_max": int(c.max(initial=0)),
                                    "bound": int(bound)}
    return scale_marginal(m, bound), np.where(has, t / np.maximum(c, 1), 0.0)


def node_marginal(bench: Bench, uid: str, method: str, mode: str, lo: int, hi: int,
                  probs, leaf, n_mc: int, meta_sink: dict, loop_rule: str = "avg") -> Marginal:
    unit = bench.by_uid[uid]
    eff = bench.effective_children(uid)
    if not eff:
        m = leaf(bench.unit_window(uid, lo, hi), uid)
        meta_sink[uid] = m.meta
        return m
    clean = bench.window_clean_runs(lo, hi)
    parts, cols, labels = [], [], []
    ud = bench.units[uid]
    if ud.self_vals is not None:
        parts.append(leaf(bench.unit_window(uid, lo, hi, "self"), uid + ".self"))
        cols.append(bench.per_run_totals(uid, lo, hi, "self")[clean])
        labels.append(uid + ".self")
        meta_sink[uid + ".self"] = parts[-1].meta
    branches: dict[str, list] = {}
    for child in eff:
        if child.kind == "alternative":
            branches.setdefault(bench.branch_of(child.uid), []).append(child)
            continue
        if child.kind == "loop_body":
            mult = unit.bound if unit.kind == "loop" else bench.loop_of_body(child.uid).bound
            if mult is None:
                raise ValueError(f"{child.uid}: loop body without a static bound")
            if loop_rule == "avg":
                part, col = loop_avg_marginal(bench, child.uid, mult, lo, hi, leaf, meta_sink)
                parts.append(part)
                cols.append(col)
                labels.append(f"{child.uid} (avg x{mult})")
                continue
        m = node_marginal(bench, child.uid, method, mode, lo, hi, P_GRID_FULL, leaf, n_mc, meta_sink, loop_rule)
        if child.kind != "loop_body":
            mult = _multiplicity(bench, uid, child.uid, lo, hi)
        parts.append(scale_marginal(m, mult))
        cols.append(bench.per_run_totals(child.uid, lo, hi)[clean])
        labels.append(f"{child.uid} (x{mult})" if mult > 1 else child.uid)
    for branch, alts in branches.items():
        ms = [node_marginal(bench, a.uid, method, mode, lo, hi, P_GRID_FULL, leaf, n_mc, meta_sink, loop_rule)
              for a in alts]
        parts.append(envelope_marginal(ms, branch))
        cols.append(sum(bench.per_run_totals(a.uid, lo, hi)[clean] for a in alts))
        labels.append(f"max({branch})")
    if len(parts) == 1:
        meta_sink[uid] = {"note": "single part", "parts": labels}
        return parts[0]
    X = np.column_stack(cols)
    seed = int(_seed(bench.bench, lo, uid, mode).integers(0, 2**31 - 1))
    q, minfo = compose_parts(parts, X, mode, probs, n_mc, seed)
    meta_sink[uid] = {"parts": labels, **minfo}
    return Marginal(q, {"uid": uid, "parts": labels, **minfo})


def decomposed_estimate(bench: Bench, method: str, window: int, n_mc: int = int(1e8),
                        probs=P_GRID_TAIL, window_size: int = WINDOW,
                        window_stride: int | None = None) -> tuple[dict, dict]:
    """`method` is a decomposed-method name, optionally suffixed with a loop rule (CHB-COP@inst)."""
    method, _, loop_rule = method.partition("@")
    loop_rule = loop_rule or "avg"
    if loop_rule not in LOOP_RULES:
        raise ValueError(f"unknown loop rule {loop_rule}")
    if method.startswith("CHB-FAM-"):          # e.g. CHB-FAM-gumbel
        mode = "fam:" + method[len("CHB-FAM-"):]
    else:
        mode = {"CHB-COP": "cop", "CHB-IND": "indep", "CHB-COMONO": "comono",
                "MEMIK-COP": "cop", "EVT-COP": "cop"}[method]
    lo, hi = bench.window_bounds(window, window_size, window_stride)
    leaf = make_leaf(method, bench.bench, window)
    meta: dict = {}
    root = node_marginal(bench, bench.schema.entry_function, method, mode, lo, hi,
                         probs, leaf, n_mc, meta, loop_rule)
    return root.pwcet, meta
