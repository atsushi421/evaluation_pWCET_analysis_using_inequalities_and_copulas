#!/usr/bin/env python3
"""Merge chunked ipoint_parse.py outputs (--skip-runs / --max-runs over consecutive run ranges) into one directory.

    merge_parsed.py --out OUT CHUNK0 CHUNK1 ...      (chunks in run order)

Per-unit and per-branch arrays and e2e.npy are concatenated in chunk order, the arrays derived from summary.bin
(e2e_all, harness_all, runs_all, hits_all) are taken from the first chunk, and stats.json is recomputed from the
merged arrays as ipoint_parse.py computes it. Every chunk must have the same files and the same caller lists.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys

import numpy as np


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("chunks", nargs="+")
    a = ap.parse_args(argv)
    files = [sorted(os.path.relpath(p, c) for sub in ("units", "branches") for p in glob.glob(os.path.join(c, sub, "*")))
             for c in a.chunks]
    if any(f != files[0] for f in files):
        sys.exit("chunks differ in their unit or branch files")
    for sub in ("units", "branches"):
        os.makedirs(os.path.join(a.out, sub), exist_ok=True)
    for rel in files[0] + ["e2e.npy"]:
        if rel.endswith(".json"):
            docs = [json.load(open(os.path.join(c, rel))) for c in a.chunks]
            if any(d != docs[0] for d in docs):
                sys.exit(f"{rel} differs between chunks")
            shutil.copy(os.path.join(a.chunks[0], rel), os.path.join(a.out, rel))
        else:
            np.save(os.path.join(a.out, rel), np.concatenate([np.load(os.path.join(c, rel)) for c in a.chunks]))
    for rel in ("e2e_all.npy", "harness_all.npy", "runs_all.npy", "hits_all.npy"):
        if os.path.exists(os.path.join(a.chunks[0], rel)):
            shutil.copy(os.path.join(a.chunks[0], rel), os.path.join(a.out, rel))

    sts = [json.load(open(os.path.join(c, "stats.json"))) for c in a.chunks]
    st = dict(sts[0])
    st["runs_parsed"] = sum(s["runs_parsed"] for s in sts)
    st["aux_changes"] = sum(s["aux_changes"] for s in sts)
    for key in ("implicit_closes", "unmatched_exits"):
        tot: dict = {}
        for s in sts:
            for k, v in s[key].items():
                tot[k] = tot.get(k, 0) + v
        st[key] = tot
    load = lambda uid, suffix="": np.load(os.path.join(a.out, "units", f"{uid}{suffix}.npy"))  # noqa: E731
    units = {}
    for uid, u0 in sts[0]["units"].items():
        u = dict(u0)
        if u0.get("kind") == "branch":
            counts = [s["units"].get(uid, {}).get("alt_counts", []) for s in sts]
            tot = np.zeros(max(map(len, counts)), dtype=np.int64)
            for c in counts:
                tot[:len(c)] += c
            u["alt_counts"] = tot.tolist()
        if "n" in u0:
            arr = load(uid)
            u.update({"n": int(len(arr)), "min": float(arr.min()), "median": float(np.median(arr)),
                      "mean": float(arr.mean()), "p99": float(np.quantile(arr, 0.99)), "max": float(arr.max()),
                      "median_ns": float(np.median(arr)) * (1.0 if st["unit"] == "ns" else st["tick_ns"])})
            if "self_median" in u0:
                s_arr = load(uid, ".self")
                u.update({"self_median": float(np.median(s_arr)), "self_min": float(s_arr.min())})
            if "iters_max" in u0:
                it = load(uid, ".iters")
                u.update({"iters_max": int(it.max()), "iters_mean": float(it.mean())})
        units[uid] = u
    st["units"] = units
    with open(os.path.join(a.out, "stats.json"), "w") as f:
        json.dump(st, f, indent=1)
    print(f"merged {len(a.chunks)} chunks, {st['runs_parsed']} runs, {len(units)} units into {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
