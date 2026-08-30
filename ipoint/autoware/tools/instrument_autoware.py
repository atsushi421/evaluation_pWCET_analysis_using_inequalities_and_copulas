#!/usr/bin/env python3
"""Apply the IPoint instrumentation of targets.json to an Autoware workspace.

    instrument_autoware.py [--ws ~/autoware] [--targets targets.json] [--only PKG]...
                           [--dry-run] [--print-tree] [--force]

For every source file listed in targets.json the instrumenter is run in place
(--lang c++ --all, include paths from build/<pkg>/compile_commands.json, the
callback as --job, the listed callees as --only-function, static loop bounds
from the 'bounds' entry); the schema and the scope tree are stored under
schemas/<pkg>/. package.xml gets a <depend>ipoint_runtime</depend> and
CMakeLists.txt links every listed target against ipoint_runtime. Both edits are
idempotent (a marker comment / the include line is checked first). The id
ranges of the files loaded into one process must not overlap; the script
verifies it from the 'processes' table.

Undo with `git checkout -- <files>` in the repositories (or apply.sh --revert).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AW = os.path.dirname(HERE)
TOOLS = os.path.join(os.path.dirname(AW), "tools")
MARK = "# --- ipoint instrumentation (CHB-COP evaluation) ---"


def find_package_dir(ws: str, pkg: str) -> str:
    for root, dirs, files in os.walk(os.path.join(ws, "src")):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("build", "install", "log")]
        if "package.xml" in files:
            with open(os.path.join(root, "package.xml")) as f:
                if re.search(rf"<name>\s*{re.escape(pkg)}\s*</name>", f.read()):
                    return root
    raise SystemExit(f"package {pkg} not found under {ws}/src")


def patch_package_xml(path: str, dry: bool) -> bool:
    with open(path) as f:
        s = f.read()
    if "<depend>ipoint_runtime</depend>" in s:
        return False
    s2 = re.sub(r"(\n\s*<export>)", r"\n  <depend>ipoint_runtime</depend>\1", s, count=1)
    if s2 == s:
        raise SystemExit(f"{path}: no <export> element to anchor the dependency")
    if not dry:
        with open(path, "w") as f:
            f.write(s2)
    return True


def patch_cmake(path: str, targets, dry: bool) -> bool:
    with open(path) as f:
        s = f.read()
    if MARK in s:
        return False
    block = [MARK, "find_package(ipoint_runtime REQUIRED)"]
    for t in targets:
        block.append(f"target_link_libraries({t} ipoint_runtime::ipoint_runtime)")
    block.append("# --- end ipoint ---")
    text = "\n".join(block) + "\n\n"
    # insert before the final ament package call
    m = None
    for m_ in re.finditer(r"^(autoware_ament_auto_package|ament_auto_package|ament_package)\s*\(", s, flags=re.M):
        m = m_
    if m is None:
        raise SystemExit(f"{path}: no ament_package call found")
    s2 = s[:m.start()] + text + s[m.start():]
    if not dry:
        with open(path, "w") as f:
            f.write(s2)
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ws", default=os.path.expanduser("~/autoware"))
    ap.add_argument("--targets", default=os.path.join(AW, "targets.json"))
    ap.add_argument("--only", action="append", default=[], help="restrict to these packages")
    ap.add_argument("--dry-run", action="store_true", help="run the instrumenter with --dry-run and do not edit files")
    ap.add_argument("--print-tree", action="store_true")
    ap.add_argument("--force", action="store_true", help="instrument files that already include ipoint.h (restore them first!)")
    ap.add_argument("--ranges-checked", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    with open(a.targets) as f:
        spec = json.load(f)
    ws = os.path.expanduser(a.ws)
    if not a.dry_run and not a.ranges_checked:
        # first pass without edits: the id ranges of a process must not overlap
        # before any source is modified
        rc = main(list(argv or sys.argv[1:]) + ["--dry-run", "--ranges-checked"])
        if rc != 0:
            return rc
    ranges = {}  # pkg/file -> (lo, hi)
    for pkg, pspec in spec["packages"].items():
        if a.only and pkg not in a.only:
            continue
        pdir = find_package_dir(ws, pkg)
        cc = os.path.join(ws, "build", pkg, "compile_commands.json")
        if not os.path.exists(cc):
            raise SystemExit(f"{cc} missing: build {pkg} with -DCMAKE_EXPORT_COMPILE_COMMANDS=ON first")
        sdir = os.path.join(AW, "schemas", pkg)
        os.makedirs(sdir, exist_ok=True)
        for fspec in pspec["files"]:
            src = os.path.join(pdir, fspec["path"])
            base = os.path.basename(src)
            with open(src) as f:
                head = f.read(4096)
            if '#include "ipoint.h"' in head and not a.force:
                if not a.dry_run:
                    print(f"skip {pkg}/{fspec['path']} (already instrumented)", file=sys.stderr)
                continue
            schema = os.path.join(sdir, base + ".schema.json")
            policy_flag = "--functions-only" if fspec.get("policy") == "functions-only" else "--all"
            cmd = [sys.executable, os.path.join(TOOLS, "ipoint_instrument.py"), src, "--lang", "c++",
                   "--compile-commands", cc, policy_flag, "--id-base", str(fspec["id_base"]), "--schema", schema,
                   "--print-tree"]
            for fn in fspec.get("functions", []):
                cmd += ["--only-function", fn]
            for uid in fspec.get("exclude_units", []):
                cmd += ["--exclude-unit", uid]
            if fspec.get("job"):
                cmd += ["--job", fspec["job"]]
            if fspec.get("bounds"):
                bpath = os.path.join(sdir, base + ".bounds.json")
                with open(bpath, "w") as f:
                    json.dump(fspec["bounds"], f, indent=1)
                cmd += ["--bounds", bpath]
            cmd += ["--dry-run"] if a.dry_run else ["--in-place"]
            print("+", " ".join(cmd[1:]), file=sys.stderr)
            r = subprocess.run(cmd, capture_output=True, text=True)
            tree_path = os.path.join(sdir, base + (".dryrun.tree.txt" if a.dry_run else ".tree.txt"))
            with open(tree_path, "w") as f:
                f.write(r.stdout)
                f.write("\n# stderr\n")
                f.write("\n".join(l for l in r.stderr.splitlines() if not l.startswith("clang:")))
            if a.print_tree:
                print(r.stdout)
            for line in r.stderr.splitlines():
                if line.startswith("warning:") or line.startswith("error:") or line.startswith("wrote"):
                    print(f"  {line}", file=sys.stderr)
            if r.returncode != 0:
                print(r.stderr[-3000:], file=sys.stderr)
                raise SystemExit(f"instrumenting {src} failed")
            m = re.search(r"ids (\d+)\.\.(\d+)", r.stderr)
            if m:
                ranges[f"{pkg}/{fspec['path']}"] = (int(m.group(1)), int(m.group(2)), pkg)
        if not a.dry_run:
            if patch_package_xml(os.path.join(pdir, "package.xml"), a.dry_run):
                print(f"  patched {pkg}/package.xml", file=sys.stderr)
            if patch_cmake(os.path.join(pdir, "CMakeLists.txt"), pspec["cmake_targets"], a.dry_run):
                print(f"  patched {pkg}/CMakeLists.txt", file=sys.stderr)
    # id ranges must be disjoint within a process
    for proc, pd in spec["processes"].items():
        rs = sorted((lo, hi, k) for k, (lo, hi, pkg) in ranges.items() if pkg in pd["packages"])
        for (lo1, hi1, k1), (lo2, hi2, k2) in zip(rs, rs[1:]):
            if lo2 <= hi1:
                raise SystemExit(f"{proc}: id ranges of {k1} ({lo1}-{hi1}) and {k2} ({lo2}-{hi2}) overlap")
    with open(os.path.join(AW, "schemas", "id_ranges.json"), "w") as f:
        json.dump({k: {"lo": v[0], "hi": v[1], "package": v[2]} for k, v in ranges.items()}, f, indent=1)
    for k, (lo, hi, pkg) in sorted(ranges.items(), key=lambda x: x[1]):
        print(f"{k}: ids {lo}..{hi}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
