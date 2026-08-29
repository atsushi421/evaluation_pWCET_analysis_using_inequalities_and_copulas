"""Candidate pair-copula families, candidate pools and tail-dependence coefficients.

Families, rotations and parameter orders follow pyvinecopulib (vinecopulib):
rotation 180 is the survival copula (upper and lower tails swapped), rotations
90 and 270 model negative dependence and place their tails in the off-diagonal
corners, so both diagonal tail-dependence coefficients are zero for them.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np
import pyvinecopulib as pv

F = pv.BicopFamily

ROTATABLE = frozenset({F.clayton, F.gumbel, F.joe, F.bb1, F.bb6, F.bb7, F.bb8, F.tawn})
ROTATIONS = (0, 90, 180, 270)

_VC15 = [F.gaussian, F.student, F.frank, F.gumbel, F.clayton, F.joe]
_PAR = [F.indep, F.gaussian, F.student, F.clayton, F.gumbel, F.frank, F.joe,
        F.bb1, F.bb6, F.bb7, F.bb8, F.tawn]
POOLS: dict[str, list[pv.BicopFamily]] = {
    # family set of vinecopulas 2.0.3 (copulas 1..15): no independence, BB or Tawn family
    "vc15": _VC15,
    # every parametric family of pyvinecopulib 0.7.6
    "par": _PAR,
    # parametric families plus the nonparametric TLL copula
    "all": _PAR + [F.tll],
}

UPPER_TAIL_FAMILIES = frozenset({F.student, F.gumbel, F.joe, F.bb1, F.bb6, F.bb7, F.bb8, F.tawn})


def label(family: pv.BicopFamily, rotation: int = 0) -> str:
    return family.name if rotation == 0 else f"{family.name}{rotation}"


def parse_label(text: str) -> tuple[pv.BicopFamily, int]:
    for rot in (270, 180, 90):
        if text.endswith(str(rot)):
            return F.__members__[text[: -len(str(rot))]], rot
    return F.__members__[text], 0


def resolve_pool(pool: str | Iterable[pv.BicopFamily]) -> list[pv.BicopFamily]:
    return list(POOLS[pool]) if isinstance(pool, str) else list(pool)


def candidates(pool: str | Iterable[pv.BicopFamily], tau: float | None = None) -> list[tuple[pv.BicopFamily, int]]:
    """(family, rotation) pairs of a pool.

    With ``tau`` given, rotatable families keep only the rotations whose
    dependence has the sign of Kendall's tau (0/180 for tau >= 0, 90/270
    otherwise), the preselection used by Dissmann et al. (2013).
    """
    out = []
    for fam in resolve_pool(pool):
        if fam in ROTATABLE:
            rots: Sequence[int] = ROTATIONS if tau is None else ((0, 180) if tau >= 0 else (90, 270))
        else:
            rots = (0,)
        out.extend((fam, r) for r in rots)
    return out


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction of the regularized incomplete beta (Numerical Recipes)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-16:
            break
    return h


def betainc_reg(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def student_t_cdf(x: float, nu: float) -> float:
    """CDF of Student's t with ``nu`` degrees of freedom (no scipy dependency)."""
    t2 = x * x
    ib = betainc_reg(nu / 2.0, 0.5, nu / (nu + t2))
    return 1.0 - 0.5 * ib if x >= 0 else 0.5 * ib


def tail_dependence(family: pv.BicopFamily, rotation: int, params) -> tuple[float, float]:
    """Analytic (lambda_L, lambda_U) of a pair copula; (nan, nan) for TLL.

    Formulas from Joe (2014, Ch. 4) with vinecopulib's parameter order:
    Student (rho, nu), BB1/BB6/BB7/BB8 (theta, delta), Tawn (psi1, psi2, theta).
    """
    p = np.asarray(params, dtype=float).ravel()
    if family in (F.indep, F.gaussian, F.frank):
        lo = up = 0.0
    elif family == F.student:
        rho, nu = p
        lo = up = 2.0 * student_t_cdf(-math.sqrt((nu + 1.0) * (1.0 - rho) / (1.0 + rho)), nu + 1.0)
    elif family == F.clayton:
        th = p[0]
        lo, up = (2.0 ** (-1.0 / th) if th > 0 else 0.0), 0.0
    elif family in (F.gumbel, F.joe):
        lo, up = 0.0, 2.0 - 2.0 ** (1.0 / p[0])
    elif family == F.bb1:
        th, de = p
        lo, up = (2.0 ** (-1.0 / (th * de)) if th > 0 else 0.0), 2.0 - 2.0 ** (1.0 / de)
    elif family == F.bb6:
        th, de = p
        lo, up = 0.0, 2.0 - 2.0 ** (1.0 / (th * de))
    elif family == F.bb7:
        th, de = p
        lo, up = 2.0 ** (-1.0 / de), 2.0 - 2.0 ** (1.0 / th)
    elif family == F.bb8:
        th, de = p
        lo, up = 0.0, (2.0 - 2.0 ** (1.0 / th)) if de >= 1.0 else 0.0
    elif family == F.tawn:
        psi1, psi2, th = p
        lo, up = 0.0, psi1 + psi2 - (psi1 ** th + psi2 ** th) ** (1.0 / th)
    elif family == F.tll:
        return (math.nan, math.nan)
    else:
        raise ValueError(f"unknown family {family}")
    if rotation == 180:
        lo, up = up, lo
    elif rotation in (90, 270):
        lo = up = 0.0
    return (lo, up)


def tail_dependence_of(bicop: pv.Bicop) -> tuple[float, float]:
    return tail_dependence(bicop.family, bicop.rotation, bicop.parameters)


def tail_concentration(bicop: pv.Bicop, q: float) -> tuple[float, float]:
    """Lower and upper tail concentration at level q, computed from the CDF.

    (C(1-q, 1-q) / (1-q), (1 - 2q + C(q, q)) / (1-q)); their limits for
    q -> 1 are lambda_L and lambda_U, which makes this usable for TLL.
    """
    c_hi = float(bicop.cdf(np.array([[q, q]]))[0])
    c_lo = float(bicop.cdf(np.array([[1.0 - q, 1.0 - q]]))[0])
    return (c_lo / (1.0 - q), (1.0 - 2.0 * q + c_hi) / (1.0 - q))


def has_upper_tail_dependence(bicop: pv.Bicop, tol: float = 1e-9) -> bool:
    lo, up = tail_dependence_of(bicop)
    if math.isnan(up):
        return tail_concentration(bicop, 1.0 - 1e-4)[1] > 0.05
    return up > tol
