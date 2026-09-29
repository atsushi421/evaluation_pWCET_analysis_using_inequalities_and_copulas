#!/usr/bin/env python3
"""E2-10 cost of the static analysis: wall time of `ipoint_instrument.py --all` (libclang parse, scope tree,
IPoint insertion, schema output) per evaluated kernel, with the arguments of `run_campaign.py instrument`.
The instrumented source and the schema go to a temporary directory, so the campaign files stay untouched.
Run it with the system python3, whose libclang bindings (llvm-14) the instrumenter needs, like run_campaign.py.

    python3 tools/static_analysis_time.py > results/tables/static_analysis_time.md
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ipoint", "tools"))
import run_campaign  # noqa: E402

V1_ONLY = {"fdct", "sqrt"}  # first-submission kernels, not in the revised evaluation


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=5)
    a = ap.parse_args()
    camp = run_campaign.Campaign(argparse.Namespace(dry_run=False))
    print(f"Static analysis and instrumentation (`ipoint_instrument.py --all`), wall time of {a.reps} runs per kernel.\n")
    print("| kernel | units | median s | min s | max s |\n|---|---|---|---|---|")
    with tempfile.TemporaryDirectory() as tmp:
        for b in run_campaign.BENCHES:
            if b in V1_ONLY:
                continue
            out_c, schema = os.path.join(tmp, b + ".ipoint_full.c"), os.path.join(tmp, b + ".schema.json")
            cmd = camp.instrument_cmd(b, out_c, schema, ["--all"])
            times = []
            for _ in range(a.reps):
                t0 = time.perf_counter()
                subprocess.run(cmd, check=True, capture_output=True)
                times.append(time.perf_counter() - t0)
            with open(schema) as f:
                units = len(json.load(f)["units"])
            print(f"| {b} | {units} | {statistics.median(times):.2f} | {min(times):.2f} | {max(times):.2f} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
