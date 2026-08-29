#!/usr/bin/env python3
"""Path-coverage statistics (experiment E2-4) from the per-run hit counts in
summary.bin of a COVERAGE (or TIMING) build.

    ipoint_coverage.py --schema schema_full.json --dir DIR [--train 10000] [--out coverage.json]

For every branch: alternatives observed within the first --train runs and
within all runs, against the static number of alternatives. For every loop:
maximum body iterations per run (train / all) against the static bound per
run (product of the bounds of the loop and its enclosing loops). For the whole
program: number of distinct path signatures (vector of alternative and loop
body hit counts) and the first run at which every alternative observed in the
whole campaign had been observed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ipoint_parse import load_summary  # noqa: E402
from ipoint_schema import Schema  # noqa: E402


def static_iters_per_run(schema: Schema, uid: str):
    by = schema.by_uid()
    prod = 1
    u = by[uid]
    while u is not None:
        if u.kind == "loop":
            if u.bound is None:
                return None
            prod *= u.bound
        u = by[u.parent] if u.parent else None
    return prod


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--train", type=int, default=10000)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    schema = Schema.from_json(a.schema)
    with open(os.path.join(a.dir, "meta.json")) as f:
        meta = json.load(f)
    s = load_summary(a.dir, meta)
    hits = s["hits"]
    n = len(s)
    train = min(a.train, n)
    by = schema.by_uid()
    res = {"bench": meta["bench"], "runs": n, "train": train, "branches": {}, "loops": {}}

    sig_cols = []
    for u in schema.units:
        if u.kind == "branch":
            alts = [by[c] for c in u.children]
            seen_train = [bool(hits[:train, x.entry].any()) for x in alts]
            seen_all = [bool(hits[:, x.entry].any()) for x in alts]
            first = None
            if all(seen_all):
                firsts = [int(np.argmax(hits[:, x.entry] > 0)) for x in alts]
                first = max(firsts) + 1
            res["branches"][u.uid] = {"static": len(alts), "observed_train": sum(seen_train),
                                      "observed_all": sum(seen_all),
                                      "alternatives": {x.uid: {"train": st, "all": sa, "hits_all": int(hits[:, x.entry].sum())}
                                                       for x, st, sa in zip(alts, seen_train, seen_all)},
                                      "first_run_all_alternatives_seen": first}
            sig_cols += [x.entry for x in alts]
        elif u.kind == "loop":
            body = by[u.children[0]] if u.children else None
            if body is None:
                continue
            col = hits[:, body.entry]
            res["loops"][u.uid] = {"bound": u.bound, "static_iters_per_run": static_iters_per_run(schema, u.uid),
                                   "max_iters_per_run_train": int(col[:train].max()), "max_iters_per_run_all": int(col.max()),
                                   "mean_iters_per_run_all": float(col.mean())}
            sig_cols.append(body.entry)
    sig = np.ascontiguousarray(hits[:, sig_cols]) if sig_cols else np.zeros((n, 0), np.uint32)
    uniq_all = len(np.unique(sig, axis=0)) if n else 0
    uniq_train = len(np.unique(sig[:train], axis=0)) if train else 0
    res["path_signatures"] = {"distinct_train": uniq_train, "distinct_all": uniq_all, "columns": len(sig_cols)}
    firsts = [b["first_run_all_alternatives_seen"] for b in res["branches"].values()]
    res["first_run_all_observed_alternatives_seen"] = max([f for f in firsts if f is not None], default=None)
    res["branches_fully_covered_train"] = sum(1 for b in res["branches"].values() if b["observed_train"] == b["static"])
    res["branches_fully_covered_all"] = sum(1 for b in res["branches"].values() if b["observed_all"] == b["static"])
    text = json.dumps(res, indent=1)
    if a.out:
        with open(a.out, "w") as f:
            f.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
