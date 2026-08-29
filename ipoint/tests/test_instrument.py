#!/usr/bin/env python3
"""Instrument the toy programs with --all, build them in COVERAGE mode with a
generated driver, run them and compare the hit counts of every unit with the
values expected from the program logic. Runs under pytest or as a script."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOY = os.path.join(HERE, "toy")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ipoint_schema import Schema  # noqa: E402

# toy -> (driver statements, {uid: (entry_hits, exit_hits)})
CASES = {
    "nested_loops.c": ("int a[12] = {0}; nested(a);", {
        "nested": (1, 1), "nested.L1": (1, 1), "nested.L1.body": (3, 3),
        "nested.L1.body.L1": (3, 3), "nested.L1.body.L1.body": (12, 12)}),
    "early_return.c": ("classify(-5); classify(0); classify(2); nothing(1); nothing(0);", {
        # classify(-5): then of if1. classify(0): else marker of if1, then of if2.
        # classify(2) -> classify(1) -> classify(0): three calls, if1 else x3, if2 then x1 else x2.
        "classify": (5, 5), "classify.if1.then": (1, 1), "classify.if1.else": (4, 4),
        "classify.if2.then": (2, 2), "classify.if2.else": (2, 2),
        "nothing": (2, 2), "nothing.if1.then": (1, 1), "nothing.if1.else": (1, 1)}),
    "elseless_if.c": ("f(12); f(25); f(17); f(5);", {
        # x > 10 holds for 12, 25, 17; x > 20 only for 25; x > 15 for 17.
        "f": (4, 4), "f.if1.then": (3, 3), "f.if1.else": (1, 1), "f.if2.then": (1, 1),
        "f.if2.else": (3, 3), "f.if2.else.if1.then": (1, 1), "f.if2.else.if1.else": (2, 2)}),
    "break_continue.c": ("g(10);", {
        # i = 1..8: odd -> continue (4), i=8 -> break; s = 2+4+6 = 12 -> do-while 12 times.
        "g": (1, 1), "g.L1": (1, 1), "g.L1.body": (8, 8), "g.L1.body.if1.then": (4, 4),
        "g.L1.body.if1.else": (4, 4), "g.L1.body.if2.then": (1, 1), "g.L1.body.if2.else": (3, 3),
        "g.L2": (1, 1), "g.L2.body": (12, 12)}),
    "single_stmt.c": ("h(4); h(0);", {
        "h": (2, 2), "h.L1": (2, 2), "h.L1.body": (3, 3), "h.if1.then": (1, 1),
        "h.if1.then.L1": (1, 1), "h.if1.then.L1.body": (2, 2), "h.if1.else": (1, 1)}),
    "else_if_chain.c": ("chain(2, 1); chain(1, 1); chain(0, 1); chain(0, 5);", {
        "chain": (4, 4), "chain.if1.then": (1, 1), "chain.if1.else": (3, 3),
        "chain.if1.else.if1.then": (1, 1), "chain.if1.else.if1.else": (2, 2)}),
}

DRIVER = r'''
#define IPOINT_IMPLEMENTATION
#include "%(inst)s"
#include <stdio.h>
int main(void) {
  ipoint_thread_init(1 << 16);
  %(calls)s
  uint32_t hist[%(n)d];
  ipoint_hits_copy_and_clear(hist, %(max_id)d);
  for (int i = 0; i <= %(max_id)d; i++) printf("%%u%%s", hist[i], i == %(max_id)d ? "\n" : " ");
  return 0;
}
'''


def run_case(toy, calls, expected, workdir):
    src = os.path.join(TOY, toy)
    inst = os.path.join(workdir, toy.replace(".c", ".ipoint.c"))
    schema_path = inst + ".schema.json"
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ipoint_instrument.py"), src, "--all",
                    "--out", inst, "--schema", schema_path], check=True, capture_output=True)
    sch = Schema.from_json(schema_path)
    assert not sch.validate(), sch.validate()
    driver = os.path.join(workdir, "driver_" + toy)
    with open(driver, "w") as f:
        f.write(DRIVER % {"inst": inst, "calls": calls, "n": sch.max_id + 1, "max_id": sch.max_id})
    exe = os.path.join(workdir, toy.replace(".c", ""))
    subprocess.run(["gcc", "-O2", "-Wall", "-Wextra", "-Werror", "-std=gnu11", "-DIPOINT_MODE_COVERAGE",
                    "-I" + os.path.join(ROOT, "include"), driver, "-o", exe], check=True)
    out = subprocess.run([exe], check=True, capture_output=True, text=True).stdout
    hist = [int(x) for x in out.split()]
    by = sch.by_uid()
    ids = set()
    for u in sch.units:
        if u.entry is not None:
            assert u.entry not in ids and (u.exit == u.entry or u.exit not in ids), "duplicate ipoint id"
            ids.update({u.entry, u.exit})
    for uid, (e, x) in expected.items():
        u = by[uid]
        assert u.instrumented, uid
        got = (hist[u.entry], hist[u.exit])
        assert got == (e, x), f"{toy}:{uid}: expected {(e, x)} got {got}"
    # every instrumented, non-empty unit closes as often as it opens
    for u in sch.instrumented_units():
        if not u.empty:
            assert hist[u.entry] == hist[u.exit], f"{toy}:{u.uid}: entry {hist[u.entry]} != exit {hist[u.exit]}"
    return len(expected)


# partial policies: (toy, extra instrumenter args). Compiled with -Werror and
# executed; every instrumented unit must open and close equally often and the
# function-level hit counts must not depend on the policy.
POLICIES = [
    ("break_continue.c", ["--max-depth", "1"]),
    ("break_continue.c", ["--all", "--exclude-unit", "g.L1.body.if1.then", "--exclude-unit", "g.L1.body.if2.then"]),
    ("break_continue.c", ["--all", "--exclude-unit", "g.L1.body"]),
    ("early_return.c", ["--all", "--exclude-unit", "classify.if1.then", "--exclude-unit", "nothing.if1.then"]),
    ("single_stmt.c", ["--all", "--exclude-unit", "h.if1.then", "--exclude-unit", "h.L1.body"]),
    ("single_stmt.c", ["--functions-only"]),
    ("elseless_if.c", ["--all", "--exclude-unit", "f.if1.then", "--exclude-unit", "f.if2.else"]),
    ("nested_loops.c", ["--all", "--exclude-unit", "nested.L1.body.L1.body"]),
]


def run_policy(toy, extra, workdir, tag):
    calls, expected = CASES[toy]
    src = os.path.join(TOY, toy)
    inst = os.path.join(workdir, f"{tag}_{toy}".replace(".c", ".ipoint.c"))
    schema_path = inst + ".schema.json"
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ipoint_instrument.py"), src,
                    "--out", inst, "--schema", schema_path] + extra, check=True, capture_output=True)
    sch = Schema.from_json(schema_path)
    assert not sch.validate(), sch.validate()
    driver = os.path.join(workdir, f"driver_{tag}_" + toy)
    with open(driver, "w") as f:
        f.write(DRIVER % {"inst": inst, "calls": calls, "n": sch.max_id + 1, "max_id": sch.max_id})
    exe = os.path.join(workdir, f"{tag}_" + toy.replace(".c", ""))
    subprocess.run(["gcc", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-misleading-indentation", "-std=gnu11",
                    "-DIPOINT_MODE_COVERAGE", "-I" + os.path.join(ROOT, "include"), driver, "-o", exe], check=True)
    hist = [int(x) for x in subprocess.run([exe], check=True, capture_output=True, text=True).stdout.split()]
    by = sch.by_uid()
    for u in sch.instrumented_units():
        if not u.empty:
            assert hist[u.entry] == hist[u.exit], f"{tag}:{toy}:{u.uid}: entry {hist[u.entry]} != exit {hist[u.exit]}"
        if u.uid in expected:
            assert (hist[u.entry], hist[u.exit]) == expected[u.uid] or u.empty, f"{tag}:{toy}:{u.uid}"
    for u in sch.units:
        if u.entry is not None and not u.instrumented:
            assert hist[u.entry] == 0 and hist[u.exit] == 0, f"{tag}:{toy}:{u.uid}: probe of excluded unit fired"


def test_all_toys():
    with tempfile.TemporaryDirectory() as d:
        for toy, (calls, expected) in CASES.items():
            run_case(toy, calls, expected, d)


def test_policies():
    with tempfile.TemporaryDirectory() as d:
        for i, (toy, extra) in enumerate(POLICIES):
            run_policy(toy, extra, d, f"p{i}")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as d:
        n = 0
        for toy, (calls, expected) in CASES.items():
            n += run_case(toy, calls, expected, d)
            print(f"ok {toy}")
        for i, (toy, extra) in enumerate(POLICIES):
            run_policy(toy, extra, d, f"p{i}")
            print(f"ok policy {toy} {' '.join(extra)}")
        print(f"all {len(CASES)} toys and {len(POLICIES)} policies passed ({n} unit checks)")
