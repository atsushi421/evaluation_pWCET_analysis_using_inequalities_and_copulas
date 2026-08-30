#!/usr/bin/env python3
"""Per-callback summary of a parsed campaign: runs, path signatures (with the
median end-to-end time of each), end-to-end quantiles and the largest units.

    pilot_summary.py --campaign traces/pilot [--top 6]

The path signature of a run lists the alternatives taken and the loop
iteration counts; early-return invocations (initialization phase, missing
inputs) form their own signatures with a small end-to-end time, which is how
the analysis separates them from the nominal path (design note, sec. 3.1).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--top", type=int, default=6)
    a = ap.parse_args(argv)
    summ = json.load(open(os.path.join(a.campaign, "merge_summary.json")))
    for cb, info in summ["callbacks"].items():
        pdir = os.path.join(a.campaign, "parsed", cb)
        if not os.path.exists(os.path.join(pdir, "e2e.npy")):
            continue
        e2e = np.load(os.path.join(pdir, "e2e.npy")) / 1e3  # us
        if len(e2e) == 0:
            print(f"==== {cb} {info['job']}: no runs")
            continue
        sigs = defaultdict(list)
        with open(os.path.join(pdir, "paths.csv")) as f:
            for i, row in enumerate(csv.DictReader(f)):
                if i < len(e2e):
                    sigs[row["signature"]].append(e2e[i])
        print(f"==== {cb} {info['job']}: {len(e2e)} runs, {len(sigs)} signatures; e2e median {np.median(e2e):.1f} us, "
              f"p99 {np.percentile(e2e, 99):.1f}, max {e2e.max():.1f}")
        for sig, vals in sorted(sigs.items(), key=lambda x: -len(x[1]))[:a.top]:
            v = np.array(vals)
            short = sig if len(sig) < 110 else sig[:107] + "..."
            print(f"   n={len(v):6d} median {np.median(v):9.1f} us p99 {np.percentile(v, 99):9.1f} max {v.max():9.1f} | {short}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
