#!/usr/bin/env python3
"""X3 summary: unsafe-window probability per mixing rate rho from the per-K estimates of
tools/x3_mixing_sweep.py. P(unsafe | rho) = sum_K Binom(K; n, rho) * (share of the K-windows whose estimate
is below the mixture reference at p, among the windows with an estimate;
the share of windows without one, e.g. every block size rejected by EVT-BM, is shown in brackets). Missing K values use the nearest smaller K that was
estimated (fewer adversarial runs never raise an estimate much, so this errs toward unsafe).

    .venv/bin/python tools/x3_summary.py qsort-exam results/x3/x3_qsort-exam.json > results/tables/x3_mixing_qsort-exam.md

Run from the repository root.
"""
import json, sys
import numpy as np
from scipy.stats import binom
sys.path.insert(0, ".")
from estimation.data import Bench  # noqa: E402

N = 10_000
RHOS = (0.0, 1e-6, 3e-6, 1e-5, 3e-5, 1e-4, 3e-4, 1e-3)
PS = ("0.0001", "1e-05")


def mixture_ref(r, k, rho, p):
    """Smallest x with (1-rho) S_r(x) + rho S_k(x) <= p (empirical survival functions)."""
    xs = np.unique(np.r_[r, k])
    sr = 1 - np.searchsorted(np.sort(r), xs, side="right") / len(r)
    sk = 1 - np.searchsorted(np.sort(k), xs, side="right") / len(k)
    return float(xs[np.argmax((1 - rho) * sr + rho * sk <= p)])


def load(bench, paths):
    """End-to-end times of the uniform (r) and killer (k) campaigns, and the estimates as
    method -> K -> [{p: value}]."""
    pre = "" if bench == "qsort-exam" else bench + "_"
    rb, kb = Bench(f"results/e214/{pre}rand", bench), Bench(f"results/e214/{pre}killer", bench)
    r, k = rb.e2e_all[rb._clean_e2e_mask], kb.e2e_all[kb._clean_e2e_mask]
    est = {}
    for path in paths:
        for key, rec in json.load(open(path)).items():
            K = int(key.split("/")[0][1:])
            for m, v in rec.items():
                est.setdefault(m, {}).setdefault(K, []).append(v)
    return r, k, est


def unsafe_prob(est_m, ref, rho, p):
    """(unsafe share, median estimate / reference) among the windows with an estimate, or (None, None) when no
    window has one, and the share of windows without an estimate, of one method at rho."""
    pk = binom.pmf(np.arange(N + 1), N, rho)
    Ks = sorted(est_m)
    unsafe, ratio, missing = 0.0, 0.0, 0.0
    for K in range(N + 1):
        if pk[K] < 1e-12:
            continue
        kk = max([x for x in Ks if x <= K], default=Ks[0])
        vals = np.array([v[p] for v in est_m[kk]], dtype=float)
        ok = vals[np.isfinite(vals)]
        missing += pk[K] * (1 - len(ok) / len(vals))
        if len(ok):
            w = pk[K] * len(ok) / len(vals)
            unsafe += w * np.mean(ok < ref)
            ratio += w * np.median(ok) / ref
    have = 1 - missing
    return (unsafe / have, ratio / have, missing) if have > 0 else (None, None, missing)


def main():
    bench, paths = sys.argv[1], sys.argv[2:]
    r, k, est = load(bench, paths)
    methods = sorted(est, key=lambda m: (not m.startswith("E2E"), m))
    rmed, kmed = float(np.median(r)), float(np.median(k))
    print(f"## {bench}: killer median = {kmed / rmed:.2f} x random median; windows per K: "
          + ", ".join(f"{m} {min(len(v) for v in est[m].values())}" for m in methods))
    for p in PS:
        print(f"\n### p = {p}: unsafe-window probability (median estimate / reference)\n")
        print("| rho | P(K>=1) | reference / random median | " + " | ".join(methods) + " |")
        print("|---" * (3 + len(methods)) + "|")
        for rho in RHOS:
            ref = mixture_ref(r, k, rho, float(p))
            cells = []
            for m in methods:
                unsafe, ratio, missing = unsafe_prob(est[m], ref, rho, p)
                cell = "-" if unsafe is None else f"{unsafe:.2f} ({ratio:.2f})"
                cells.append(cell + (f" [no estimate {missing:.0%}]" if missing > 0.005 else ""))
            print(f"| {rho:g} | {1 - (1 - rho) ** N:.2f} | {ref / rmed:.2f} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
