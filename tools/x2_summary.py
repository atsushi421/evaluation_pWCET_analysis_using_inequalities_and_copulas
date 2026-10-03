#!/usr/bin/env python3
"""X2 summary: for every estimator and training window, the share of queue-full cb1 invocations that exceed the
estimate, to be compared with the nominal exceedance probability p. The header gives the steady-state median and
reference and the per-run average time of one pose update in both conditions, with the self time of the loop
spread over its iterations as in the loop rule (estimation/tree.py).

    .venv/bin/python tools/x2_summary.py ipoint/autoware/traces/x2_queuefull/bench_warm1 results/x2/x2_cb1.json \
        > results/tables/x2_queue_full.md
"""
import json
import sys

import numpy as np

sys.path.insert(0, ".")
from estimation.data import Bench  # noqa: E402

NORMAL = "ipoint/autoware/traces/autoware/bench_warm1"
POSE = "EKFLocalizer::timer_callback.if3.then.L1.body"
LOOP = POSE[:-len(".body")]


def main():
    nb, qb = Bench(NORMAL, "cb1"), Bench(sys.argv[1], "cb1")
    d = json.load(open(sys.argv[2]))
    n = len(qb.e2e_all)
    cnt = qb.per_run_counts(POSE, 0, n)
    at_bound = (cnt == 5) & qb._clean_e2e_mask
    full = np.sort(qb.e2e_all[at_bound])
    kmed = float(np.median(full))
    q_avg = (qb.per_run_totals(POSE, 0, n) + qb.per_run_totals(LOOP, 0, n, "self"))[at_bound] / 5
    ncnt = nb.per_run_counts(POSE, 0, len(nb.e2e_all))
    n_tot = nb.per_run_totals(POSE, 0, len(nb.e2e_all)) + nb.per_run_totals(LOOP, 0, len(nb.e2e_all), "self")
    n_avg = n_tot[ncnt > 0] / ncnt[ncnt > 0]
    ref = nb.references([1e-4])["censored"][1e-4]
    methods = sorted({k.split("/", 1)[1] for k in d if k.startswith("w")}, key=lambda m: (not m.startswith("E2E"), m))
    wins = sorted({k.split("/")[0] for k in d if k.startswith("w")})
    print(f"queue-full invocations {len(full)}, median {kmed / 1e3:.0f} us, max {full[-1] / 1e3:.0f} us; windows {len(wins)}\n")
    print(f"steady state: median {np.median(nb.e2e_all) / 1e3:.0f} us, reference at p = 0.0001 {ref / 1e3:.0f} us; "
          f"per-run average of one pose update: steady state median {np.median(n_avg) / 1e3:.0f} us "
          f"(max {n_avg.max() / 1e3:.0f} us), queue full median {np.median(q_avg) / 1e3:.0f} us (max {q_avg.max() / 1e3:.0f} us)\n")
    for p in ("0.0001", "1e-05"):
        print(f"### p = {p}\n")
        print("| method | estimate / normal reference | estimate / queue-full median | queue-full exceedance (median, max over windows) | windows with exceedance > p |")
        print("|---|---|---|---|---|")
        for m in methods:
            r_ref, r_med, exc = [], [], []
            for w in wins:
                v = d.get(f"{w}/{m}")
                if v is None:
                    continue
                est = v["vs_full_median"][p] * kmed
                r_ref.append(v["vs_normal_ref"][p])
                r_med.append(v["vs_full_median"][p])
                exc.append(1 - np.searchsorted(full, est, side="right") / len(full))
            exc = np.array(exc)
            print(f"| {m} | {np.median(r_ref):.2f} [{min(r_ref):.2f}, {max(r_ref):.2f}] | {np.median(r_med):.2f} [{min(r_med):.2f}, {max(r_med):.2f}] "
                  f"| {np.median(exc):.2%}, {exc.max():.2%} | {int((exc > float(p)).sum())}/{len(exc)} |")
        print()


if __name__ == "__main__":
    main()
