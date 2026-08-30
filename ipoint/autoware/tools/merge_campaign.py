#!/usr/bin/env python3
"""Merge and parse the traces of a replay campaign per callback.

    merge_campaign.py --campaign traces/autoware [--targets targets.json] [--only cb1]...
        [--include-rejected] [--min-unit-ns 300]

For every process of targets.json the pid recorded in replay_XXXX/replay.json
selects its trace files; the accepted replays are merged in order
(autoware_trace_merge.py, run index = replay * 10^6 + invocation) into
<campaign>/merged/<cb>/ and parsed (ipoint_parse.py, all schemas of the
packages loaded into that process, the job function as the end-to-end unit)
into <campaign>/parsed/<cb>/. A summary with the number of runs, the units and
the parser's consistency counters is written to <campaign>/merge_summary.json.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AW = os.path.dirname(HERE)
TOOLS = os.path.join(os.path.dirname(AW), "tools")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--targets", default=os.path.join(AW, "targets.json"))
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--include-rejected", action="store_true")
    ap.add_argument("--min-unit-ns", type=float, default=300.0)
    ap.add_argument("--max-replays", type=int, default=None)
    a = ap.parse_args(argv)

    with open(a.targets) as f:
        spec = json.load(f)
    replays = []
    for d in sorted(glob.glob(os.path.join(a.campaign, "replay_[0-9]*"))):
        rj = os.path.join(d, "replay.json")
        if not os.path.exists(rj):
            continue
        with open(rj) as f:
            r = json.load(f)
        if r.get("accepted") or a.include_rejected:
            replays.append((d, r))
    if a.max_replays:
        replays = replays[:a.max_replays]
    print(f"{len(replays)} replays", file=sys.stderr)
    summary = {"replays": len(replays), "callbacks": {}}
    for cb, ps in spec["processes"].items():
        if a.only and cb not in a.only:
            continue
        args = []
        for d, r in replays:
            for pid in r.get("pids", {}).get(cb, []):
                args.append(f"{os.path.join(d, 'ipoint')}:{pid}")
        if not args:
            print(f"{cb}: no traces", file=sys.stderr)
            continue
        merged = os.path.join(a.campaign, "merged", cb)
        parsed = os.path.join(a.campaign, "parsed", cb)
        schemas = []
        job = None
        for pkg in ps["packages"]:
            for s in sorted(glob.glob(os.path.join(AW, "schemas", pkg, "*.schema.json"))):
                schemas.append(s)
                with open(s) as f:
                    sd = json.load(f)
                for u in sd["units"]:
                    if u.get("job") and job is None:
                        job = u["uid"]
        if not schemas:
            print(f"{cb}: no schema", file=sys.stderr)
            continue
        subprocess.run([sys.executable, os.path.join(HERE, "autoware_trace_merge.py"), "--out", merged] + args, check=True)
        cmd = [sys.executable, os.path.join(TOOLS, "ipoint_parse.py"), "--trace-dir", merged, "--out", parsed, "--ns",
               "--min-unit-ns", str(a.min_unit_ns)]
        for s in schemas:
            cmd += ["--schema", s]
        if job:
            cmd += ["--entry", job]
        subprocess.run(cmd, check=True)
        with open(os.path.join(merged, "meta.json")) as f:
            meta = json.load(f)
        with open(os.path.join(parsed, "stats.json")) as f:
            st = json.load(f)
        summary["callbacks"][cb] = {"job": job, "runs": meta["n_runs"], "processes": len(meta["processes"]),
                                    "tsc_hz": meta["tsc_hz_start"], "units": len(st["units"]),
                                    "implicit_closes": sum(st["implicit_closes"].values()),
                                    "unmatched_exits": sum(st["unmatched_exits"].values()),
                                    "aux_changes": st["aux_changes"], "suggested_exclusions": st["suggested_exclusions"],
                                    "overflow": sum(p["overflow"] for p in meta["processes"]),
                                    "flush_in_job": sum(p["flush_in_job"] for p in meta["processes"])}
        print(f"{cb}: {meta['n_runs']} runs, {len(st['units'])} units, implicit {summary['callbacks'][cb]['implicit_closes']}, "
              f"aux changes {st['aux_changes']}", file=sys.stderr)
    with open(os.path.join(a.campaign, "merge_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
