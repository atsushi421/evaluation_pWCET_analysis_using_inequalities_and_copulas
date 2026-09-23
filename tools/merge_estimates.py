#!/usr/bin/env python3
"""Merge result JSONs of chb_cop_from_schema.py for one benchmark (union of windows and methods).

    .venv/bin/python tools/merge_estimates.py --into results/estimates_multiwindow/ndes.json part1.json part2.json ...

--into may be missing (created) or existing (entries of the parts replace equal window/method keys).
"""
import argparse
import json
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--into", required=True)
    ap.add_argument("parts", nargs="+")
    a = ap.parse_args()
    out = json.load(open(a.into)) if os.path.exists(a.into) else None
    for path in a.parts:
        d = json.load(open(path))
        if out is None:
            out = {**d, "windows": {}}
        if d["bench"] != out["bench"] or d["references"] != out["references"]:
            raise SystemExit(f"{path}: different benchmark or reference")
        for w, entries in d["windows"].items():
            out["windows"].setdefault(w, {}).update(entries)
    os.makedirs(os.path.dirname(os.path.abspath(a.into)), exist_ok=True)
    with open(a.into, "w") as f:
        json.dump(out, f, indent=1)
    print(f"{a.into}: windows {sorted(out['windows'], key=int)}")


if __name__ == "__main__":
    main()
