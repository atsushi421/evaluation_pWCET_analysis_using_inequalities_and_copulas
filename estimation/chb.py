"""Saturating-Chebyshev (CHB) and MEMIK leaf estimators.

Vectorized reimplementation of the RESTK + envelope pipeline of ``memik/``,
``atan/`` and ``tanh/`` (same algorithm and settings as ``chb_main.ipynb``:
k in [1, 150], n_sims 1000/500/100 for memik/atan/tanh, n_boot 1e3,
p_test {1e-4, 1e-5, 1e-6}, 13-point log d grids), plus the finite-sample
KL certificate of CC-C. The d grid is derived from a calibration subsample
(the first ``calib_frac`` of the window) and the moments are estimated on
the remaining main sample, so the union bound over the fixed grid applies
to the main sample.
"""
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .kl import kl_inv_upper

P_TEST = (1e-4, 1e-5, 1e-6)
K_MAX = 150
N_BOOT = 1000
N_SIMS = {"memik": 1000, "atan": 500, "tanh": 100}


@dataclass(frozen=True)
class Family:
    name: str
    g: Callable          # y = g(x, d), the saturating transform
    inv: Callable        # b = inv(theta, d), inverse of g in x
    sup: float           # sup of g (pi/2, 1, or inf for memik)
    d_hi_factor: float   # upper end of the d grid, times max(sample)

    def d_grid(self, calib: np.ndarray, n_d: int = 13, widen: float = 1.0) -> np.ndarray:
        """13-point log grid of the notebooks; widen > 1 stretches both ends by that factor."""
        if not np.isfinite(self.sup):
            return np.array([1.0])
        mid = (float(calib.min()) + float(calib.max())) / 2.0
        return np.logspace(np.log10(mid / 50.0 / widen), np.log10(float(calib.max()) * self.d_hi_factor * widen), n_d)


FAMILIES = {
    "atan": Family("atan", lambda x, d: np.arctan(x / d), lambda t, d: d * np.tan(t), np.pi / 2, 5000.0),
    "tanh": Family("tanh", lambda x, d: np.tanh(x / d), lambda t, d: d * np.arctanh(t), 1.0, 1000.0),
    "memik": Family("memik", lambda x, d: x, lambda t, d: t, np.inf, 1.0),
    # further bounded saturating transforms, only for the family comparison (E1-1)
    "softsign": Family("softsign", lambda x, d: x / (x + d), lambda t, d: d * t / (1.0 - t), 1.0, 1000.0),
    "hill2": Family("hill2", lambda x, d: x * x / (x * x + d * d), lambda t, d: d * np.sqrt(t / (1.0 - t)), 1.0, 1000.0),
    "expsat": Family("expsat", lambda x, d: -np.expm1(-x / d), lambda t, d: -d * np.log1p(-t), 1.0, 1000.0),
}


def _restk_min_k(samples, fam: Family, d: float, p: float, q_est: float,
                 n_sims: int, n_boot: int, rng: np.random.Generator, k_max: int = K_MAX) -> int:
    """min over n_sims bootstrap simulations of the k chosen by the RESTK scan."""
    idx = rng.integers(0, len(samples), size=(n_sims, n_boot))
    y = fam.g(samples[idx], d)
    powers = np.ones_like(y)
    best = np.full(n_sims, np.inf)
    cur = np.full(n_sims, 0, dtype=np.int64)
    active = np.ones(n_sims, dtype=bool)
    with np.errstate(all="ignore"):
        for k in range(1, k_max + 1):
            if not active.any():
                break
            powers *= y
            m = powers.mean(axis=1)
            tight = fam.inv((m / p) ** (1.0 / k), d) / q_est
            dip = active & (tight < 1.0)          # NaN compares False, like the originals
            active &= ~dip
            upd = active & (tight < best)
            best[upd] = tight[upd]
            cur[upd] = k
    cur[cur == 0] = k_max
    return int(cur.min())


def _predict_max_k(max_k_test: dict, p_all, k_max: int = K_MAX) -> dict:
    """Linear fit of k against log10 p (predict_max_k_linear of the originals)."""
    xs = np.log10(np.array(list(max_k_test.keys())))
    ys = np.array(list(max_k_test.values()), dtype=float)
    slope, intercept = np.polyfit(xs, ys, 1)
    out = dict(max_k_test)
    for p in p_all:
        if p not in out:
            out[p] = int(round(slope * np.log10(p) + intercept))
    return {p: min(max(k, 1), k_max) for p, k in out.items()}


def _log_moments(y: np.ndarray, k_max: int) -> np.ndarray:
    """log E[y^k] for k = 1..k_max by log-sum-exp (index k-1)."""
    with np.errstate(divide="ignore"):
        ly = np.log(y)
    ly = ly[np.isfinite(ly)]         # y == 0 contributes nothing to the sum
    n = len(y)
    out = np.empty(k_max)
    for k in range(1, k_max + 1):
        lp = ly * k
        mx = lp.max()
        out[k - 1] = mx + np.log(np.exp(lp - mx).sum()) - np.log(n)
    return out


