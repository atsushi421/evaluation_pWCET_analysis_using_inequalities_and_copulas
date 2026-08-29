"""Copula modeling for CHB-COP: family pools, selection criteria, R-vines and MC composition.

Requires pyvinecopulib (see requirements.txt). Import the submodules from the
repository root like the other modules of this repository::

    from copula import select, vine, compose, families
    sel = select.select(u, pool="par", criterion="bic")
    fit = vine.fit_vine(U, pool="par", criterion="bic", indep_alpha=0.05)
    res = compose.compose(fit.vinecop, icdfs, exceed_probs=[1e-4, 1e-5, 1e-6])
"""
from . import families, select, vine, compose  # noqa: F401
from .families import POOLS, candidates, label, parse_label, tail_concentration, tail_dependence, tail_dependence_of
from .select import CRITERIA, NATIVE_CRITERIA, Candidate, Selection, independence_test, kendall_tau, pseudo_obs
from .vine import VineFit, fit_vine, fit_vine_native, swap_arguments, to_matrix
from .compose import ComposeResult, empirical_quantiles, icdf_from_curve, icdf_from_pwcet_dict, icdf_from_samples

__all__ = [
    "families", "select", "vine", "compose",
    "POOLS", "candidates", "label", "parse_label", "tail_concentration", "tail_dependence", "tail_dependence_of",
    "CRITERIA", "NATIVE_CRITERIA", "Candidate", "Selection", "independence_test", "kendall_tau", "pseudo_obs",
    "VineFit", "fit_vine", "fit_vine_native", "swap_arguments", "to_matrix",
    "ComposeResult", "empirical_quantiles", "icdf_from_curve", "icdf_from_pwcet_dict", "icdf_from_samples",
]
