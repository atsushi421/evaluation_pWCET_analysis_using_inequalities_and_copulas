#!/usr/bin/env python3
"""End-to-end test of the job mode: a three-thread C++ program records 3000 job
invocations through IPOINT_JOB_BEGIN/END into IPOINT_OUT_DIR, the per-thread
files are merged by autoware_trace_merge.py and parsed by ipoint_parse.py with
a hand-written schema. Checks run counts, per-unit sample counts, the
alternatives taken and the end-to-end times."""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

PROGRAM = r'''
#define IPOINT_IMPLEMENTATION
#define IPOINT_MODE_TIMING
#include "ipoint.h"
#include <thread>
#include <vector>
static void leaf(int k) { IPOINT(3); volatile int x = 0; for (int i = 0; i < k; i++) x += i; IPOINT(4); }
static void job(int k) {
  IPOINT_JOB_BEGIN(1);
  leaf(k % 50 + 1);
  if (k % 2) { IPOINT(5); IPOINT(6); } else { IPOINT(7); }
  IPOINT_JOB_END(2);
}
int main() {
  std::vector<std::thread> th;
  for (int t = 0; t < 3; t++) th.emplace_back([t] { for (int i = 0; i < 1000; i++) job(i + t); });
  for (auto &x : th) x.join();
  ipoint_flush_all();  // every thread is idle: write the remainder and the final meta.json
  return 0;
}
'''

SCHEMA = {
    "source": "jobmode.cpp", "source_sha256": "", "cflags": [], "policy": {}, "entry_function": "job", "max_id": 7,
    "lang": "c++", "id_base": 0,
    "units": [
        {"uid": "job", "kind": "function", "parent": None, "depth": 0, "entry": 1, "exit": 2, "instrumented": True,
         "job": True, "children": ["job.if1"]},
        {"uid": "leaf", "kind": "function", "parent": None, "depth": 0, "entry": 3, "exit": 4, "instrumented": True},
        {"uid": "job.if1", "kind": "branch", "parent": "job", "depth": 1, "instrumented": False,
         "children": ["job.if1.then", "job.if1.else"]},
        {"uid": "job.if1.then", "kind": "alternative", "parent": "job.if1", "depth": 1, "entry": 5, "exit": 6,
         "instrumented": True},
        {"uid": "job.if1.else", "kind": "alternative", "parent": "job.if1", "depth": 1, "entry": 7, "exit": 7,
         "instrumented": True, "empty": True},
    ],
}


def main():
    with tempfile.TemporaryDirectory() as wd:
        src = os.path.join(wd, "jobmode.cpp")
        with open(src, "w") as f:
            f.write(PROGRAM)
        exe = os.path.join(wd, "jobmode")
        subprocess.run(["g++", "-O2", "-std=c++17", "-I" + os.path.join(ROOT, "include"), src, "-o", exe, "-pthread"], check=True)
        out = os.path.join(wd, "replay0")
        os.makedirs(out)
        env = dict(os.environ, IPOINT_OUT_DIR=out, IPOINT_BUF_RECORDS="4096", IPOINT_TAG="jobmode")
        subprocess.run([exe], check=True, env=env)
        merged = os.path.join(wd, "merged")
        subprocess.run([sys.executable, os.path.join(ROOT, "autoware", "tools", "autoware_trace_merge.py"), out,
                        "--out", merged, "--replay-stride", "1000000"], check=True)
        schema_path = os.path.join(wd, "schema.json")
        with open(schema_path, "w") as f:
            json.dump(SCHEMA, f)
        parsed = os.path.join(wd, "parsed")
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ipoint_parse.py"), "--schema", schema_path,
                        "--trace-dir", merged, "--out", parsed, "--ns"], check=True)
        with open(os.path.join(merged, "meta.json")) as f:
            meta = json.load(f)
        assert meta["n_runs"] == 3000, meta["n_runs"]
        assert 1e9 < meta["tsc_hz_start"] < 5e9, meta["tsc_hz_start"]
        st = json.load(open(os.path.join(parsed, "stats.json")))
        assert st["runs_parsed"] == 3000
        assert st["units"]["job"]["n"] == 3000 and st["units"]["leaf"]["n"] == 3000
        assert st["units"]["job.if1.then"]["n"] == 1500 and st["units"]["job.if1.else"]["n"] == 1500
        assert st["units"]["job.if1"]["alt_counts"] == [1500, 1500]
        assert not st["implicit_closes"] and not st["unmatched_exits"]
        e2e = np.load(os.path.join(parsed, "e2e.npy"))
        assert len(e2e) == 3000 and e2e.min() > 0 and np.median(e2e) < 1e5, (len(e2e), e2e.min(), np.median(e2e))
        runs = np.load(os.path.join(parsed, "units", "job.run.npy"))
        assert len(set(runs.tolist())) == 3000, "run indices not unique"
        job_s = np.load(os.path.join(parsed, "units", "job.npy"))
        leaf_s = np.load(os.path.join(parsed, "units", "leaf.npy"))
        assert (job_s >= leaf_s).all(), "job shorter than its leaf"
        print(f"job mode OK: {meta['n_runs']} runs, median job {np.median(job_s):.0f} ns, leaf {np.median(leaf_s):.0f} ns, "
              f"tsc {meta['tsc_hz_start'] / 1e6:.3f} MHz")
    return 0


def test_jobmode():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
