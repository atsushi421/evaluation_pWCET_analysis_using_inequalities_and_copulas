"""Monte-Carlo composition of unit-level distributions through a copula.

Generalizes the last cells of ``copulas.ipynb``: uniform samples from a fitted
copula (or the independence, comonotonic and countermonotonic couplings) are
mapped through per-unit inverse CDFs, aggregated (sum or max) and re-quantized
at the requested exceedance probabilities. Simulation is chunked and only the
largest values are kept, so N = 1e8 needs little memory.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

import numpy as np
import pyvinecopulib as pv

ICDF = Callable[[np.ndarray], np.ndarray]


def icdf_from_pwcet_dict(pwcet: dict) -> ICDF:
    """Inverse CDF from a pWCET dictionary {exceedance probability: value}."""
    alphas = np.array(sorted(pwcet.keys()), dtype=float)
    values = np.array([pwcet[a] for a in alphas], dtype=float)
    ps = 1.0 - alphas[::-1]
    xs = values[::-1]

    def icdf(u):
        return np.interp(np.asarray(u, dtype=float), ps, xs)
    return icdf


def icdf_from_curve(exceed_probs: Sequence[float], values: Sequence[float]) -> ICDF:
    return icdf_from_pwcet_dict(dict(zip(exceed_probs, values)))


def icdf_from_samples(samples) -> ICDF:
    """Empirical quantile function (left-continuous, no extrapolation beyond the maximum)."""
    xs = np.sort(np.asarray(samples, dtype=float))
    n = len(xs)

    def icdf(u):
        idx = np.clip(np.floor(np.asarray(u, dtype=float) * n).astype(np.int64), 0, n - 1)
        return xs[idx]
    return icdf


def empirical_quantiles(samples, exceed_probs: Iterable[float]) -> dict:
    """Quantile at 1 - p for every p, with the index convention of copulas.ipynb."""
    xs = np.sort(np.asarray(samples, dtype=float))
    n = len(xs)
    out = {}
    for p in exceed_probs:
        idx = min(max(int(math.ceil((1.0 - p) * n)) - 1, 0), n - 1)
        out[p] = float(xs[idx])
    return out


def uniform_samples(model, n: int, d: int, rng: np.random.Generator, seed: int) -> np.ndarray:
    if isinstance(model, str):
        if model == "indep":
            return rng.uniform(size=(n, d))
        if model == "comono":
            return np.repeat(rng.uniform(size=(n, 1)), d, axis=1)
        if model == "countermono":
            if d != 2:
                raise ValueError("countermonotonic coupling is bivariate")
            u = rng.uniform(size=n)
            return np.column_stack([u, 1.0 - u])
        raise ValueError(model)
    if hasattr(model, "simulate"):
        return model.simulate(n, seeds=[seed])
    raise TypeError(type(model))


@dataclass
class ComposeResult:
    quantiles: dict
    n_samples: int
    seconds: float
    mean: float
    max: float


def compose(model, icdfs: Sequence[ICDF], exceed_probs: Iterable[float], n_samples: int = 10_000_000,
            chunk: int = 2_000_000, seed: int = 0, agg: str = "sum") -> ComposeResult:
    """Quantiles at 1 - p of agg(F_1^{-1}(U_1), ..., F_d^{-1}(U_d)) with (U_1..U_d) ~ model."""
    probs = sorted(set(float(p) for p in exceed_probs), reverse=True)
    d = len(icdfs)
    if isinstance(model, pv.Bicop) and d != 2:
        raise ValueError("a bivariate copula needs exactly two inverse CDFs")
    if isinstance(model, pv.Vinecop) and model.dim != d:
        raise ValueError("vine dimension and number of inverse CDFs differ")
    keep = int(math.ceil(max(probs) * n_samples)) + 2
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    top = np.empty(0)
    total, count, largest = 0.0, 0, -np.inf
    done = 0
    k = 0
    while done < n_samples:
        m = min(chunk, n_samples - done)
        u = uniform_samples(model, m, d, rng, (seed * 100_003 + k) % 2_147_483_647)
        cols = [icdfs[i](u[:, i]) for i in range(d)]
        s = np.sum(cols, axis=0) if agg == "sum" else np.max(cols, axis=0)
        total += float(s.sum())
        count += m
        largest = max(largest, float(s.max()))
        top = np.concatenate([top, s])
        if len(top) > keep:
            top = np.partition(top, len(top) - keep)[len(top) - keep:]
        done += m
        k += 1
    desc = np.sort(top)[::-1]
    quantiles = {}
    for p in probs:
        idx_from_top = n_samples - int(math.ceil((1.0 - p) * n_samples))
        quantiles[p] = float(desc[min(idx_from_top, len(desc) - 1)])
    return ComposeResult(quantiles, n_samples, time.perf_counter() - t0, total / count, largest)


# ------------------------------------------------------------ exact bivariate composition

def cdf_from_samples(samples) -> Callable[[np.ndarray], np.ndarray]:
    """Empirical CDF F(x) = #{samples <= x} / n (right-continuous)."""
    xs = np.sort(np.asarray(samples, dtype=float))
    n = len(xs)

    def cdf(x):
        return np.searchsorted(xs, np.asarray(x, dtype=float), side="right") / n
    return cdf


