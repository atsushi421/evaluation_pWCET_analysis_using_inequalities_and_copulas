#!/usr/bin/env python3
"""Diff and merge of the monotone-curve recompute (results/jobs/mono*, batch6/batch7) into the stored estimates.

    .venv/bin/python tools/merge_monotone.py --diff [--out results/tables/monotone_diff.md]
    .venv/bin/python tools/merge_monotone.py --apply

The job files are the source of truth: every (job, window, method) whose JSON exists is compared
with (--diff) or written over (--apply) the stored entry. Stored file per job:
  traces_fine                      -> results/estimates_fine/<bench>.json
  window_size 100000               -> results/estimates_n1e5/<bench>.json
  window 0                         -> results/estimates/<bench>.json
  windows 1..9                     -> results/estimates_multiwindow/<bench>.json
--apply keeps the stored `seconds` (measured in the original run) and records the recompute time
in `seconds_monotone`.
"""
import argparse
import json
import os
from collections import defaultdict

import numpy as np

JOB_FILES = ("results/jobs/batch6.txt", "results/jobs/batch7.txt")
P_EVAL = ("0.0001", "1e-05", "1e-06")
METHOD_ORDER = ["E2E-CHB", "E2E-MEMIK", "CHB-COP", "CHB-IND", "CHB-COMONO", "MEMIK-COP"]


def jobs():
    for jf in JOB_FILES:
        for line in open(jf):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            f = line.split()
            yield dict(traces=f[0], bench=f[1], windows=f[2].split(","), methods=f[3].split(","),
                       wsize=int(f[4]), out=f[5])


def target_dir(job, w):
    if job["traces"].endswith("traces_fine"):
        return "results/estimates_fine"
    if job["wsize"] == 100000:
        return "results/estimates_n1e5"
    return "results/estimates" if w == "0" else "results/estimates_multiwindow"


def collect():
    """{(stored_file, window, method): new_entry}; also the list of jobs without a JSON."""
    new, missing = {}, []
    for job in jobs():
        path = os.path.join(job["out"], job["bench"] + ".json")
        if not os.path.exists(path):
            missing.append(job["out"])
            continue
        d = json.load(open(path))
        for w in job["windows"]:
            for m in job["methods"]:
                key = (os.path.join(target_dir(job, w), job["bench"] + ".json"), w, m)
                new[key] = d["windows"][w][m]
    return new, missing


def fmt(x):
    return "inf" if not np.isfinite(x) else f"{x:.3f}"


