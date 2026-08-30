#!/usr/bin/env python3
"""C++ counterpart of test_instrument.py: instrument the toy C++ sources with
--all, build them in COVERAGE mode with a generated driver (g++ -Werror), run
them and compare the hit counts with the values expected from the program
logic. The first function of every file is also marked as --job so that the
IPOINT_JOB_BEGIN/END macros are exercised."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOY = os.path.join(HERE, "toy_cpp")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ipoint_schema import Schema  # noqa: E402

# toy -> (job, driver statements, {uid: (entry_hits, exit_hits)}); markers compare entry only
CASES = {
    "methods.cpp": ("Acc::sum_to",
                    "toy::Acc a(3); a.sum_to(0); a.sum_to(4); std::vector<int> v(3); a.fill(v); "
                    "(void)a.name(2); (void)a.name(-1); (void)toy::make(1); (void)toy::make(0); "
                    "if (toy::classify(3).second != 3 || toy::classify(0).first.ok || toy::classify(-2).second != 2) return 1; "
                    "if (toy::repeat(0).size() != 0 || toy::repeat(4).size() != 2) return 1;", {
        # sum_to(0): then of if1 (return). sum_to(4): else marker, loop of 4 iterations,
        # i = 0, 2 continue (then), i = 1, 3 else marker.
        "Acc::sum_to": (2, 2), "Acc::sum_to.if1.then": (1, 1), "Acc::sum_to.if1.else": (1, 1),
        "Acc::sum_to.L1": (1, 1), "Acc::sum_to.L1.body": (4, 4),
        "Acc::sum_to.L1.body.if1.then": (2, 2), "Acc::sum_to.L1.body.if1.else": (2, 2),
        # fill: range-for over 3 elements; the lambda is opaque
        "Acc::fill": (1, 1), "Acc::fill.L1": (1, 1), "Acc::fill.L1.body": (3, 3),
        "Acc::name": (2, 2), "Acc::name.if1.then": (1, 1), "Acc::name.if1.else": (1, 1),
        "make": (2, 2), "make.if1.then": (1, 1), "make.if1.else": (1, 1),
        # classify: braced-init-list returns of a std::pair (constructor cursors around the list)
        "classify": (3, 3), "classify.if1.then": (1, 1), "classify.if1.else": (2, 2),
        "classify.if2.then": (1, 1), "classify.if2.else": (1, 1),
        "repeat": (2, 2), "repeat.if1.then": (1, 1), "repeat.if1.else": (1, 1)}),
    "overload.cpp": ("E::est", "E e; (void)e.est(5); (void)e.est(0); (void)e.est(2.5);", {
        # est(int): 5, 0 and the nested est(1) from est(double)
        "E::est": (3, 3), "E::est.if1.then": (1, 1), "E::est.if1.else": (2, 2), "E::est#2": (1, 1)}),
    "trycatch.cpp": ("guarded", "(void)guarded(1); (void)guarded(0); int p = 1, q = 2; (void)pick(p, q, true); (void)pick(p, q, false); "
                     "update(20); update(5); update(-1); if (state() != 0) return 1;", {
        # guarded(1): the throw leaves the then-alternative without its exit probe
        "guarded": (2, 2), "guarded.if1.then": (1, 0), "guarded.if1.else": (1, 1),
        "pick": (2, 2), "pick.if1.then": (1, 1), "pick.if1.else": (1, 1),
        # update: `return set_state(...)` in a void function (20 -> if1, 5 -> if2, -1 -> fall through)
        "update": (3, 3), "update.if1.then": (1, 1), "update.if1.else": (2, 2),
        "update.if2.then": (1, 1), "update.if2.else": (1, 1), "set_state": (3, 3)}),
}

DRIVER = r'''
#define IPOINT_IMPLEMENTATION
#include "%(inst)s"
#include <cstdio>
#include <vector>
int main() {
  ipoint_thread_init(1 << 16);
  %(calls)s
  uint32_t hist[%(n)d];
  ipoint_hits_copy_and_clear(hist, %(max_id)d);
  for (int i = 0; i <= %(max_id)d; i++) std::printf("%%u%%s", hist[i], i == %(max_id)d ? "\n" : " ");
  return 0;
}
'''


def run_case(toy, job, calls, expected, workdir):
    src = os.path.join(TOY, toy)
    inst = os.path.join(workdir, toy.replace(".cpp", ".ipoint.cpp"))
    schema_path = inst + ".schema.json"
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ipoint_instrument.py"), src, "--lang", "c++",
                    "--all", "--job", job, "--id-base", "100", "--out", inst, "--schema", schema_path],
                   check=True, capture_output=True)
    sch = Schema.from_json(schema_path)
    assert not sch.validate(), sch.validate()
    assert sch.lang == "c++" and sch.id_base == 100
    with open(inst) as f:
        text = f.read()
    assert "IPOINT_JOB_BEGIN(" in text and "IPOINT_JOB_END(" in text, "job macros missing"
    driver = os.path.join(workdir, "driver_" + toy)
    with open(driver, "w") as f:
        f.write(DRIVER % {"inst": inst, "calls": calls, "n": sch.max_id + 1, "max_id": sch.max_id})
    exe = os.path.join(workdir, toy.replace(".cpp", ""))
    for mode in ("COVERAGE", "TIMING"):
        subprocess.run(["g++", "-O2", "-Wall", "-Wextra", "-Werror", "-std=c++17", "-DIPOINT_MODE_" + mode,
                        "-I" + os.path.join(ROOT, "include"), driver, "-o", exe + "_" + mode.lower()], check=True)
    out = subprocess.run([exe + "_coverage"], check=True, capture_output=True, text=True).stdout
    hist = [int(x) for x in out.split()]
    by = sch.by_uid()
    ids = set()
    for u in sch.units:
        if u.entry is not None:
            assert u.entry not in ids and (u.exit == u.entry or u.exit not in ids), "duplicate ipoint id"
            ids.add(u.entry)
            ids.add(u.exit)
    failures = []
    for uid, (ne, nx) in expected.items():
        u = by[uid]
        got = (hist[u.entry], hist[u.exit])
        if u.empty or u.entry == u.exit:
            ok = got[0] == ne
        else:
            ok = got == (ne, nx)
        if not ok:
            failures.append(f"{toy}:{uid}: expected {(ne, nx)}, got {got}")
    # every overload of the --job name is a job; the entry is the first definition
    job_unit = [u for u in sch.units if u.job]
    assert job_unit and job_unit[0].uid == sch.entry_function, "job unit / entry mismatch"
    return failures


def main():
    failures = []
    with tempfile.TemporaryDirectory() as wd:
        for toy, (job, calls, expected) in CASES.items():
            failures += run_case(toy, job, calls, expected, wd)
    for f in failures:
        print("FAIL", f)
    print(f"{len(CASES)} toy programs, {len(failures)} failures")
    return 1 if failures else 0


def test_toys():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
