#!/usr/bin/env python3
"""Distribution-free upper confidence bounds of the (1-p)-quantile from upper order statistics, for comparison
with the KL certificate (results/tables/certification.md). Samples: the estimation part of training window 0
(the window without its first 10 %, as in chb_leaf), so n matches the certificate. The r-th largest of n
observations bounds the (1-p)-quantile with confidence 1 - alpha whenever P(Bin(n, p) <= r - 1) <= alpha; the
largest such r is used, and none exists below p = 1 - alpha^(1/n). Reported relative to the empirical quantile of
all SMI-censored runs, defined as in tools/certification_curve.py.

    .venv/bin/python tools/orderstat.py > results/tables/orderstat.md
"""
import os
import sys

import numpy as np
from scipy.stats import binom

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from estimation.data import Bench  # noqa: E402

BENCHES = "bsort100 fir matmult edn ndes st lms prime cnt ludcmp select qsort-exam".split()
PS, ALPHA = (1e-2, 1e-3, 5e-4), 0.05


def upper_rank(n: int, p: float) -> int:
    """Largest r with P(Bin(n, p) <= r - 1) <= ALPHA, or 0 if none."""
    r = 0
    while binom.cdf(r, n, p) <= ALPHA:
        r += 1
    return r


def main():
    print(f"Upper order statistic of the estimation part of training window 0 (alpha = {ALPHA}) / empirical "
          "quantile of all SMI-censored runs. Cells: rank from the top, ratio.\n")
    print("| bench | n | " + " | ".join(f"p={p:g}" for p in PS) + " |")
    print("|---|---|" + "---|" * len(PS))
    for name in BENCHES:
        b = Bench("ipoint/traces_full", name)
        xs = np.sort(b.e2e_all[b._clean_e2e_mask])
        x = b.e2e_window(*b.window_bounds(0))
        main_part = np.sort(x[max(int(len(x) * 0.1), 2):])
        n, cells = len(main_part), []
        for p in PS:
            r = upper_rank(n, p)
            ref = xs[min(int(np.ceil((1 - p) * len(xs))) - 1, len(xs) - 1)]
            cells.append(f"{r}, {main_part[n - r] / ref:.3f}" if r else "none")
        print(f"| {name} | {n} | " + " | ".join(cells) + " |", flush=True)


if __name__ == "__main__":
    main()
