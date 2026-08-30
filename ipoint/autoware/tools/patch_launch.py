#!/usr/bin/env python3
"""Launch-side changes of the Autoware campaign (idempotent, reversible with --revert):

  1. tier4_control_launch/launch/control.launch.xml: the trajectory follower
     (cb4) is loaded into its own component container
     /control/trajectory_follower_container instead of /control/control_container,
     so that the process pinned to the cb4 core hosts no other node.
  2. autoware_launch/config/localization/ndt_scan_matcher/ndt_scan_matcher.param.yaml:
     num_threads 4 -> 2, matching the two cores dedicated to the NDT process.

Both files are installed as symlinks (colcon --symlink-install), so no rebuild
is needed after editing the sources.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

MARK = "<!-- ipoint: dedicated container for the trajectory follower (CHB-COP evaluation) -->"


def find(ws: str, rel: str) -> str:
    hits = glob.glob(os.path.join(ws, "src", "**", rel), recursive=True)
    if len(hits) != 1:
        raise SystemExit(f"{rel}: expected exactly one match under {ws}/src, got {hits}")
    return hits[0]


def patch_control_launch(path: str, revert: bool) -> bool:
    with open(path) as f:
        s = f.read()
    old_open = '<load_composable_node target="/control/control_container">\n          <composable_node pkg="autoware_trajectory_follower_node"'
    new_open = (MARK + '\n        <node_container pkg="$(var container_package)" exec="$(var container_executable)" '
                'name="trajectory_follower_container" namespace="">\n          <composable_node pkg="autoware_trajectory_follower_node"')
    if revert:
        if MARK not in s:
            return False
        s2 = s.replace(new_open, old_open, 1)
        # the closing tag of that block
        i = s2.index('<composable_node pkg="autoware_trajectory_follower_node"')
        j = s2.index("</node_container>", i)
        s2 = s2[:j] + "</load_composable_node>" + s2[j + len("</node_container>"):]
    else:
        if MARK in s:
            return False
        if s.count(old_open) != 1:
            raise SystemExit(f"{path}: trajectory follower load_composable_node not found once")
        s2 = s.replace(old_open, new_open, 1)
        i = s2.index('<composable_node pkg="autoware_trajectory_follower_node"')
        j = s2.index("</load_composable_node>", i)
        s2 = s2[:j] + "</node_container>" + s2[j + len("</load_composable_node>"):]
    with open(path, "w") as f:
        f.write(s2)
    return True


def patch_ndt_threads(path: str, revert: bool, threads: int) -> bool:
    with open(path) as f:
        s = f.read()
    m = re.search(r"^(\s*num_threads:\s*)(\d+)(.*)$", s, flags=re.M)
    if not m:
        raise SystemExit(f"{path}: num_threads not found")
    cur = int(m.group(2))
    marker = "  # ipoint: was 4"
    if revert:
        if marker not in m.group(3):
            return False
        s2 = s[:m.start()] + f"{m.group(1)}4" + s[m.end():]
    else:
        if marker in m.group(3):
            return False
        s2 = s[:m.start()] + f"{m.group(1)}{threads}{m.group(3)}{marker}" + s[m.end():]
    with open(path, "w") as f:
        f.write(s2)
    return cur != threads or revert


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ws", default=os.path.expanduser("~/autoware"))
    ap.add_argument("--ndt-threads", type=int, default=4, help="4 = upstream value (no patch)")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args(argv)
    ws = os.path.expanduser(a.ws)
    c = find(ws, "tier4_control_launch/launch/control.launch.xml")
    n = find(ws, "autoware_launch/config/localization/ndt_scan_matcher/ndt_scan_matcher.param.yaml")
    print(f"{'reverted' if a.revert else 'patched'} control.launch.xml: {patch_control_launch(c, a.revert)}")
    # threads == 4 is the upstream value: make sure the parameter is not patched
    ndt_revert = a.revert or a.ndt_threads == 4
    print(f"{'reverted' if ndt_revert else 'patched'} ndt num_threads: {patch_ndt_threads(n, ndt_revert, a.ndt_threads)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