def _envelope(samples, fam: Family, d_list, max_k_by_d: dict, p_all, k_max: int = K_MAX) -> dict:
    """min over the (d, k) grid of the plug-in bound, with the originals' early stop."""
    out = {}
    log_m = {d: _log_moments(fam.g(samples, d), k_max) for d in d_list}
    for p in p_all:
        best, arg = np.inf, (None, None)
        for d in d_list:
            best_d = np.inf
            for k in range(1, max_k_by_d[d][p] + 1):
                theta = np.exp((log_m[d][k - 1] - np.log(p)) / k)
                if theta >= fam.sup:
                    continue
                pred = float(fam.inv(theta, d))
                if pred > best_d:
                    break
                best_d = pred
                if pred < best:
                    best, arg = pred, (float(d), k)
        out[p] = (best, arg[0], arg[1])
    return out


def family_pwcet(samples: np.ndarray, fam_name: str, p_all, rng: np.random.Generator,
                 d_list=None, p_test=P_TEST, k_max: int = K_MAX, n_sims: int | None = None) -> dict:
    fam = FAMILIES[fam_name]
    if d_list is None:
        d_list = fam.d_grid(samples)
    n_sims = N_SIMS[fam_name] if n_sims is None else n_sims
    max_k_by_d = {}
    for d in d_list:
        mk = {p: _restk_min_k(samples, fam, d, p, float(np.quantile(samples, 1 - p)),
                              n_sims, N_BOOT, rng, k_max) for p in p_test}
        max_k_by_d[d] = _predict_max_k(mk, p_all, k_max)
    return _envelope(samples, fam, d_list, max_k_by_d, p_all, k_max)


@dataclass
class LeafResult:
    pwcet: dict                      # {p: bound}
    detail: dict = field(default_factory=dict)


def _shift(samples):
    samples = np.asarray(samples, dtype=np.float64)
    lo = samples.min()
    if lo <= 0:
        return samples - lo + 1.0, lo - 1.0
    return samples, 0.0


def chb_leaf(samples, p_all, rng: np.random.Generator, calib_frac: float = 0.1,
             alpha: float = 0.05, certificate: bool = True) -> LeafResult:
    """Envelope over the atan and tanh grids (plug-in), plus the KL certificate."""
    samples, shift = _shift(samples)
    n_cal = max(int(len(samples) * calib_frac), 2)
    calib, main = samples[:n_cal], samples[n_cal:]
    per_family, pwcet, detail = {}, {}, {}
    for name in ("atan", "tanh"):
        fam = FAMILIES[name]
        per_family[name] = family_pwcet(main, name, p_all, rng, d_list=fam.d_grid(calib))
    for p in p_all:
        name = min(per_family, key=lambda f: per_family[f][p][0])
        v, d, k = per_family[name][p]
        pwcet[p] = v + shift
        detail[p] = {"family": name, "d": d, "k": k}
    out = LeafResult(pwcet, {"choice": detail, "n_main": len(main), "n_calib": n_cal})
    if certificate:
        out.detail["certificate"] = kl_certificate(main, calib, p_all, alpha, shift)
    return out


def memik_leaf(samples, p_all, rng: np.random.Generator) -> LeafResult:
    samples, shift = _shift(samples)
    env = family_pwcet(samples, "memik", p_all, rng)
    return LeafResult({p: v + shift for p, (v, _, k) in env.items()},
                      {"choice": {p: {"k": k} for p, (v, _, k) in env.items()}})


def kl_certificate(main, calib, p_all, alpha: float, shift: float = 0.0) -> dict:
    """Certified envelope: with probability >= 1 - alpha, simultaneously over the
    whole grid, P(X >= b) <= mu+/f(b), where mu+ is the KL upper confidence bound
    of E[(g(X,d)/sup)^k]. Entries are +inf below the certification floor."""
    n = len(main)
    grid = {name: FAMILIES[name].d_grid(calib) for name in ("atan", "tanh")}
    g_size = sum(len(d) for d in grid.values()) * K_MAX
    tau = np.log(g_size / alpha) / n
    mu_all = {}
    for name, d_list in grid.items():
        fam = FAMILIES[name]
        for d in d_list:
            z = fam.g(main, d) / fam.sup
            log_m = _log_moments(z, K_MAX)
            mu_all[(name, float(d))] = kl_inv_upper(np.exp(log_m), tau)
    out = {"tau": tau, "grid_size": g_size, "alpha": alpha, "n": n,
           "floor": 1.0 - np.exp(-tau), "p_min_data": float(min(m.min() for m in mu_all.values())),
           "pwcet": {}}
    ks = np.arange(1, K_MAX + 1)
    for p in p_all:
        best = np.inf
        for (name, d), mu in mu_all.items():
            fam = FAMILIES[name]
            with np.errstate(all="ignore"):
                theta = (mu / p) ** (1.0 / ks)
                valid = theta < 1.0
                if valid.any():
                    b = fam.inv(theta[valid] * fam.sup, d).min()
                    best = min(best, float(b))
        out["pwcet"][p] = best + shift if np.isfinite(best) else np.inf
    return out
