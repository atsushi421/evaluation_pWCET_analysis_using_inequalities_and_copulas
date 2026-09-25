#!/usr/bin/env python3
"""Turn the parsed traces of a replay campaign into the per-benchmark trace
directories that the estimation pipeline reads (estimation.data.Bench).

    make_bench.py --campaign traces/autoware [--out traces/autoware/bench]
        [--rules analysis.json] [--targets targets.json] [--only cb1]...

For every callback of the rules file the nominal runs are selected by their
path signature (paths.csv: a run is excluded when its signature matches one of
the "exclude" patterns, or does not contain every "require" pattern),
renumbered in trace order and written as
<out>/<cb>/parsed/{e2e_all.npy, units/<uid>{,.run,.self,.iters}.npy}. The
schemas of the packages loaded into the process are merged into
<out>/<cb>/schema_timing.json with the job function as entry, the static loop
bounds of the rules file ("bounds": uid -> [bound, source]) and the loop
bodies listed under "demote" marked uninstrumented (their loop becomes a leaf
of the composition; its samples are the whole loop duration). overhead.json
carries tick_ns = 1 because the parser wrote nanoseconds.
<out>/<cb>/selection.json reports the runs excluded per rule and the observed
iteration maximum of every bounded loop over the nominal runs; a maximum above
its bound aborts unless --allow-bound-violation is given.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
AW = os.path.dirname(HERE)
TOOLS = os.path.join(os.path.dirname(AW), "tools")
sys.path.insert(0, TOOLS)
from ipoint_parse import merge_schemas  # noqa: E402
from ipoint_schema import Schema, Unit  # noqa: E402


def load_paths(path: str) -> tuple[np.ndarray, list[str]]:
    """Run ids (replay * 10^6 + invocation, strictly increasing in trace order) and signatures."""
    runs, sigs = [], []
    with open(path) as f:
        for row in csv.DictReader(f):
            runs.append(int(row["run"]))
            sigs.append(row["signature"])
    runs = np.asarray(runs, dtype=np.int64)
    if len(runs) and not np.all(np.diff(runs) > 0):
        sys.exit(f"{path}: run ids are not strictly increasing")
    return runs, sigs


def rows_of(run_ids: np.ndarray, runs: np.ndarray, what: str) -> np.ndarray:
    pos = np.searchsorted(run_ids, runs)
    if pos.max(initial=-1) >= len(run_ids) or not np.array_equal(run_ids[np.minimum(pos, len(run_ids) - 1)], runs):
        sys.exit(f"{what}: run ids not found in paths.csv")
    return pos


def select_runs(sigs: list[str], rules: dict) -> tuple[np.ndarray, dict]:
    excl = [(p, re.compile(p)) for p in rules.get("exclude", [])]
    req = [(p, re.compile(p)) for p in rules.get("require", [])]
    keep = np.ones(len(sigs), dtype=bool)
    counts = {p: 0 for p, _ in excl}
    counts.update({"missing " + p: 0 for p, _ in req})
    for i, s in enumerate(sigs):
        for p, rx in excl:
            if rx.search(s):
                counts[p] += 1
                keep[i] = False
        for p, rx in req:
            if not rx.search(s):
                counts["missing " + p] += 1
                keep[i] = False
    return keep, counts


def merged_schema(spec: dict, cb: str, rules: dict) -> Schema:
    schemas = []
    for pkg in spec["processes"][cb]["packages"]:
        for p in sorted(glob.glob(os.path.join(AW, "schemas", pkg, "*.schema.json"))):
            schemas.append(Schema.from_json(p))
    jobs = [u.uid for s in schemas for u in s.units if u.job]
    if len(jobs) != 1:
        sys.exit(f"{cb}: expected one job function in the schemas, found {jobs}")
    schema = merge_schemas(schemas, jobs[0])
    by = schema.by_uid()
    for uid, (bound, source) in rules.get("bounds", {}).items():
        u = by[uid]
        if u.kind != "loop":
            sys.exit(f"{cb}: bound given for {uid} which is a {u.kind}, not a loop")
        u.bound, u.bound_source = int(bound), source
    for uid in rules.get("demote", {}):
        u = by[uid]
        if u.kind != "loop_body":
            sys.exit(f"{cb}: demote given for {uid} which is a {u.kind}, not a loop_body")
        for d in descendants(by, uid):
            d.instrumented = False
        u.instrumented = False
    errors = schema.validate()
    if errors:
        sys.exit(f"{cb}: merged schema invalid: " + "; ".join(errors[:5]))
    return schema


def descendants(by: dict, uid: str) -> list:
    out = []
    for c in by[uid].children:
        out.append(by[c])
        out += descendants(by, c)
    return out


def structural_eff(by: dict, uid: str, present: set) -> list:
    """Nearest present descendants over the schema's structural children (estimation.data.Bench.effective_children)."""
    out = []
    for c in by[uid].children:
        if by[c].instrumented and c in present:
            out.append(c)
        else:
            out += structural_eff(by, c, present)
    return out


