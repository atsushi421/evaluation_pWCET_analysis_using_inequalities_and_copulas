#!/usr/bin/env python3
"""Data-driven timing granularity for the Autoware callbacks: turn the
per-unit statistics of a parsed pilot campaign into `exclude_units` entries of
targets.json, following the rule of the benchmark campaign (a unit whose median
duration is below --min-unit-ns loses its probes; excluding a unit excludes its
descendants; the job function is never excluded).

    prune_from_pilot.py --campaign traces/pilot [--targets targets.json] [--min-unit-ns 300]
                        [--apply] [--report report.json]

Without --apply the report is printed only. With --apply the exclusions are
merged into targets.json; re-instrument (restore the sources, apply.sh) and
run a verification pilot afterwards: parents shrink once their children lose
their probes, so a second round may exclude a few more units.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AW = os.path.dirname(HERE)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--targets", default=os.path.join(AW, "targets.json"))
    ap.add_argument("--min-unit-ns", type=float, default=300.0)
    ap.add_argument("--min-samples", type=int, default=20, help="units with fewer samples are left alone")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", default=None)
    a = ap.parse_args(argv)

    with open(a.targets) as f:
        spec = json.load(f)
    # uid -> (package, file spec) through the schemas
    owner = {}
    for pkg, pspec in spec["packages"].items():
        for fspec in pspec["files"]:
            sp = os.path.join(AW, "schemas", pkg, os.path.basename(fspec["path"]) + ".schema.json")
            if not os.path.exists(sp):
                continue
            with open(sp) as f:
                sd = json.load(f)
            for u in sd["units"]:
                owner[u["uid"]] = (pkg, fspec, sd)
    report = {"min_unit_ns": a.min_unit_ns, "callbacks": {}}
    new_excl = {}  # (pkg, path) -> set(uid)
    for st_path in sorted(glob.glob(os.path.join(a.campaign, "parsed", "*", "stats.json"))):
        cb = os.path.basename(os.path.dirname(st_path))
        with open(st_path) as f:
            st = json.load(f)
        excl, kept = [], []
        for uid, v in st["units"].items():
            if uid not in owner or v.get("kind") == "branch" or "median_ns" not in v:
                continue
            pkg, fspec, sd = owner[uid]
            by = {u["uid"]: u for u in sd["units"]}
            u = by[uid]
            if u.get("job") or u.get("empty"):
                continue
            if v["n"] < a.min_samples:
                continue
            if v["median_ns"] < a.min_unit_ns:
                excl.append((uid, v["median_ns"], v["n"]))
                new_excl.setdefault((pkg, fspec["path"]), set()).add(uid)
            else:
                kept.append((uid, v["median_ns"], v["n"]))
        report["callbacks"][cb] = {"excluded": [{"uid": u, "median_ns": round(m, 1), "n": n} for u, m, n in sorted(excl, key=lambda x: x[1])],
                                   "kept": len(kept), "units_seen": len(st["units"])}
        print(f"{cb}: {len(excl)} units below {a.min_unit_ns:.0f} ns, {len(kept)} kept", file=sys.stderr)
        for u, m, n in sorted(excl, key=lambda x: x[1])[:8]:
            print(f"    drop {u} (median {m:.0f} ns, n={n})", file=sys.stderr)
    if a.apply:
        for pkg, pspec in spec["packages"].items():
            for fspec in pspec["files"]:
                add = new_excl.get((pkg, fspec["path"]))
                if add:
                    cur = set(fspec.get("exclude_units", []))
                    fspec["exclude_units"] = sorted(cur | add)
        with open(a.targets, "w") as f:
            json.dump(spec, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"targets.json updated ({sum(len(v) for v in new_excl.values())} exclusions); restore the sources and re-run apply.sh", file=sys.stderr)
    if a.report:
        with open(a.report, "w") as f:
            json.dump(report, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
