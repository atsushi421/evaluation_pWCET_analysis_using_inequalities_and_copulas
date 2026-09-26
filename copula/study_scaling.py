#!/usr/bin/env python3
"""Cost of the copula stage against the number of parts (experiment N2 of the paper repo's answers_draft/09).

Synthetic parts: n = 1e4 runs of m parts coupled by a Gaussian copula, either dense (every pair
Kendall tau 0.2, so no pair passes the independence pre-test and every pair copula is selected over the
whole pool) or sparse (an AR(1) chain with lag-one tau 0.3, so most pairs of the higher trees are
independent). Per m: the time of the R-vine fit of the pipeline (pool par, BIC, independence pre-test
alpha 0.05), the number of non-independent pair copulas, and the time of the Monte-Carlo composition
with N = 1e6 draws (the pipeline uses 1e8 for the benchmarks and 1e7 for Autoware; the time is linear in N).

    .venv/bin/python -m copula.study_scaling [--dims 2,4,8,16,24,32] [--workers 6] [--out copula/results]
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from copula import compose as cp
from copula import select as sel
from copula import vine

N_TRAIN = 10_000
N_MC = 1_000_000


def correlation(m: int, kind: str) -> np.ndarray:
    rho = lambda tau: np.sin(np.pi * tau / 2)  # noqa: E731  Kendall's tau of a Gaussian copula
    if kind == "dense":
        c = np.full((m, m), rho(0.2))
    else:
        r = rho(0.3)
        c = r ** np.abs(np.subtract.outer(np.arange(m), np.arange(m)))
    np.fill_diagonal(c, 1.0)
    return c


def task(m: int, kind: str) -> dict:
    rng = np.random.default_rng([m, len(kind)])
    z = rng.multivariate_normal(np.zeros(m), correlation(m, kind), size=N_TRAIN)
    x = np.exp(0.3 * z)                               # lognormal parts
    u = sel.pseudo_obs(x)
    t0 = time.perf_counter()
    fit = vine.fit_vine(u, pool="par", criterion="bic", indep_alpha=0.05)
    t_fit = time.perf_counter() - t0
    icdfs = [cp.icdf_from_samples(x[:, i]) for i in range(m)]
    t0 = time.perf_counter()
    cp.compose(fit.vinecop, icdfs, [1e-4], n_samples=N_MC, seed=1)
    t_mc = time.perf_counter() - t0
    pairs = m * (m - 1) // 2
    return {"m": m, "kind": kind, "fit_s": t_fit, "mc_s_per_1e6": t_mc, "pairs": pairs,
            "non_indep": pairs - fit.n_independent()}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dims", default="2,4,8,16,24,32")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default="copula/results")
    a = ap.parse_args()
    jobs = [(int(m), k) for k in ("sparse", "dense") for m in a.dims.split(",")]
    with ProcessPoolExecutor(a.workers) as ex:
        res = list(ex.map(task, *zip(*jobs)))
    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(os.path.join(a.out, "scaling.json"), "w"), indent=1)
    lines = ["N2: R-vine fit (pool par, BIC, independence pre-test) and Monte-Carlo composition time on one core "
             "of the Xeon Silver 4216, n = 1e4 runs; MC time per 1e6 draws (linear in N).\n",
             "| coupling | m | pair copulas | non-independent | fit [s] | MC per 1e6 [s] | MC 1e8 [s] (x100) |",
             "|---|---|---|---|---|---|---|"]
    for r in res:
        lines.append(f"| {r['kind']} | {r['m']} | {r['pairs']} | {r['non_indep']} | {r['fit_s']:.1f} | "
                     f"{r['mc_s_per_1e6']:.2f} | {100 * r['mc_s_per_1e6']:.0f} |")
    text = "\n".join(lines) + "\n"
    open(os.path.join(a.out, "scaling.md"), "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