def diff(new, missing, out):
    stored = {}
    rows = []                      # (file, bench, w, m, p, old, new, rel)
    for (f, w, m), e in new.items():
        if f not in stored:
            stored[f] = json.load(open(f))
        o = stored[f]["windows"][w][m]
        for p in P_EVAL:
            a, b = o["tightness"][p], e["tightness"][p]
            rel = (b / a - 1.0) if np.isfinite(a) and np.isfinite(b) and a else (0.0 if a == b else np.inf)
            rows.append((f, stored[f]["bench"], w, m, p, a, b, rel))
    L = []
    L.append("# Monotone-curve recompute vs stored estimates\n")
    L.append(f"Jobs without JSON: {len(missing)}" + (" (" + ", ".join(missing[:20]) + (" ..." if len(missing) > 20 else "") + ")" if missing else "") + "\n")
    L.append(f"Compared entries: {len(new)} (bench, window, method); {len(rows)} values.\n")
    # 1. distribution of relative change per method and p
    L.append("## Relative change new/old - 1 (all stored sets)\n")
    L.append("| method | p | n | changed | median | p90 | max | min |")
    L.append("|---|---|---|---|---|---|---|---|")
    for m in METHOD_ORDER:
        for p in P_EVAL:
            r = np.array([x[7] for x in rows if x[3] == m and x[4] == p])
            if not len(r):
                continue
            fin = r[np.isfinite(r)]
            ninf = int((~np.isfinite(r)).sum())
            ch = int((np.abs(fin) > 1e-9).sum()) + ninf
            L.append(f"| {m} | {p} | {len(r)} | {ch} | {np.median(fin)*100:+.2f}% | {np.percentile(fin, 90)*100:+.2f}% | "
                     f"{fin.max()*100:+.2f}% | {fin.min()*100:+.2f}% |" + (f" +{ninf} to/from inf" if ninf else ""))
    # 2. unsafe counts over the 120 windows (w0 + 1..9) per method and p
    L.append("\n## Unsafe windows (tightness < 1) over window 0 + windows 1..9, 12 kernels\n")
    L.append("| method | p | old | new |")
    L.append("|---|---|---|---|")
    for m in METHOD_ORDER:
        for p in P_EVAL:
            sel = [x for x in rows if x[3] == m and x[4] == p and x[0].split("/")[1] in ("estimates", "estimates_multiwindow")]
            if not sel:
                continue
            L.append(f"| {m} | {p} | {sum(x[5] < 1 for x in sel)} | {sum(x[6] < 1 for x in sel)} | (n={len(sel)})")
    for setname in ("estimates_n1e5", "estimates_fine"):
        sel_all = [x for x in rows if x[0].split("/")[1] == setname]
        if not sel_all:
            continue
        L.append(f"\n## {setname}: old -> new\n")
        L.append("| bench | method | p=1e-4 | p=1e-5 | p=1e-6 |")
        L.append("|---|---|---|---|---|")
        seen = sorted({(x[1], x[3]) for x in sel_all}, key=lambda t: (t[0], METHOD_ORDER.index(t[1])))
        for b, m in seen:
            cells = []
            for p in P_EVAL:
                x = next(x for x in sel_all if x[1] == b and x[3] == m and x[4] == p)
                cells.append(f"{fmt(x[5])} -> {fmt(x[6])}" if abs(x[7]) > 1e-9 or not np.isfinite(x[7]) else fmt(x[5]))
            L.append(f"| {b} | {m} | " + " | ".join(cells) + " |")
    # 3. largest changes
    L.append("\n## Largest relative changes\n")
    L.append("| set | bench | window | method | p | old | new | change |")
    L.append("|---|---|---|---|---|---|---|---|")
    big = sorted(rows, key=lambda x: -(abs(x[7]) if np.isfinite(x[7]) else 1e9))[:25]
    for x in big:
        if abs(x[7]) < 1e-9:
            break
        L.append(f"| {x[0].split('/')[1]} | {x[1]} | {x[2]} | {x[3]} | {x[4]} | {fmt(x[5])} | {fmt(x[6])} | "
                 f"{'inf' if not np.isfinite(x[7]) else f'{x[7]*100:+.1f}%'} |")
    # 4. select windows 8 and 9 (the worst non-monotone unit curves)
    L.append("\n## select windows 8 and 9 (worst non-monotone unit curves)\n")
    L.append("| window | method | p=1e-4 | p=1e-5 | p=1e-6 |")
    L.append("|---|---|---|---|---|")
    for w in ("8", "9"):
        for m in METHOD_ORDER:
            sel = [x for x in rows if x[1] == "select" and x[2] == w and x[3] == m and "multiwindow" in x[0]]
            if sel:
                L.append(f"| {w} | {m} | " + " | ".join(f"{fmt(x[5])} -> {fmt(x[6])}" for x in sorted(sel, key=lambda x: P_EVAL.index(x[4]))) + " |")
    # 5. E2-14
    old_p, new_p = "results/e214/estimates.json", "results/e214/estimates_monotone.json"
    if os.path.exists(old_p) and os.path.exists(new_p):
        o, n = json.load(open(old_p)), json.load(open(new_p))
        L.append("\n## E2-14 (qsort-exam killer input): tightness vs killer median, old -> new\n")
        L.append("| method | p=1e-4 | p=1e-5 | p=1e-6 |")
        L.append("|---|---|---|---|")
        for m in o:
            if not isinstance(o[m], dict) or "tightness" not in o[m]:
                continue
            cells = []
            for p in P_EVAL:
                a, b = o[m]["tightness"].get(p), n.get(m, {}).get("tightness", {}).get(p)
                cells.append(f"{fmt(a)} -> {fmt(b)}" if b is not None else fmt(a))
            L.append(f"| {m} | " + " | ".join(cells) + " |")
    text = "\n".join(L) + "\n"
    if out:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w").write(text)
    print(text)


def apply(new, missing):
    if missing:
        raise SystemExit(f"{len(missing)} jobs have no JSON; finish the recompute first")
    by_file = defaultdict(dict)
    for (f, w, m), e in new.items():
        by_file[f][(w, m)] = e
    for f, entries in by_file.items():
        d = json.load(open(f))
        for (w, m), e in entries.items():
            old = d["windows"][w][m]
            e = dict(e)
            e["seconds_monotone"] = e["seconds"]
            e["seconds"] = old["seconds"]
            d["windows"][w][m] = e
        with open(f, "w") as fh:
            json.dump(d, fh, indent=1)
        print(f"{f}: replaced {len(entries)} entries")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default="results/tables/monotone_diff.md")
    a = ap.parse_args()
    new, missing = collect()
    if a.diff:
        diff(new, missing, a.out)
    if a.apply:
        apply(new, missing)


if __name__ == "__main__":
    main()
