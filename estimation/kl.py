"""KL-inverted Hoeffding bound (Hoeffding 1963, Theorem 1) for [0, 1] means.

For z_1..z_n iid in [0, 1] with sample mean q, the true mean mu satisfies
mu <= kl_inv_upper(q, tau) with probability >= 1 - e^{-n tau}, where
kl(q||mu) is the binary KL divergence and tau = ln(1/delta)/n. Verified
against Monte-Carlo coverage in the paper repo notes/verify_kl_bound/.
"""
import numpy as np


def kl(q: np.ndarray, p: np.ndarray) -> np.ndarray:
    q = np.clip(q, 1e-300, 1 - 1e-16)
    p = np.clip(p, 1e-300, 1 - 1e-16)
    return q * np.log(q / p) + (1 - q) * np.log((1 - q) / (1 - p))


def kl_inv_upper(q, tau: float) -> np.ndarray:
    """sup{mu in [q, 1) : kl(q||mu) <= tau} by simultaneous bisection."""
    q = np.atleast_1d(np.asarray(q, dtype=float))
    lo = q.copy()
    hi = np.full_like(q, 1 - 1e-12)
    for _ in range(80):
        m = 0.5 * (lo + hi)
        above = kl(q, m) > tau
        hi = np.where(above, m, hi)
        lo = np.where(above, lo, m)
    return 0.5 * (lo + hi)