def attach_callees(schema: Schema, parsed: str, data: dict, entry: str) -> tuple[dict, list]:
    """Give every instrumented callee function a place in the composition tree.

    The parser subtracts every unit nested at run time (callee functions included)
    from a container's self time, while the schema lists only the structural
    children, so a callee's time would drop out of the composition. A function
    instance whose call site (the unit on top of the stack when it ran) is a
    container of the composition (self samples and at least one structural child
    present) is added below that call site; instances called from a leaf are
    already inside the leaf's sample. A function whose composed instances all
    come from one call site and none from a leaf moves below it with its subtree;
    otherwise every container call site gets a leaf unit <F>@<site> holding the
    durations of the instances it called.
    Returns the virtual units {uid: (source uid, instance mask)} and a report."""
    by = schema.by_uid()
    present = set(data)
    container = {u for u in present if os.path.exists(os.path.join(parsed, "units", u + ".self.npy"))
                 and structural_eff(by, u, present)}
    virtual, report = {}, []
    next_id = schema.max_id
    for uid in sorted(present):
        u = by[uid]
        if u.kind != "function" or uid == entry:
            continue
        cpath = os.path.join(parsed, "units", uid + ".caller.npy")
        if not os.path.exists(cpath):
            sys.exit(f"{uid}: no call-site record; re-parse with the current ipoint_parse.py")
        names = json.load(open(os.path.join(parsed, "units", uid + ".callers.json")))
        row, m = data[uid]
        callers = np.asarray(names, dtype=object)[np.load(cpath)][m] if names else np.asarray([], dtype=object)
        sites = sorted({c for c in callers if c in container})
        n_leaf = int(sum(1 for c in callers if c not in container))
        entry_r = {"function": uid, "instances": int(m.sum()), "in_leaves_or_outside": n_leaf, "sites": {}}
        if not sites:
            entry_r["mode"] = "inside leaves"
        elif len(sites) == 1 and n_leaf == 0:
            t = by[sites[0]]
            u.parent = t.uid
            t.children.append(uid)
            entry_r["mode"] = "moved"
            entry_r["sites"][t.uid] = int(m.sum())
        else:
            entry_r["mode"] = "per-site leaves"
            for site in sites:
                vuid = f"{uid}@{site}"
                sel = callers == site
                next_id += 1
                schema.units.append(Unit(uid=vuid, kind="function", parent=site, depth=by[site].depth + 1,
                                         line=u.line, stmt="call", entry=next_id, exit=next_id, instrumented=True,
                                         qualified=u.qualified))
                by[site].children.append(vuid)
                virtual[vuid] = (uid, sel)
                entry_r["sites"][site] = int(sel.sum())
        report.append(entry_r)
    schema.max_id = next_id
    return virtual, report


