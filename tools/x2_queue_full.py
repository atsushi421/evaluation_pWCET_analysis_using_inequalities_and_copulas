#!/usr/bin/env python3
"""X2: the EKF callback (cb1) with a full measurement queue, an input that no training window contains.

The estimators are trained on the steady-state windows of the Autoware campaign (bench_warm1, windows 0-9 by
default) and compared with the invocations of the queue-full replays whose pose-update loop runs its static bound
of 5 iterations (the relay ipoint/autoware/tools/pose_burst_relay.py keeps the queue full). Every estimate is stored
as a ratio to the queue-full median, to the queue-full maximum, and to the steady-state reference. Entries already
in the output are kept, so a rerun resumes; ONLY=<method,...> recomputes the listed methods. Run from the
repository root and summarize with tools/x2_summary.py.

    .venv/bin/python tools/x2_queue_full.py ipoint/autoware/traces/x2_queuefull/bench_warm1 results/x2/x2_cb1.json
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, ".")
sys.path.insert(0, "tools")
from estimation import tree  # noqa: E402
from estimation.data import Bench  # noqa: E402
from chb_cop_from_schema import run_e2e  # noqa: E402

NORMAL = "ipoint/autoware/traces/autoware/bench_warm1"
POSE = "EKFLocalizer::timer_callback.if3.then.L1.body"
METHODS = ("E2E-CHB", "E2E-MEMIK", "E2E-CANTELLI", "E2E-EVT-PoT", "CHB-IND", "CHB-IND@max", "CHB-COMONO")


def queue_full(qdir: str):
    """The queue-full replays, their pose-update counts per invocation, and the invocations at the bound."""
    qb = Bench(qdir, "cb1")
    cnt = qb.per_run_counts(POSE, 0, len(qb.e2e_all))
    return qb, cnt, qb.e2e_all[(cnt == 5) & qb._clean_e2e_mask]


def one(qdir: str, w: int, m: str):
    nb = Bench(NORMAL, "cb1")
    full = queue_full(qdir)[2]
    kmed, kmax = float(np.median(full)), float(full.max())
    nref = nb.references(tree.P_EVAL)["censored"]
    lo, hi = nb.window_bounds(w)
    if m.startswith("E2E-"):
        est, _ = run_e2e(m, nb.e2e_window(lo, hi), "cb1", w)
    else:
        est, _ = tree.decomposed_estimate(nb, m, w, n_mc=int(1e7))
    print(f"w{w}/{m}", " ".join(f"{est[p] / kmed:.3f}" for p in tree.P_EVAL), flush=True)
    return f"w{w}/{m}", {"vs_full_median": {str(p): est[p] / kmed for p in tree.P_EVAL},
                         "vs_full_max": {str(p): est[p] / kmax for p in tree.P_EVAL},
                         "vs_normal_ref": {str(p): est[p] / nref[p] for p in tree.P_EVAL}}


def main():
    qdir, out_path = sys.argv[1:3]
    wins = [int(w) for w in sys.argv[3].split(",")] if len(sys.argv) > 3 else list(range(10))
    out = json.load(open(out_path)) if os.path.exists(out_path) else {}
    nb = Bench(NORMAL, "cb1")
    qb, cnt, full = queue_full(qdir)
    nref = nb.references(tree.P_EVAL)["censored"]
    out["queue_full"] = {"runs": int(len(qb.e2e_all)), "pose_count_hist": np.bincount(cnt).tolist(),
                         "n_full": int(len(full)), "median_us": float(np.median(full)) / 1e3,
                         "max_us": float(full.max()) / 1e3, "normal_median_us": float(np.median(nb.e2e_all)) / 1e3,
                         "normal_ref_us": {str(p): nref[p] / 1e3 for p in tree.P_EVAL}}
    only = os.environ.get("ONLY")
    methods = tuple(only.split(",")) if only else METHODS
    todo = [(qdir, w, m) for w in wins for m in methods if only or f"w{w}/{m}" not in out]
    if todo:
        with ProcessPoolExecutor(int(os.environ.get("WORKERS", "8"))) as ex:
            for key, v in ex.map(one, *zip(*todo)):
                out[key] = v
                json.dump(out, open(out_path, "w"), indent=1)
    json.dump(out, open(out_path, "w"), indent=1)


if __name__ == "__main__":
    main()
