#!/usr/bin/env python3
"""Re-run ipoint_parse.py on the merged traces of a campaign, all callbacks in parallel
(the parse step of merge_campaign.py without re-merging).

    reparse_campaign.py --campaign traces/autoware [--only cb1]... [--min-unit-ns 300]
"""
import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AW = os.path.dirname(HERE)
TOOLS = os.path.join(os.path.dirname(AW), "tools")

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--campaign", required=True)
ap.add_argument("--targets", default=os.path.join(AW, "targets.json"))
ap.add_argument("--only", action="append", default=[])
ap.add_argument("--min-unit-ns", type=float, default=300.0)
a = ap.parse_args()
spec = json.load(open(a.targets))
procs = {}
for cb, ps in spec["processes"].items():
    if a.only and cb not in a.only:
        continue
    merged = os.path.join(a.campaign, "merged", cb)
    if not os.path.isdir(merged):
        continue
    schemas = [s for pkg in ps["packages"] for s in sorted(glob.glob(os.path.join(AW, "schemas", pkg, "*.schema.json")))]
    job = next((u["uid"] for s in schemas for u in json.load(open(s))["units"] if u.get("job")), None)
    cmd = [sys.executable, os.path.join(TOOLS, "ipoint_parse.py"), "--trace-dir", merged,
           "--out", os.path.join(a.campaign, "parsed", cb), "--ns", "--min-unit-ns", str(a.min_unit_ns)]
    for s in schemas:
        cmd += ["--schema", s]
    if job:
        cmd += ["--entry", job]
    log = open(os.path.join(a.campaign, f"reparse_{cb}.log"), "w")
    procs[cb] = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
for cb, p in procs.items():
    print(f"{cb}: exit {p.wait()}", flush=True)
