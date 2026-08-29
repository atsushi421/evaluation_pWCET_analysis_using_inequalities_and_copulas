#!/usr/bin/env python3
"""Consistency checks of a parsed trace (tests/test_roundtrip.sh uses it).

    ipoint_check.py --schema schema.json --trace-dir DIR --parsed OUT [--max-gap-ns 500]

Checks: no implicit closes / unmatched exits / core migrations, the end-to-end
time derived from the trace equals the one in summary.bin, the harness time
exceeds the end-to-end time by a small bounded gap, every unit sample is
non-negative, the number of samples of each unit equals its hit count, and
loop iteration counts never exceed the static bound.
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--trace-dir", required=True)
    ap.add_argument("--parsed", required=True)
    ap.add_argument("--max-gap-ns", type=float, default=500.0)
    a = ap.parse_args(argv)
    schema = Schema.from_json(a.schema)
    with open(os.path.join(a.trace_dir, "meta.json")) as f:
        meta = json.load(f)
    with open(os.path.join(a.parsed, "stats.json")) as f:
        st = json.load(f)
    tick_ns = 1e9 / meta["tsc_hz_start"]
    summary = load_summary(a.trace_dir, meta)
    n = st["runs_parsed"]
    fails = []

    def check(cond, msg):
        if not cond:
            fails.append(msg)

    check(sum(st["implicit_closes"].values()) == 0, f"implicit closes: {st['implicit_closes']}")
    check(sum(st["unmatched_exits"].values()) == 0, f"unmatched exits: {st['unmatched_exits']}")
    check(st["aux_changes"] == 0, f"core changed within {st['aux_changes']} runs")
    check(meta["migrations"] == 0 and meta["total_overflow"] == 0, "harness reported migrations or buffer overflow")
    e2e = np.load(os.path.join(a.parsed, "e2e.npy"))
    e2e_all = np.load(os.path.join(a.parsed, "e2e_all.npy"))
    harness = np.load(os.path.join(a.parsed, "harness_all.npy"))
    check(np.array_equal(e2e, e2e_all[:n]), "e2e from trace differs from summary.bin")
    gap = (harness[:n] - e2e) * tick_ns
    check(gap.min() >= 0, f"harness time below e2e time (min gap {gap.min():.1f} ns)")
    check(np.median(gap) <= a.max_gap_ns, f"median harness-e2e gap {np.median(gap):.1f} ns exceeds {a.max_gap_ns}")
    hits = summary["hits"][:n]
    for uid, us in st["units"].items():
        u = schema.by_uid()[uid]
        if u.kind == "branch":
            continue
        arr = np.load(os.path.join(a.parsed, "units", f"{uid}.npy"))
        check(arr.min() >= 0, f"{uid}: negative sample")
        expected = int(hits[:, u.entry].sum())
        check(len(arr) == expected, f"{uid}: {len(arr)} samples but {expected} entry hits")
        if u.kind == "loop" and u.bound is not None and "iters_max" in us:
            check(us["iters_max"] <= u.bound, f"{uid}: observed {us['iters_max']} iterations > bound {u.bound}")
        if uid in st["units"] and "self_min" in us:
            check(us["self_min"] >= 0, f"{uid}: negative self time {us['self_min']}")
    for f_ in fails:
        print("FAIL:", f_)
    print(f"{meta['bench']}: {len(fails)} failures over {n} runs, {len(st['units'])} units")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
