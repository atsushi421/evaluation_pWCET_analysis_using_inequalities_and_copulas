#!/usr/bin/env python3
"""Audit declared loop bounds against the COVERAGE build's per-run counters.

For every loop unit with a static bound, a run violates the bound whenever
its total body iterations exceed loop entries * bound (a sound per-run test:
it can only fire when at least one entry exceeded the bound). This is how the
uint32-wrap violation of prime's trial-division loop was found: 10 of 10^7
runs iterated 103,620 times against the declared 32,767 before the input
domain was restricted to U(0, 65535^2).

Writes <traces>/bounds_audit.json and prints one line per bounded loop.
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ipoint_parse import summary_dtype  # noqa: E402


def audit_bench(bench_dir: str) -> list:
    schema = json.load(open(os.path.join(bench_dir, "schema_full.json")))
    units = {u["uid"]: u for u in schema["units"]}
    meta = json.load(open(os.path.join(bench_dir, "coverage", "meta.json")))
    rows = np.fromfile(os.path.join(bench_dir, "coverage", "summary.bin"),
                       dtype=summary_dtype(meta["max_id"]))
    hits = rows["hits"]
    out = []
    for uid, u in units.items():
        if u["kind"] != "loop" or u.get("bound") is None:
            continue
        body = units.get(uid + ".body")
        if body is None:
            continue
        entries = hits[:, u["entry"]].astype(np.int64)
        iters = hits[:, body["entry"]].astype(np.int64)
        out.append({
            "loop": uid,
            "bound": u["bound"],
            "runs": int(len(rows)),
            "max_total_iters_per_run": int(iters.max()),
            "max_entries_per_run": int(entries.max()),
            "violating_runs": int((iters > entries * u["bound"]).sum()),
        })
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--traces", default="traces")
    ap.add_argument("--bench", default="all")
    a = ap.parse_args()
    if a.bench == "all":
        benches = sorted(d for d in os.listdir(a.traces)
                         if os.path.isfile(os.path.join(a.traces, d, "schema_full.json")))
    else:
        benches = a.bench.split(",")
    report, bad = {}, 0
    for b in benches:
        rows = audit_bench(os.path.join(a.traces, b))
        report[b] = rows
        for r in rows:
            tag = f"VIOLATION x{r['violating_runs']}" if r["violating_runs"] else "ok"
            bad += r["violating_runs"]
            print(f"{b:<11} {r['loop']:<44} bound={r['bound']:<7} "
                  f"max_iters/run={r['max_total_iters_per_run']:<9} {tag}")
    with open(os.path.join(a.traces, "bounds_audit.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(f"total violating runs: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