def default_u_grid() -> np.ndarray:
    """Integration grid on (0, 1), logarithmically refined toward both ends (about 47k points)."""
    near0 = 10.0 ** (-np.linspace(1.0, 12.0, 12_000))
    mid = np.linspace(0.1, 0.9, 2_001)
    near1 = 1.0 - 10.0 ** (-np.linspace(1.0, 12.0, 33_000))
    return np.unique(np.concatenate([near0, mid, near1]))


def exact_sum_tail(model, cdf1, icdf1, cdf2, t: float, u_grid: np.ndarray | None = None) -> float:
    """P(X + Y > t) for (U, V) ~ model (bivariate), X = F1^{-1}(U), Y = F2^{-1}(V).

    P(X + Y > t) = 1 - F1(t) + int_0^{F1(t)} [1 - h1(u, F2(t - F1^{-1}(u)))] du,
    with h1(u, v) = P(V <= v | U = u) the first h-function of the copula; the
    integral is evaluated by the trapezoidal rule on ``u_grid``.
    """
    grid = default_u_grid() if u_grid is None else u_grid
    f1t = float(cdf1(t))
    us = grid[grid < f1t]
    if len(us) == 0:
        return 1.0
    us = np.append(us, f1t)
    x = icdf1(us)
    v = np.clip(cdf2(np.maximum(t - x, 0.0)), 0.0, 1.0)
    uv = np.asfortranarray(np.column_stack([np.clip(us, 1e-300, 1.0 - 1e-16), np.clip(v, 1e-300, 1.0 - 1e-16)]))
    g = 1.0 - model.hfunc1(uv)
    g[v >= 1.0 - 1e-16] = 0.0
    integral = float(np.sum(0.5 * (g[1:] + g[:-1]) * np.diff(us))) + float(g[0] * us[0])
    return (1.0 - f1t) + integral


def exact_sum_quantiles(model, cdf1, icdf1, cdf2, icdf2, exceed_probs: Iterable[float],
                        u_grid: np.ndarray | None = None, rel_tol: float = 1e-5) -> dict:
    """Quantiles at 1 - p of X + Y by bisection on :func:`exact_sum_tail` (no Monte-Carlo noise)."""
    grid = default_u_grid() if u_grid is None else u_grid
    out = {}
    for p in sorted(set(float(q) for q in exceed_probs), reverse=True):
        lo = 0.0
        hi = float(icdf1(np.array([1.0 - p]))[0] + icdf2(np.array([1.0 - p]))[0])
        hi = max(hi, 1e-12)
        while exact_sum_tail(model, cdf1, icdf1, cdf2, hi, grid) > p:
            hi *= 2.0
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if exact_sum_tail(model, cdf1, icdf1, cdf2, mid, grid) > p:
                lo = mid
            else:
                hi = mid
            if hi - lo <= rel_tol * hi:
                break
        out[p] = hi
    return out
