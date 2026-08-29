"""Pair-copula family selection over a candidate pool with several criteria.

All candidates are fitted once by maximum likelihood; every criterion is then
evaluated on the same fits, so that selections under different criteria are
directly comparable. Criteria:

``loglik``  maximum log-likelihood (no penalty)
``aic``     Akaike information criterion
``bic``     Bayesian (Schwarz) information criterion
``mbic``    modified BIC with prior probability ``psi0`` of non-independence
            (Nagler, Bumann and Czado, 2019)
``cv``      K-fold cross-validated out-of-sample log-likelihood
``tcf``     tail-concentration fit: Wald-type distance between the empirical
            and the model upper tail concentration 1 - 2q + C(q, q) at the
            levels ``tcf_levels`` (upper tail only, the corner that drives the
            quantiles of a sum)
``hybrid``  smallest ``tcf`` among the candidates whose BIC is within
            ``hybrid_delta`` of the best BIC
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pyvinecopulib as pv

from .families import F, candidates, label, tail_dependence

CRITERIA = ("loglik", "aic", "bic", "mbic", "cv", "tcf", "hybrid")
NATIVE_CRITERIA = ("loglik", "aic", "bic", "mbic")
TCF_LEVELS = (0.90, 0.95, 0.98, 0.99, 0.995)
HYBRID_DELTA_BIC = 10.0


def pseudo_obs(x, ties_method: str = "average") -> np.ndarray:
    """Rank-based pseudo-observations in (0, 1); ``ties_method`` as in pyvinecopulib."""
    return pv.to_pseudo_obs(np.asarray(x, dtype=float), ties_method=ties_method)


def kendall_tau(u: np.ndarray) -> float:
    return float(pv.wdm(np.ascontiguousarray(u[:, 0]), np.ascontiguousarray(u[:, 1]), "ktau"))


def independence_test(u: np.ndarray) -> tuple[float, float, float]:
    """Kendall's tau, its standardized statistic and the two-sided p-value.

    Asymptotic test used by VineCopula's ``BiCopIndTest``:
    z = tau / sqrt(2 (2n + 5) / (9 n (n - 1))).
    """
    n = len(u)
    tau = kendall_tau(u)
    z = tau / math.sqrt(2.0 * (2.0 * n + 5.0) / (9.0 * n * (n - 1.0)))
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return tau, z, p


@dataclass
class Candidate:
    family: pv.BicopFamily
    rotation: int
    bicop: pv.Bicop
    npars: float
    loglik: float
    aic: float
    bic: float
    mbic: float
    tau: float
    lambda_l: float
    lambda_u: float
    fit_seconds: float
    cv_loglik: float = math.nan
    tcf: float = math.nan

    @property
    def label(self) -> str:
        return label(self.family, self.rotation)

    @property
    def parameters(self) -> list[float]:
        return np.asarray(self.bicop.parameters).ravel().tolist()

    def as_dict(self) -> dict:
        return {
            "label": self.label, "family": self.family.name, "rotation": self.rotation,
            "npars": self.npars, "loglik": self.loglik, "aic": self.aic, "bic": self.bic,
            "mbic": self.mbic, "cv_loglik": self.cv_loglik, "tcf": self.tcf, "tau": self.tau,
            "lambda_l": self.lambda_l, "lambda_u": self.lambda_u, "fit_seconds": self.fit_seconds,
            "parameters": self.parameters if self.family != F.tll else [],
        }


def fit_candidate(u: np.ndarray, family: pv.BicopFamily, rotation: int, psi0: float = 0.9) -> Candidate:
    bicop = pv.Bicop(family=family, rotation=rotation)
    t0 = time.perf_counter()
    if family != F.indep:
        bicop.fit(u, controls=pv.FitControlsBicop(family_set=[family]))
    dt = time.perf_counter() - t0
    ll = float(bicop.loglik(u))
    lo, up = tail_dependence(family, rotation, bicop.parameters)
    return Candidate(family, rotation, bicop, float(bicop.npars), ll, float(bicop.aic(u)),
                     float(bicop.bic(u)), float(bicop.mbic(u, psi0)), float(bicop.tau), lo, up, dt)


def fit_candidates(u: np.ndarray, pool="par", preselect: bool = True, psi0: float = 0.9) -> list[Candidate]:
    tau = kendall_tau(u) if preselect else None
    out = []
    for fam, rot in candidates(pool, tau):
        try:
            out.append(fit_candidate(u, fam, rot, psi0))
        except RuntimeError:
            continue  # numerical failure of one family must not abort the selection
    return out


def tail_concentration_stat(u: np.ndarray, bicop: pv.Bicop, levels: Iterable[float] = TCF_LEVELS) -> float:
    """Wald-type distance between empirical and model upper tail concentration."""
    n = len(u)
    qs = np.asarray(list(levels), dtype=float)
    emp = np.array([np.mean((u[:, 0] > q) & (u[:, 1] > q)) for q in qs])
    model = 1.0 - 2.0 * qs + bicop.cdf(np.column_stack([qs, qs]))
    model = np.clip(model, 0.0, 1.0)
    var = (model * (1.0 - model) + 1.0 / n) / n
    return float(np.sum((emp - model) ** 2 / var))


def cross_validate(u: np.ndarray, cands: list[Candidate], folds: int = 5, seed: int = 0) -> None:
    """Fill ``cv_loglik`` (sum over folds of the out-of-sample log-likelihood)."""
    n = len(u)
    idx = np.random.default_rng(seed).permutation(n)
    parts = np.array_split(idx, folds)
    for c in cands:
        total = 0.0
        try:
            for k in range(folds):
                test = parts[k]
                train = np.concatenate([parts[j] for j in range(folds) if j != k])
                b = pv.Bicop(family=c.family, rotation=c.rotation)
                if c.family != F.indep:
                    b.fit(u[train], controls=pv.FitControlsBicop(family_set=[c.family]))
                total += float(b.loglik(u[test]))
            c.cv_loglik = total
        except RuntimeError:
            c.cv_loglik = -math.inf


def score(c: Candidate, criterion: str) -> float:
    """Lower is better; a NaN value (numerical failure) ranks last."""
    if criterion == "loglik":
        v = -c.loglik
    elif criterion == "aic":
        v = c.aic
    elif criterion == "bic":
        v = c.bic
    elif criterion == "mbic":
        v = c.mbic
    elif criterion == "cv":
        v = -c.cv_loglik
    elif criterion == "tcf":
        v = c.tcf
    else:
        raise ValueError(criterion)
    return math.inf if math.isnan(v) else v


def rank(cands: list[Candidate], criterion: str, hybrid_delta: float = HYBRID_DELTA_BIC) -> list[Candidate]:
    if criterion == "hybrid":
        best = min(score(c, "bic") for c in cands)
        feasible = [c for c in cands if score(c, "bic") - best <= hybrid_delta]
        return sorted(feasible, key=lambda c: score(c, "tcf")) + sorted(
            [c for c in cands if score(c, "bic") - best > hybrid_delta], key=lambda c: score(c, "bic"))
    return sorted(cands, key=lambda c: score(c, criterion))


@dataclass
class Selection:
    bicop: pv.Bicop
    criterion: str
    pool: str
    tau: float
    indep_pvalue: float
    independent_by_test: bool
    candidates: list[Candidate] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def label(self) -> str:
        return label(self.bicop.family, self.bicop.rotation)

    @property
    def chosen(self) -> Candidate | None:
        for c in self.candidates:
            if c.bicop is self.bicop:
                return c
        return None

    def as_dict(self) -> dict:
        return {"criterion": self.criterion, "pool": self.pool, "label": self.label,
                "tau": self.tau, "indep_pvalue": self.indep_pvalue,
                "independent_by_test": self.independent_by_test, "seconds": self.seconds,
                "candidates": [c.as_dict() for c in self.candidates]}


def needs_cv(criterion: str) -> bool:
    return criterion == "cv"


def needs_tcf(criterion: str) -> bool:
    return criterion in ("tcf", "hybrid")


def evaluate_extra(u: np.ndarray, cands: list[Candidate], criteria: Iterable[str], cv_folds: int = 5,
                   seed: int = 0, tcf_levels: Iterable[float] = TCF_LEVELS) -> None:
    crits = set(criteria)
    if any(needs_tcf(c) for c in crits):
        for c in cands:
            c.tcf = tail_concentration_stat(u, c.bicop, tcf_levels)
    if any(needs_cv(c) for c in crits):
        cross_validate(u, cands, cv_folds, seed)


def select(u: np.ndarray, pool: str = "par", criterion: str = "bic", indep_alpha: float | None = None,
           preselect: bool = True, psi0: float = 0.9, cv_folds: int = 5, seed: int = 0,
           tcf_levels: Iterable[float] = TCF_LEVELS, hybrid_delta: float = HYBRID_DELTA_BIC,
           always_fit: bool = False) -> Selection:
    """Select one pair copula for the pseudo-observations ``u`` (n x 2).

    ``indep_alpha``: if given, Kendall's tau independence test is applied first
    and the independence copula is returned when it is not rejected.
    """
    if criterion not in CRITERIA:
        raise ValueError(f"criterion must be one of {CRITERIA}")
    t0 = time.perf_counter()
    tau, _, pval = independence_test(u)
    by_test = indep_alpha is not None and pval >= indep_alpha
    cands: list[Candidate] = []
    if by_test and not always_fit:
        bicop = pv.Bicop()
    else:
        cands = fit_candidates(u, pool, preselect, psi0)
        evaluate_extra(u, cands, [criterion], cv_folds, seed, tcf_levels)
        bicop = pv.Bicop() if by_test else rank(cands, criterion, hybrid_delta)[0].bicop
    return Selection(bicop, criterion, pool if isinstance(pool, str) else "custom", tau, pval, by_test,
                     cands, time.perf_counter() - t0)


def select_all_criteria(u: np.ndarray, pool: str = "par", criteria: Iterable[str] = CRITERIA, preselect: bool = True,
                        psi0: float = 0.9, cv_folds: int = 5, seed: int = 0,
                        tcf_levels: Iterable[float] = TCF_LEVELS, hybrid_delta: float = HYBRID_DELTA_BIC
                        ) -> tuple[list[Candidate], dict[str, Candidate]]:
    """Fit the pool once and return the winner under every criterion."""
    cands = fit_candidates(u, pool, preselect, psi0)
    crits = list(criteria)
    evaluate_extra(u, cands, crits, cv_folds, seed, tcf_levels)
    return cands, {c: rank(cands, c, hybrid_delta)[0] for c in crits}


def subset(cands: list[Candidate], pool: str) -> list[Candidate]:
    """Candidates of a (sub)pool, so that one fit of the largest pool serves every pool."""
    allowed = set(candidates(pool))
    return [c for c in cands if (c.family, c.rotation) in allowed]
