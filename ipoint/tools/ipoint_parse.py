#!/usr/bin/env python3
"""Turn the raw IPoint trace of a measurement run into per-unit samples.

    ipoint_parse.py --schema schema.json --trace-dir DIR --out OUT
        [--ns] [--max-runs N] [--min-unit-ns 300] [--legacy-names map.json]

Reads DIR/trace.bin (records of the fully traced runs), DIR/summary.bin
(one row per run) and DIR/meta.json written by bench_main.

Each run is replayed through a stack machine: an entry IPoint pushes the unit,
its exit pops it and yields one sample (exit - entry). A parent's self time is
its duration minus the durations of the units nested directly inside it.
Units that are still open when an ancestor closes are closed implicitly at the
ancestor's exit timestamp and counted in stats.json["implicit_closes"].

Outputs (times in TSC ticks unless --ns):
  units/<uid>.npy            sample per unit instance, trace order
  units/<uid>.run.npy        run index of every sample
  units/<uid>.self.npy       self time of container units
  units/<uid>.iters.npy      iterations per loop instance (loop units)
  units/<uid>.gap<k>.npy     k-th gap between consecutive children (functions)
  branches/<uid>.alt.npy     index of the alternative taken per branch instance
  sample/<uid>.pkl           pickled list of samples (copulas.ipynb format)
  e2e.npy / e2e_all.npy      end-to-end time of traced runs / of every run
  paths.csv                  per-run path signature (loop iteration counts and
                             alternatives taken) with its hash
  stats.json                 per-unit statistics, suggested exclusions
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pickle
import sys
from collections import defaultdict
from typing import Dict, List

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ipoint_schema import Schema, Unit  # noqa: E402

REC_DTYPE = np.dtype([("ts", "<u8"), ("id", "<u4"), ("aux", "<u4")])


def summary_dtype(max_id: int) -> np.dtype:
    return np.dtype([("run", "<u8"), ("seed", "<u8"), ("e2e", "<u8"), ("harness", "<u8"), ("sink", "<u8"),
                     ("nrec", "<u4"), ("overflow", "<u4"), ("hits", "<u4", (max_id + 1,))])


def load_summary(trace_dir: str, meta: dict) -> np.ndarray:
    return np.fromfile(os.path.join(trace_dir, "summary.bin"), dtype=summary_dtype(meta["max_id"]))


class RunParser:
    def __init__(self, schema: Schema):
        self.schema = schema
        self.by = schema.by_uid()
        self.id_map = schema.id_to_unit()
        self.samples: Dict[str, List[int]] = defaultdict(list)
        self.sample_run: Dict[str, List[int]] = defaultdict(list)
        self.selfs: Dict[str, List[int]] = defaultdict(list)
        self.iters: Dict[str, List[int]] = defaultdict(list)
        self.gaps: Dict[str, List[List[int]]] = defaultdict(list)
        self.alts: Dict[str, List[int]] = defaultdict(list)
        self.implicit: Dict[str, int] = defaultdict(int)
        self.unmatched_exit: Dict[str, int] = defaultdict(int)
        self.aux_changes = 0
        self.alt_index = {}
        for u in schema.units:
            if u.kind == "branch":
                for i, c in enumerate(u.children):
                    self.alt_index[c] = (u.uid, i)

    def parse_run(self, recs: np.ndarray, run: int, sig: Dict[str, int]) -> None:
        stack: List[list] = []  # [unit, ts_entry, child_sum, n_body, last_child_end, gaps]
        ts_arr, id_arr, aux_arr = recs["ts"], recs["id"], recs["aux"]
        if len(recs) and aux_arr.min() != aux_arr.max():
            self.aux_changes += 1

        def close(frame, ts_exit: int, implicit: bool) -> None:
            u, ts_in, child_sum, n_body, last_end, gaps = frame
            dur = int(ts_exit - ts_in)
            self.samples[u.uid].append(dur)
            self.sample_run[u.uid].append(run)
            if u.children:
                self.selfs[u.uid].append(dur - child_sum)
                if u.kind == "function":
                    gaps.append(int(ts_exit - last_end))
                    self.gaps[u.uid].append(gaps)
            if u.kind == "loop":
                self.iters[u.uid].append(n_body)
                sig[u.uid] = sig.get(u.uid, 0) + n_body
            if implicit:
                self.implicit[u.uid] += 1
            if stack:
                p = stack[-1]
                p[2] += dur
                if p[0].kind == "loop" and u.kind == "loop_body":
                    p[3] += 1
                if p[0].kind == "function":
                    p[5].append(int(ts_in - p[4]))
                p[4] = ts_exit

        for i in range(len(recs)):
            iid = int(id_arr[i])
            m = self.id_map.get(iid)
            if m is None:
                continue
            u, role = m
            ts = int(ts_arr[i])
            if role == "marker":
                self.samples[u.uid].append(0)
                self.sample_run[u.uid].append(run)
                if u.uid in self.alt_index:
                    b, k = self.alt_index[u.uid]
                    self.alts[b].append(k)
                    sig[u.uid] = sig.get(u.uid, 0) + 1
                if stack:
                    stack[-1][4] = ts
                continue
            if role == "entry":
                stack.append([u, ts, 0, 0, ts, []])
                if u.uid in self.alt_index:
                    b, k = self.alt_index[u.uid]
                    self.alts[b].append(k)
                    sig[u.uid] = sig.get(u.uid, 0) + 1
                continue
            # exit
            if not any(f[0] is u for f in stack):
                self.unmatched_exit[u.uid] += 1
                continue
            while stack and stack[-1][0] is not u:
                close(stack.pop(), ts, True)
            close(stack.pop(), ts, False)
        while stack:
            frame = stack.pop()
            close(frame, int(ts_arr[-1]) if len(recs) else frame[1], True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--trace-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ns", action="store_true", help="convert ticks to nanoseconds with tsc_hz_start")
    ap.add_argument("--max-runs", type=int, default=None)
    ap.add_argument("--min-unit-ns", type=float, default=300.0, help="units with median below this are suggested for exclusion")
    ap.add_argument("--legacy-names", help="json {uid: name} for sample/<name>.pkl aliases")
    a = ap.parse_args(argv)

    schema = Schema.from_json(a.schema)
    with open(os.path.join(a.trace_dir, "meta.json")) as f:
        meta = json.load(f)
    tick_ns = 1e9 / meta["tsc_hz_start"] if meta.get("ts_impl") != "clock_gettime_raw" else 1.0
    scale = tick_ns if a.ns else 1.0
    os.makedirs(os.path.join(a.out, "units"), exist_ok=True)
    os.makedirs(os.path.join(a.out, "branches"), exist_ok=True)
    os.makedirs(os.path.join(a.out, "sample"), exist_ok=True)

    summary = load_summary(a.trace_dir, meta)
    np.save(os.path.join(a.out, "e2e_all.npy"), summary["e2e"].astype(np.float64) * scale)
    np.save(os.path.join(a.out, "harness_all.npy"), summary["harness"].astype(np.float64) * scale)
    np.save(os.path.join(a.out, "hits_all.npy"), summary["hits"])
    np.save(os.path.join(a.out, "runs_all.npy"), summary["run"])

    trace_path = os.path.join(a.trace_dir, "trace.bin")
    recs = np.memmap(trace_path, dtype=REC_DTYPE, mode="r") if os.path.getsize(trace_path) else np.zeros(0, REC_DTYPE)
    sent = meta["sentinels"]
    begins = np.flatnonzero(recs["id"] == sent["run_begin"])
    ends = np.flatnonzero(recs["id"] == sent["run_end"])
    if len(begins) != len(ends):
        print(f"warning: {len(begins)} run_begin but {len(ends)} run_end sentinels", file=sys.stderr)
    n_runs = min(len(begins), len(ends))
    if a.max_runs is not None:
        n_runs = min(n_runs, a.max_runs)

    rp = RunParser(schema)
    entry_unit = schema.entry_unit()
    e2e: List[int] = []
    paths = []
    for k in range(n_runs):
        b, e = int(begins[k]), int(ends[k])
        run = int(recs["ts"][b])
        seed = int(recs["ts"][b + 1]) if recs["id"][b + 1] == sent["run_seed"] else 0
        body = recs[b + 2:e]
        sig: Dict[str, int] = {}
        rp.parse_run(body, run, sig)
        if entry_unit is not None:
            ids = body["id"]
            ie = np.flatnonzero(ids == entry_unit.entry)
            ix = np.flatnonzero(ids == entry_unit.exit)
            e2e.append(int(body["ts"][ix[-1]] - body["ts"][ie[0]]) if len(ie) and len(ix) else 0)
        sig_str = ";".join(f"{u}={sig[u]}" for u in sorted(sig))
        paths.append((run, seed, sig_str, hashlib.sha1(sig_str.encode()).hexdigest()[:12]))
        if (k + 1) % 10000 == 0:
            print(f"parsed {k + 1}/{n_runs} runs", file=sys.stderr)

    np.save(os.path.join(a.out, "e2e.npy"), np.asarray(e2e, dtype=np.float64) * scale)
    with open(os.path.join(a.out, "paths.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["run", "seed", "signature", "hash"])
        w.writerows(paths)

    legacy = {}
    if a.legacy_names:
        with open(a.legacy_names) as f:
            legacy = json.load(f)
    stats = {"tick_ns": tick_ns, "unit": "ns" if a.ns else "ticks", "runs_parsed": n_runs,
             "aux_changes": rp.aux_changes, "implicit_closes": dict(rp.implicit),
             "unmatched_exits": dict(rp.unmatched_exit), "units": {}, "suggested_exclusions": []}
    for uid, vals in rp.samples.items():
        arr = np.asarray(vals, dtype=np.float64) * scale
        np.save(os.path.join(a.out, "units", f"{uid}.npy"), arr)
        np.save(os.path.join(a.out, "units", f"{uid}.run.npy"), np.asarray(rp.sample_run[uid], dtype=np.uint64))
        with open(os.path.join(a.out, "sample", f"{legacy.get(uid, uid)}.pkl"), "wb") as f:
            pickle.dump(arr.tolist(), f)
        u = schema.by_uid()[uid]
        med_ns = float(np.median(arr)) * (1.0 if a.ns else tick_ns) if len(arr) else 0.0
        st = {"kind": u.kind, "n": int(len(arr)), "min": float(arr.min()), "median": float(np.median(arr)),
              "mean": float(arr.mean()), "p99": float(np.quantile(arr, 0.99)), "max": float(arr.max()),
              "median_ns": med_ns}
        if uid in rp.selfs:
            s_arr = np.asarray(rp.selfs[uid], dtype=np.float64) * scale
            np.save(os.path.join(a.out, "units", f"{uid}.self.npy"), s_arr)
            st["self_median"] = float(np.median(s_arr))
            st["self_min"] = float(s_arr.min())
        if uid in rp.iters:
            it = np.asarray(rp.iters[uid], dtype=np.uint32)
            np.save(os.path.join(a.out, "units", f"{uid}.iters.npy"), it)
            st["iters_max"] = int(it.max())
            st["iters_mean"] = float(it.mean())
            st["bound"] = u.bound
        if uid in rp.gaps:
            g = rp.gaps[uid]
            width = max(len(x) for x in g)
            for k in range(width):
                col = np.asarray([x[k] if k < len(x) else np.nan for x in g], dtype=np.float64) * scale
                np.save(os.path.join(a.out, "units", f"{uid}.gap{k}.npy"), col)
            st["gaps"] = width
        # every unit below the granularity floor loses its probes, except the
        # entry function whose IPoint pair defines the end-to-end time
        if not u.empty and med_ns < a.min_unit_ns and uid != schema.entry_function:
            stats["suggested_exclusions"].append(uid)
        stats["units"][uid] = st
    for b, alts in rp.alts.items():
        np.save(os.path.join(a.out, "branches", f"{b}.alt.npy"), np.asarray(alts, dtype=np.uint8))
        stats["units"].setdefault(b, {"kind": "branch"})["alt_counts"] = np.bincount(np.asarray(alts), minlength=2).tolist()
    with open(os.path.join(a.out, "stats.json"), "w") as f:
        json.dump(stats, f, indent=1)
    print(f"parsed {n_runs} runs, {len(rp.samples)} units; implicit closes: {sum(rp.implicit.values())}, "
          f"unmatched exits: {sum(rp.unmatched_exit.values())}, suggested exclusions: {stats['suggested_exclusions']}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
