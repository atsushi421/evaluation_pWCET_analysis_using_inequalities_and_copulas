"""EVT and Cantelli estimators for the baseline ablation (E2-2).

E2E-EVT-PoT / EVT-COP leaves: GPD above a threshold selected by EQMAE
minimization (Arcaro 2018, 31 candidates in [0.6, 0.9]) followed by TailID
(ECRTS 2025; scenario 1 keeps t = Q(p_m), scenario 2 moves t to the first
ID-sensitive point, scenario 3 falls back to the ECDF), empirical below.
E2E-EVT-BM: block maxima with L-moments GEV (Hosking 1990) per block size,
accepted by Q-Q linearity R^2 >= 0.99 (the TimeProbe procedure made numeric),
KS p-value reported. E2E-CANTELLI: one-sided Chebyshev bound from bootstrap
upper confidence limits of mean and standard deviation (CTA, RTSS 2023).
"""
import math
import os
import sys
from dataclasses import dataclass, field

import numpy as np
from scipy import stats as sps

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "external", "TailID"))
from src.tailid import tail_id  # noqa: E402
from src.threshold_selection import select_threshold  # noqa: E402

EULER_GAMMA = 0.5772156649015329


# ------------------------------------------------------------ PoT + TailID

@dataclass
class PotFit:
    scenario: int                 # TailID scenario (3 = ECDF fallback)
    p_m: float
    threshold: float | None = None
    xi: float | None = None
    sigma: float | None = None
    zeta: float | None = None     # exceedance fraction n_t / n
    samples: np.ndarray | None = None
    detail: dict = field(default_factory=dict)

    def quantile(self, p: float) -> float:
        if self.scenario == 3 or p >= self.zeta_or(1.0):
            xs = np.sort(self.samples)
            idx = min(max(int(math.ceil((1.0 - p) * len(xs))) - 1, 0), len(xs) - 1)
            return float(xs[idx])
        if abs(self.xi) < 1e-9:
            return self.threshold + self.sigma * math.log(self.zeta / p)
        return self.threshold + self.sigma / self.xi * ((p / self.zeta) ** (-self.xi) - 1.0)

    def zeta_or(self, default: float) -> float:
        return self.zeta if self.zeta is not None else default

    def icdf(self, u: np.ndarray) -> np.ndarray:
        u = np.asarray(u, dtype=float)
        xs = np.sort(self.samples)
        n = len(xs)
        idx = np.clip(np.floor(u * n).astype(np.int64), 0, n - 1)
        out = xs[idx].astype(float)
        if self.scenario != 3:
            p = 1.0 - u
            tail = p < self.zeta
            if tail.any():
                pt = np.clip(p[tail], 1e-300, None)
                if abs(self.xi) < 1e-9:
                    out[tail] = self.threshold + self.sigma * np.log(self.zeta / pt)
                else:
                    out[tail] = self.threshold + self.sigma / self.xi * ((pt / self.zeta) ** (-self.xi) - 1.0)
        return out

    def cdf(self, x) -> np.ndarray:
        scalar = np.ndim(x) == 0
        x = np.atleast_1d(np.asarray(x, dtype=float))
        xs = np.sort(self.samples)
        out = np.searchsorted(xs, x, side="right") / len(xs)
        if self.scenario != 3:
            tail = x > self.threshold
            if tail.any():
                z = (x[tail] - self.threshold) / self.sigma
                if abs(self.xi) < 1e-9:
                    sf = np.exp(-z)
                else:
                    sf = np.maximum(1.0 + self.xi * z, 0.0) ** (-1.0 / self.xi)
                out[tail] = 1.0 - self.zeta * sf
        out = np.clip(out, 0.0, 1.0)
        return float(out[0]) if scalar else out


