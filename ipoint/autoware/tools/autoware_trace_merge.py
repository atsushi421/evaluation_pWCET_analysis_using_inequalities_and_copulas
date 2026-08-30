#!/usr/bin/env python3
"""Merge the per-thread trace files written by job-mode processes (ipoint.h
with IPOINT_OUT_DIR) into one trace.bin + meta.json that ipoint_parse.py reads.

    autoware_trace_merge.py --out DIR [--replay-stride 1000000] \
        REPLAY_DIR[:PID]...

Every argument is the IPOINT_OUT_DIR of one replay (records of all
instrumented processes of that replay land there); an optional :PID selects the
files of one process, so that the callbacks of different containers can be
separated. Runs (job invocations) are copied in the order of their run index,
which is the process-wide invocation counter, and re-numbered as
replay_index * stride + run so that the run indices of a campaign are unique
and increase with time. The seed sentinel keeps the thread id.

meta.json carries the TSC frequency (from the calibration pairs taken at
process start and exit; the median over the merged processes), the sentinels
and per-process bookkeeping (records, overflow, in-job flushes) so that the
parser and the campaign report can check the trace.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import List

import numpy as np

REC_DTYPE = np.dtype([("ts", "<u8"), ("id", "<u4"), ("aux", "<u4")])
RUN_BEGIN, RUN_SEED, RUN_END = 0xFFFFFFF0, 0xFFFFFFF1, 0xFFFFFFF2


def load_process(dir_: str, pid: str | None):
    metas = []
    for m in glob.glob(os.path.join(dir_, "*.meta.json")):
        mm = re.match(r"(.*)_(\d+)\.meta\.json$", os.path.basename(m))
        if pid is not None and mm and mm.group(2) != str(pid):
            continue
        with open(m) as f:
            metas.append(json.load(f))
    recs = []
    for meta in metas:
        for t in meta["threads"]:
            p = os.path.join(dir_, t["file"])
            if os.path.exists(p) and os.path.getsize(p):
                recs.append(np.fromfile(p, dtype=REC_DTYPE))
    return metas, recs


def split_runs(recs: np.ndarray):
    """(run_index, slice) of every complete run in a thread file."""
    b = np.flatnonzero(recs["id"] == RUN_BEGIN)
    e = np.flatnonzero(recs["id"] == RUN_END)
    out = []
    j = 0
    for i in b:
        while j < len(e) and e[j] < i:
            j += 1
        if j >= len(e):
            break
        # the next begin must come after this end (a truncated run is dropped)
        nxt = b[np.searchsorted(b, i, side="right")] if np.searchsorted(b, i, side="right") < len(b) else len(recs)
        if e[j] > nxt:
            continue
        out.append((int(recs["ts"][i]), i, e[j] + 1))
        j += 1
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("replays", nargs="+", help="IPOINT_OUT_DIR of a replay, optionally :PID")
    ap.add_argument("--out", required=True)
    ap.add_argument("--replay-stride", type=int, default=1_000_000)
    ap.add_argument("--max-id", type=int, default=0, help="max ipoint id (informational)")
    a = ap.parse_args(argv)

    os.makedirs(a.out, exist_ok=True)
    chunks: List[np.ndarray] = []
    hz: List[float] = []
    procs = []
    n_runs = 0
    for k, arg in enumerate(a.replays):
        dir_, _, pid = arg.partition(":")
        metas, recs = load_process(dir_, pid or None)
        if not metas:
            print(f"warning: no meta.json in {dir_} (pid {pid or 'any'})", file=sys.stderr)
            continue
        runs = []
        for r in recs:
            for run, s, e in split_runs(r):
                runs.append((run, r[s:e]))
        runs.sort(key=lambda x: x[0])
        for run, body in runs:
            body = body.copy()
            body["ts"][0] = k * a.replay_stride + run
            chunks.append(body)
        n_runs += len(runs)
        for m in metas:
            hz.append(float(m.get("tsc_hz") or m.get("tsc_hz_short") or 0.0))
            procs.append({"replay": k, "dir": dir_, "pid": m["pid"], "tag": m["tag"], "jobs_total": m["jobs_total"],
                          "records": sum(t["records"] for t in m["threads"]),
                          "overflow": sum(t["overflow"] for t in m["threads"]),
                          "flush_in_job": sum(t["flush_in_job"] for t in m["threads"]),
                          "threads": len(m["threads"]), "tsc_hz": m.get("tsc_hz"), "runs_merged": len(runs)})
    trace = np.concatenate(chunks) if chunks else np.zeros(0, REC_DTYPE)
    trace.tofile(os.path.join(a.out, "trace.bin"))
    hz_valid = [h for h in hz if h > 1e8]
    meta = {"source": "autoware_trace_merge", "n_replays": len(a.replays), "n_runs": n_runs,
            "tsc_hz_start": float(np.median(hz_valid)) if hz_valid else None,
            "tsc_hz_spread": (float(max(hz_valid) - min(hz_valid)) if hz_valid else None),
            "ts_impl": "rdtscp_lfence", "max_id": a.max_id, "replay_stride": a.replay_stride,
            "sentinels": {"run_begin": RUN_BEGIN, "run_seed": RUN_SEED, "run_end": RUN_END},
            "processes": procs}
    with open(os.path.join(a.out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(f"merged {n_runs} runs ({len(trace)} records) from {len(procs)} processes into {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
