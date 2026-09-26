#!/usr/bin/env python3
"""E2-8: serial dependence of the training windows (R2-4).

Per benchmark or callback and training window: lag-1 autocorrelation and effective sample size (Geyer's
initial positive sequence, lags up to 200) of the end-to-end time X and of the moment term
f(X) = tanh(X / d)^k at the (d, k) that E2E-CHB selected at --p in that window. The moment term decides the
bound and the finite-sample certificate; the table reports its n_eff next to that of X.

    .venv/bin/python tools/neff_table.py --traces ipoint/traces_full --results results/estimates \
        [--benches ...] [--p 0.0001] [--out results/tables/neff.md]
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from estimation.data import Bench  # noqa: E402

BENCHES = "bsort100,fir,matmult,edn,ndes,st,lms,prime,cnt,ludcmp,select,qsort-exam"


def neff(y: np.ndarray, max_lag: int = 200) -> tuple[float, float]:
    y = y - y.mean()
    v = y.var()
    if v == 0:
        return float(len(y)), 0.0
    r = [float(np.dot(y[:-k], y[k:]) / ((len(y) - k) * v)) for k in range(1, max_lag + 1)]
    s = 0.0
    for i in range(0, max_lag - 1, 2):
        if r[i] + r[i + 1] <= 0:
            break
        s += r[i] + r[i + 1]
    return len(y) / (1 + 2 * s), r[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--traces", default="ipoint/traces_full")
    ap.add_argument("--results", default="results/estimates")
    ap.add_argument("--benches", default=BENCHES)
    ap.add_argument("--p", default="0.0001")
    ap.add_argument("--out", default="results/tables/neff.md")
    a = ap.parse_args()
    lines = [f"E2-8: lag-1 autocorrelation r1 and effective sample size n_eff (Geyer) of the end-to-end time X and "
             f"of the moment term f(X) = tanh(X/d)^k at the (d, k) of E2E-CHB at p={a.p}, per training window "
             "(n = 1e4): median over windows [min, max].\n",
             "| series | windows | r1(X) | n_eff(X) | r1(f(X)) | n_eff(f(X)) |", "|---|---|---|---|---|---|"]
    for b in a.benches.split(","):
        bench = Bench(a.traces, b)
        res = json.load(open(os.path.join(a.results, f"{b}.json")))
        rows = []
        for w, e in res["windows"].items():
            c = e.get("E2E-CHB", {}).get("meta", {}).get("choice", {}).get(a.p)
            if not c or c.get("d") is None:
                continue
            lo, hi = e["runs"] if "runs" in e else bench.window_bounds(int(w), res["window_size"])
            x = bench.e2e_window(lo, hi)
            shift = float(x.min()) - 1.0 if x.min() <= 0 else 0.0      # chb._shift
            nx, rx = neff(x)
            nf, rf = neff(np.tanh((x - shift) / c["d"]) ** c["k"])
            rows.append((rx, nx, rf, nf))
        if not rows:
            continue
        v = np.array(rows)
        f = lambda j, d: f"{np.median(v[:, j]):.{d}f} [{v[:, j].min():.{d}f}, {v[:, j].max():.{d}f}]"  # noqa: E731
        lines.append(f"| {b} | {len(v)} | {f(0, 3)} | {f(1, 0)} | {f(2, 3)} | {f(3, 0)} |")
    text = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
