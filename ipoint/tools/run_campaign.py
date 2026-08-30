#!/usr/bin/env python3
"""Drive the whole measurement campaign for the Mälardalen kernels.

    run_campaign.py --bench all --out traces [--stages instrument,pilot,build,run,parse]
        [--runs 1e7 --full 1e5 --overhead-runs 1e5 --coverage-runs 1e7]
        [--pilot-runs 1000 --pilot-rounds 8 --min-unit-ns 300 --max-probe-share 0.05 | --max-depth N]
        [--seed0 20260829 --core 3 --warmup 1000] [--dry-run]
    run_campaign.py --probe-bench --out traces

Stages per benchmark:
  instrument  full scope tree (schema_full.json, <b>.ipoint_full.c)
  pilot       data-driven granularity: instrument everything, run a short
              TIMING pilot, drop units whose median is below --min-unit-ns,
              repeat until no unit is dropped (parents shrink once their
              children lose their probes). Result: exclusions.json and the
              pruned <b>.ipoint.c / schema_timing.json. --max-depth replaces
              the pilot by a fixed depth policy.
  build       OFF and TIMING from the pruned source, COVERAGE from the full one
  run         TIMING --runs (first --full runs fully traced), OFF
              --overhead-runs, COVERAGE --coverage-runs
  parse       per-unit samples, consistency check, overhead and coverage
              statistics, campaign.json with the environment description
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.dirname(ROOT)
BENCH_DIR = os.path.join(ROOT, "bench")
SRC_DIR = os.path.join(REPO, "benchmarks", "malardalen")
# entry: function whose outermost IPoint pair is the end-to-end time ("main" needs
# keep_main, the harness then calls the renamed ipoint_orig_main); patch: size patch
# in benchmarks/malardalen/patches applied before instrumentation; kernel_flags:
# extra compiler flags for the kernel object only.
BENCHES = {
    "bsort100": {"entry": "BubbleSort", "param": 0.0},
    "fdct": {"entry": "fdct", "param": 0.0},
    "fir": {"entry": "fir_filter_int", "param": 0.0, "bounds": "bounds/fir.bounds.json"},
    "matmult": {"entry": "Multiply", "param": 0.0},
    "sqrt": {"entry": "sqrtfcn", "param": 1e-3},
    "edn": {"entry": "main", "keep_main": True, "param": 0.0, "bounds": "bounds/edn.bounds.json"},
    "ndes": {"entry": "des", "param": 0.0, "bounds": "bounds/ndes.bounds.json"},
    "st": {"entry": "main", "keep_main": True, "param": 0.0},
    "lms": {"entry": "main", "keep_main": True, "param": 0.0, "bounds": "bounds/lms.bounds.json"},
    "prime": {"entry": "prime", "param": 0.0, "bounds": "bounds/prime.bounds.json"},
    "cnt": {"entry": "Sum", "param": 0.0, "patch": "cnt.size.patch"},
    "ludcmp": {"entry": "ludcmp", "param": 0.0, "bounds": "bounds/ludcmp.bounds.json"},
    # the kernel function select() clashes with libc's select(), which <stdlib.h>
    # declares under the GNU feature set; strict C11 hides it and the kernel
    # symbol is renamed (like main) for the adapter
    "select": {"entry": "select", "param": 0.0, "patch": "select.size.patch", "bounds": "bounds/select.bounds.json",
               "kernel_flags": ["-std=c11", "-Dselect=mrtc_select"]},
    "qsort-exam": {"entry": "sort", "param": 0.0, "patch": "qsort-exam.size.patch",
                   "bounds": "bounds/qsort-exam.bounds.json"},
}
TS_IMPLS = ["RDTSCP_LFENCE", "LFENCE_RDTSC_LFENCE", "CPUID_RDTSC", "CLOCK_GETTIME_RAW"]


class Campaign:
    def __init__(self, a):
        self.a = a
        self.log = []

    def sh(self, cmd, cwd=None, capture=False):
        line = " ".join(cmd)
        self.log.append(line)
        print("+", line, file=sys.stderr)
        if self.a.dry_run:
            return ""
        r = subprocess.run(cmd, cwd=cwd, check=True, capture_output=capture, text=True)
        return r.stdout if capture else ""

    # paths
    def build_dir(self, b):
        return os.path.join(BENCH_DIR, "build", b)

    def out_dir(self, b, *p):
        return os.path.join(self.a.out, b, *p)

    def ids(self, schema_path):
        with open(schema_path) as f:
            d = json.load(f)
        u = {x["uid"]: x for x in d["units"]}[d["entry_function"]]
        return u["entry"], u["exit"], d["max_id"]

    def source(self, b):
        """Upstream source, or the size-patched copy in the build directory."""
        cfg = BENCHES[b]
        src = os.path.join(SRC_DIR, b + ".c")
        if "patch" not in cfg:
            return src
        out = os.path.join(self.build_dir(b), b + ".c")
        if not os.path.exists(out):
            os.makedirs(self.build_dir(b), exist_ok=True)
            self.sh(["patch", "-s", "-o", out, src, os.path.join(SRC_DIR, "patches", cfg["patch"])])
        return out

    def instrument_cmd(self, b, out_c, schema, extra):
        cfg = BENCHES[b]
        cmd = [sys.executable, os.path.join(HERE, "ipoint_instrument.py"), self.source(b),
               "--entry", cfg["entry"], "--out", out_c, "--schema", schema]
        if "bounds" in cfg:
            cmd += ["--bounds", os.path.join(BENCH_DIR, cfg["bounds"])]
        if cfg.get("keep_main"):
            cmd.append("--keep-main")
        return cmd + extra

    # stages
    def instrument(self, b):
        os.makedirs(self.build_dir(b), exist_ok=True)
        self.sh(self.instrument_cmd(b, os.path.join(self.build_dir(b), b + ".ipoint_full.c"),
                                    os.path.join(self.build_dir(b), "schema_full.json"), ["--all"]))

    def instrument_pruned(self, b, exclusions):
        extra = ["--all"] if self.a.max_depth is None else ["--max-depth", str(self.a.max_depth)]
        for x in sorted(exclusions):
            extra += ["--exclude-unit", x]
        self.sh(self.instrument_cmd(b, os.path.join(self.build_dir(b), b + ".ipoint.c"),
                                    os.path.join(self.build_dir(b), "schema_timing.json"), extra))

    def make(self, b, mode, src):
        defs = " ".join(BENCHES[b].get("kernel_flags", []))
        self.sh(["make", "-s", f"BENCH={b}", f"MODE={mode}", f"SRC={src}", f"KERNEL_DEFS={defs}"], cwd=BENCH_DIR)

    def run_bench(self, b, mode, out, runs, full, schema, extra=()):
        exe = os.path.join(self.build_dir(b), mode, f"bench_{b}")
        e, x, m = (0, 0, 0) if self.a.dry_run and not os.path.exists(schema) else self.ids(schema)
        cmd = ["taskset", "-c", str(self.a.core), exe, "--out", out, "--runs", str(int(runs)),
               "--full-trace-runs", str(int(full)), "--seed0", str(self.a.seed0), "--core", str(self.a.core),
               "--warmup", str(self.a.warmup), "--param", str(BENCHES[b]["param"]), "--entry-id", str(e),
               "--exit-id", str(x), "--max-id", str(m), "--calib", "1"] + list(extra)
        self.sh(cmd)

    def pilot(self, b):
        excl_path = os.path.join(self.build_dir(b), "exclusions.json")
        if self.a.max_depth is not None:
            self.instrument_pruned(b, [])
            with open(excl_path, "w") as f:
                json.dump({"policy": "max_depth", "max_depth": self.a.max_depth, "exclusions": [], "rounds": []}, f, indent=1)
            return
        exclusions, rounds = set(), []
        src = os.path.join(self.build_dir(b), b + ".ipoint.c")
        schema = os.path.join(self.build_dir(b), "schema_timing.json")
        for k in range(self.a.pilot_rounds):
            self.instrument_pruned(b, exclusions)
            self.make(b, "timing", src)
            out = self.out_dir(b, "pilot", f"round{k}")
            self.run_bench(b, "timing", out, self.a.pilot_runs, self.a.pilot_runs, schema)
            parsed = os.path.join(out, "parsed")
            self.sh([sys.executable, os.path.join(HERE, "ipoint_parse.py"), "--schema", schema, "--trace-dir", out,
                     "--out", parsed, "--min-unit-ns", str(self.a.min_unit_ns)])
            if self.a.dry_run:
                break
            with open(os.path.join(parsed, "stats.json")) as f:
                st = json.load(f)
            new = set(st["suggested_exclusions"]) - exclusions
            if self.a.max_probe_share > 0 and not new:
                new |= self.probe_budget_exclusions(schema, st) - exclusions
            rounds.append({"round": k, "instrumented_units": len([u for u in st["units"].values() if u.get("kind") != "branch"]),
                           "new_exclusions": sorted(new)})
            if os.path.exists(os.path.join(out, "trace.bin")):
                os.remove(os.path.join(out, "trace.bin"))
            if not new:
                break
            exclusions |= new
        else:
            print(f"warning: {b}: pilot did not converge within {self.a.pilot_rounds} rounds", file=sys.stderr)
        self.instrument_pruned(b, exclusions)
        with open(excl_path, "w") as f:
            json.dump({"policy": "pilot", "min_unit_ns": self.a.min_unit_ns, "max_probe_share": self.a.max_probe_share,
                       "probe_ns": self.a.probe_ns, "pilot_runs": self.a.pilot_runs,
                       "exclusions": sorted(exclusions), "rounds": rounds}, f, indent=1)

    def probe_budget_exclusions(self, schema_path, st):
        """Units to drop so that the probes of a run cost at most --max-probe-share
        of the end-to-end median: the unit with the most probes per run goes
        first (its descendants are already below the floor, or go with it)."""
        with open(schema_path) as f:
            sch = json.load(f)
        entry = sch["entry_function"]
        runs = max(1, st["runs_parsed"])
        e2e_ns = st["units"].get(entry, {}).get("median_ns", 0.0)
        cost = {}
        for u in sch["units"]:
            if u["kind"] == "branch" or u["uid"] == entry or not u.get("instrumented", True):
                continue
            n = st["units"].get(u["uid"], {}).get("n", 0)
            cost[u["uid"]] = (1 if u.get("empty") else 2) * n / runs
        budget = self.a.max_probe_share * e2e_ns / self.a.probe_ns - 2  # the entry pair is always paid
        drop = set()
        while cost and sum(cost.values()) > budget:
            worst = max(cost, key=lambda k: (cost[k], -st["units"].get(k, {}).get("median_ns", 0.0)))
            drop.add(worst)
            del cost[worst]
        return drop

    def build(self, b):
        d = self.build_dir(b)
        self.make(b, "off", os.path.join(d, b + ".ipoint.c"))
        self.make(b, "timing", os.path.join(d, b + ".ipoint.c"))
        self.make(b, "coverage", os.path.join(d, b + ".ipoint_full.c"))

    def run(self, b):
        d = self.build_dir(b)
        st, sf = os.path.join(d, "schema_timing.json"), os.path.join(d, "schema_full.json")
        self.run_bench(b, "timing", self.out_dir(b, "timing"), self.a.runs, self.a.full, st)
        self.run_bench(b, "off", self.out_dir(b, "off"), self.a.overhead_runs, 0, st)
        self.run_bench(b, "coverage", self.out_dir(b, "coverage"), self.a.coverage_runs, 0, sf)

    def parse(self, b):
        d = self.build_dir(b)
        st, sf = os.path.join(d, "schema_timing.json"), os.path.join(d, "schema_full.json")
        timing, off, cov = self.out_dir(b, "timing"), self.out_dir(b, "off"), self.out_dir(b, "coverage")
        parsed = self.out_dir(b, "parsed")
        self.sh([sys.executable, os.path.join(HERE, "ipoint_parse.py"), "--schema", st, "--trace-dir", timing,
                 "--out", parsed, "--min-unit-ns", str(self.a.min_unit_ns)])
        try:
            self.sh([sys.executable, os.path.join(HERE, "ipoint_check.py"), "--schema", st, "--trace-dir", timing,
                     "--parsed", parsed])
        except subprocess.CalledProcessError:
            print(f"warning: {b}: consistency check reported failures", file=sys.stderr)
        self.sh([sys.executable, os.path.join(HERE, "ipoint_overhead.py"), "--off", off, "--timing", timing,
                 "--coverage", cov, "--out", self.out_dir(b, "overhead.json")], capture=True)
        self.sh([sys.executable, os.path.join(HERE, "ipoint_coverage.py"), "--schema", sf, "--dir", cov,
                 "--train", "10000", "--out", self.out_dir(b, "coverage.json")], capture=True)
        if self.a.dry_run:
            return
        for name in ("schema_full.json", "schema_timing.json", "exclusions.json", b + ".ipoint.c", b + ".ipoint_full.c"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                shutil.copy(p, self.out_dir(b, name))
        sysinfo = json.loads(subprocess.run([os.path.join(HERE, "sysinfo.sh"), str(self.a.core)], check=True,
                                            capture_output=True, text=True).stdout)
        rdtscp = subprocess.run(["grep", "-c", "rdtscp", os.path.join(d, "timing", "kernel.objdump")],
                                capture_output=True, text=True).stdout.strip()
        with open(self.out_dir(b, "campaign.json"), "w") as f:
            json.dump({"bench": b, "config": BENCHES[b], "args": vars(self.a), "sysinfo": sysinfo,
                       "kernel_cflags": "-O2 -fno-builtin", "rdtscp_in_kernel_objdump": int(rdtscp or 0),
                       "commands": self.log}, f, indent=1)

    def probe_bench(self):
        os.makedirs(self.a.out, exist_ok=True)
        res = []
        for impl in TS_IMPLS:
            exe = os.path.join(BENCH_DIR, "build", f"probe_{impl.lower()}")
            os.makedirs(os.path.dirname(exe), exist_ok=True)
            self.sh(["gcc", "-O2", "-std=gnu11", "-DIPOINT_MODE_TIMING", f"-DIPOINT_TS_IMPL=IPOINT_TS_{impl}",
                     "-I" + os.path.join(ROOT, "include"), os.path.join(ROOT, "src", "ipoint_probe_bench.c"), "-o", exe])
            out = self.sh(["taskset", "-c", str(self.a.core), exe, "--pairs", "1000000", "--calib", "1",
                           "--core", str(self.a.core), "--json"], capture=True)
            if out:
                res.append(json.loads(out))
        if not self.a.dry_run:
            with open(os.path.join(self.a.out, "probe_cost.json"), "w") as f:
                json.dump(res, f, indent=1)
            for r in res:
                print(f"{r['ts_impl']:22s} median {r['ns']['median']:.1f} ns  p99 {r['ns']['p99']:.1f} ns  max {r['ns']['max']:.0f} ns")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bench", default="all", help="comma separated names or 'all'")
    ap.add_argument("--out", default=os.path.join(ROOT, "traces"))
    ap.add_argument("--stages", default="instrument,pilot,build,run,parse")
    ap.add_argument("--runs", type=float, default=1e7)
    ap.add_argument("--full", type=float, default=1e5, help="runs whose complete IPoint trace is kept")
    ap.add_argument("--overhead-runs", type=float, default=1e5)
    ap.add_argument("--coverage-runs", type=float, default=1e7)
    ap.add_argument("--pilot-runs", type=int, default=1000)
    ap.add_argument("--pilot-rounds", type=int, default=8, help="a round re-measures after each pruning step; kernels with deep unit trees need 4-6")
    ap.add_argument("--min-unit-ns", type=float, default=300.0)
    ap.add_argument("--max-probe-share", type=float, default=0.05,
                    help="after the floor has converged, also drop the units with the most probes per run until "
                         "probes * --probe-ns is at most this share of the end-to-end median (0 = off; "
                         "the paper uses 0.05)")
    ap.add_argument("--probe-ns", type=float, default=22.0, help="probe cost assumed by --max-probe-share")
    ap.add_argument("--max-depth", type=int, default=None, help="fixed depth policy instead of the pilot")
    ap.add_argument("--seed0", type=int, default=20260829)
    ap.add_argument("--core", type=int, default=3)
    ap.add_argument("--warmup", type=int, default=1000)
    ap.add_argument("--probe-bench", action="store_true", help="only measure the probe cost of every timestamp implementation")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    c = Campaign(a)
    if a.probe_bench:
        c.probe_bench()
        return 0
    benches = list(BENCHES) if a.bench == "all" else a.bench.split(",")
    stages = a.stages.split(",")
    for b in benches:
        if b not in BENCHES:
            sys.exit(f"unknown benchmark {b}")
        for s in stages:
            print(f"=== {b}: {s}", file=sys.stderr)
            getattr(c, s)(b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