def coverage(dst_root: str, cb: str, n: int = 10_000) -> dict:
    """Composed per-run time (self of every container + every leaf) over the end-to-end time,
    on the first n nominal runs: the composition must account for the whole run."""
    sys.path.insert(0, os.path.join(os.path.dirname(AW), ".."))
    from estimation.data import Bench  # noqa: E402
    b = Bench(dst_root, cb)
    hi = min(n, len(b.e2e_all))

    def walk(uid):
        eff = b.effective_children(uid)
        if not eff:
            return b.per_run_totals(uid, 0, hi)
        s = b.per_run_totals(uid, 0, hi, "self") if b.units[uid].self_vals is not None else 0.0
        return s + sum(walk(c.uid) for c in eff)

    r = walk(b.schema.entry_function) / b.e2e_all[:hi]
    return {"runs": int(hi), "median": float(np.median(r)), "min": float(r.min()), "p1": float(np.quantile(r, 0.01)),
            "p99": float(np.quantile(r, 0.99)), "max": float(r.max())}


def drop_warmup(run_ids: np.ndarray, keep: np.ndarray, warmup: int) -> int:
    """Drop the first `warmup` nominal runs of every replay (run id = replay * 10^6 + invocation):
    the first invocations after a process start pay one-time costs (first publish, first touch of code
    and data), which the per-replay restart repeats once per replay instead of once per boot."""
    if warmup <= 0:
        return 0
    rep = run_ids // 1_000_000
    rank = np.zeros(len(keep), dtype=np.int64)
    seen: dict = {}
    for i in np.flatnonzero(keep):
        rank[i] = seen.get(rep[i], 0)
        seen[rep[i]] = rank[i] + 1
    drop = keep & (rank < warmup)
    keep &= ~drop
    return int(drop.sum())