def pot_fit(samples, n_candidates: int = 31, gamma: float = 0.9999, mos: int = 40) -> PotFit:
    x = np.asarray(samples, dtype=np.float64)
    p_m = float(select_threshold(x, n_candidates))
    p_c1 = 1.0 - 0.05 * (1.0 - p_m)
    res = tail_id(x, p_m=p_m, p_c1=p_c1, gamma=gamma, mos=mos)
    scenario = res.scenario.value
    detail = {"p_m": p_m, "p_c1": p_c1, "n_sensitive": len(res.sensitive_points),
              "tailid_scenario": scenario}
    if scenario == 3:
        return PotFit(3, p_m, samples=x, detail=detail)
    t = float(np.quantile(x, p_m)) if scenario == 1 else float(res.tail_threshold)
    exc = x[x > t] - t
    if len(exc) < 10:
        detail["fallback"] = f"only {len(exc)} exceedances"
        return PotFit(3, p_m, samples=x, detail=detail)
    xi, _, sigma = sps.genpareto.fit(exc, floc=0)
    detail |= {"threshold": t, "xi": float(xi), "sigma": float(sigma), "n_exc": len(exc)}
    return PotFit(scenario, p_m, t, float(xi), float(sigma), len(exc) / len(x), x, detail)


# ------------------------------------------------------------ Block Maxima

def lmom_gev(maxima: np.ndarray):
    """GEV parameters from the first three L-moments (Hosking 1990).
    Returns (kappa, loc, scale) in scipy's genextreme convention (c = kappa)."""
    xs = np.sort(maxima)
    n = len(xs)
    i = np.arange(1, n + 1)
    b0 = xs.mean()
    b1 = np.sum((i - 1) / (n - 1) * xs) / n
    b2 = np.sum((i - 1) * (i - 2) / ((n - 1) * (n - 2)) * xs) / n
    l1, l2 = b0, 2 * b1 - b0
    t3 = (6 * b2 - 6 * b1 + b0) / l2
    c = 2.0 / (3.0 + t3) - math.log(2) / math.log(3)
    kappa = 7.8590 * c + 2.9554 * c * c
    if abs(kappa) < 1e-6:
        scale = l2 / math.log(2)
        return 0.0, l1 - EULER_GAMMA * scale, scale
    g = math.gamma(1.0 + kappa)
    scale = l2 * kappa / ((1.0 - 2.0 ** (-kappa)) * g)
    loc = l1 - scale * (1.0 - g) / kappa
    return kappa, loc, scale


def bm_estimate(samples, p_list, block_sizes=(10, 20, 50, 100), r2_min: float = 0.99) -> dict:
    """Per block size: L-moments GEV fit, Q-Q acceptance, pWCET(p) = G^{-1}((1-p)^B)."""
    x = np.asarray(samples, dtype=np.float64)
    out = {}
    for b in block_sizes:
        nb = len(x) // b
        maxima = x[:nb * b].reshape(nb, b).max(axis=1)
        kappa, loc, scale = lmom_gev(maxima)
        dist = sps.genextreme(kappa, loc=loc, scale=scale)
        pos = (np.arange(1, nb + 1) - 0.44) / (nb + 0.12)     # Gringorten plotting positions
        theo = dist.ppf(pos)
        emp = np.sort(maxima)
        ok = np.isfinite(theo)
        r2 = float(np.corrcoef(theo[ok], emp[ok])[0, 1] ** 2) if ok.sum() > 2 else 0.0
        ks_p = float(sps.kstest(maxima, dist.cdf).pvalue)
        est = {p: float(dist.ppf((1.0 - p) ** b)) for p in p_list}
        out[b] = {"kappa": kappa, "loc": loc, "scale": scale, "n_blocks": nb,
                  "qq_r2": r2, "ks_pvalue": ks_p, "accepted": r2 >= r2_min, "estimate": est}
    return out


# ------------------------------------------------------------ Cantelli

def cantelli_estimate(samples, p_list, n_boot: int = 1000, conf: float = 0.95,
                      rng: np.random.Generator | None = None) -> dict:
    x = np.asarray(samples, dtype=np.float64)
    rng = rng or np.random.default_rng(0)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    boots = x[idx]
    mu_up = float(np.quantile(boots.mean(axis=1), conf))
    sd_up = float(np.quantile(boots.std(axis=1, ddof=1), conf))
    mu, sd = float(x.mean()), float(x.std(ddof=1))
    return {"mu_upper": mu_up, "sd_upper": sd_up, "mu": mu, "sd": sd,
            "estimate": {p: mu_up + sd_up * math.sqrt((1 - p) / p) for p in p_list},
            "plugin": {p: mu + sd * math.sqrt((1 - p) / p) for p in p_list}}