def convert(campaign: str, out: str, cb: str, rules: dict, spec: dict, allow_violation: bool, warmup: int = 0) -> dict:
    parsed = os.path.join(campaign, "parsed", cb)
    run_ids, sigs = load_paths(os.path.join(parsed, "paths.csv"))
    e2e = np.load(os.path.join(parsed, "e2e.npy"))
    if len(e2e) != len(sigs):
        sys.exit(f"{cb}: {len(e2e)} end-to-end samples but {len(sigs)} runs in paths.csv")
    keep, counts = select_runs(sigs, rules)
    n_warm = drop_warmup(run_ids, keep, warmup)
    remap = np.full(len(sigs), -1, dtype=np.int64)      # row of paths.csv -> new run index
    remap[keep] = np.arange(int(keep.sum()))
    schema = merged_schema(spec, cb, rules)
    by = schema.by_uid()
    dropped = {uid for uid in by if not by[uid].instrumented}

    data, empty, observed = {}, [], {}
    for p in sorted(glob.glob(os.path.join(parsed, "units", "*.run.npy"))):
        uid = os.path.basename(p)[: -len(".run.npy")]
        if uid not in by:
            sys.exit(f"{cb}: unit {uid} of the parsed traces is not in the merged schema")
        if uid in dropped:
            continue
        row = rows_of(run_ids, np.load(p).astype(np.int64), f"{cb}/{uid}")
        m = keep[row]
        if not m.any():
            empty.append(uid)
            continue
        data[uid] = (row, m)
        if by[uid].kind == "loop" and by[uid].bound is not None:
            iters = np.load(os.path.join(parsed, "units", uid + ".iters.npy"))[m]
            observed[uid] = {"bound": by[uid].bound, "source": by[uid].bound_source,
                             "observed_max": int(iters.max()), "instances": int(m.sum())}
            if iters.max() > by[uid].bound:
                msg = f"{cb}: {uid} iterated {int(iters.max())} times > static bound {by[uid].bound}"
                if not allow_violation:
                    sys.exit(msg)
                print("WARNING:", msg, file=sys.stderr)
    bodies_without_bound = [u.uid for u in schema.units if u.kind == "loop_body" and u.instrumented
                            and u.uid in data and by[u.parent].bound is None]
    if bodies_without_bound:
        sys.exit(f"{cb}: timed loop bodies without a static bound: {bodies_without_bound}")
    virtual, attached = attach_callees(schema, parsed, data, schema.entry_function)

    dst = os.path.join(out, cb)
    udst = os.path.join(dst, "parsed", "units")
    if os.path.isdir(udst):
        for f in glob.glob(os.path.join(udst, "*.npy")):
            os.remove(f)
    os.makedirs(udst, exist_ok=True)
    np.save(os.path.join(dst, "parsed", "e2e_all.npy"), e2e[keep])
    for uid, (row, m) in data.items():
        np.save(os.path.join(udst, uid + ".run.npy"), remap[row[m]])
        for suffix in ("", ".self", ".iters"):
            src = os.path.join(parsed, "units", uid + suffix + ".npy")
            if os.path.exists(src):
                np.save(os.path.join(udst, uid + suffix + ".npy"), np.load(src)[m])
    for vuid, (src_uid, sel) in virtual.items():
        row, m = data[src_uid]
        np.save(os.path.join(udst, vuid + ".run.npy"), remap[row[m]][sel])
        np.save(os.path.join(udst, vuid + ".npy"), np.load(os.path.join(parsed, "units", src_uid + ".npy"))[m][sel])
    errors = schema.validate()
    if errors:
        sys.exit(f"{cb}: schema invalid after attaching the callees: " + "; ".join(errors[:5]))
    schema.to_json(os.path.join(dst, "schema_timing.json"))
    with open(os.path.join(dst, "overhead.json"), "w") as f:
        json.dump({"tick_ns": 1.0, "unit": "ns", "note": "samples were written in nanoseconds by ipoint_parse.py --ns"}, f, indent=1)
    cov = coverage(out, cb)
    sel = {"job": schema.entry_function, "runs_total": len(sigs), "runs_nominal": int(keep.sum()),
           "excluded": counts, "warmup_per_replay": warmup, "excluded_warmup": n_warm, "rules": {k: rules[k] for k in ("exclude", "require") if k in rules},
           "bounds": observed, "demoted": rules.get("demote", {}), "callees": attached, "coverage": cov,
           "units_written": len(data) + len(virtual), "units_without_nominal_instances": empty}
    with open(os.path.join(dst, "selection.json"), "w") as f:
        json.dump(sel, f, indent=1)
    if abs(cov["median"] - 1.0) > 1e-3:
        sys.exit(f"{cb}: the composition covers {cov['median']:.4f} of the end-to-end time (median over runs), not 1")
    return sel


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--out", default=None, help="default <campaign>/bench")
    ap.add_argument("--rules", default=os.path.join(AW, "analysis.json"))
    ap.add_argument("--targets", default=os.path.join(AW, "targets.json"))
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--allow-bound-violation", action="store_true")
    ap.add_argument("--warmup", type=int, default=0, help="drop the first N nominal runs of every replay")
    a = ap.parse_args(argv)
    with open(a.rules) as f:
        rules = json.load(f)
    with open(a.targets) as f:
        spec = json.load(f)
    out = a.out or os.path.join(a.campaign, "bench")
    for cb, r in rules.items():
        if cb.startswith("_") or (a.only and cb not in a.only):
            continue
        if not os.path.isdir(os.path.join(a.campaign, "parsed", cb)):
            print(f"{cb}: no parsed traces, skipped")
            continue
        sel = convert(a.campaign, out, cb, r, spec, a.allow_bound_violation, a.warmup)
        modes = {}
        for c in sel["callees"]:
            modes[c["mode"]] = modes.get(c["mode"], 0) + 1
        print(f"{cb}: {sel['runs_nominal']}/{sel['runs_total']} nominal runs, excluded {sel['excluded']}, warm-up {sel['excluded_warmup']}, "
              f"{sel['units_written']} units, callees {modes}, coverage median {sel['coverage']['median']:.4f} "
              f"[{sel['coverage']['min']:.4f}, {sel['coverage']['max']:.4f}], "
              f"bounds {[(u, v['observed_max'], v['bound']) for u, v in sel['bounds'].items()]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
