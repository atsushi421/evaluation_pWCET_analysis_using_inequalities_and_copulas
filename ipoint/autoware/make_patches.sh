#!/bin/bash
# Save the instrumentation as git patches of the three Autoware repositories
# (core, universe, launcher) into patches/, restricted to the files this
# campaign touches (target packages and the two launch-side files), with the
# base commits in patches/base.json. Re-apply on a fresh checkout with
#   git -C <repo> apply patches/<repo>.patch
set -eo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WS=${1:-$HOME/autoware}
mkdir -p "$HERE/patches"
paths_of() {  # package directories of a repository listed in targets.json
  python3 - "$1" "$HERE/targets.json" <<'PY'
import json, os, re, sys
repo, tj = sys.argv[1], sys.argv[2]
pkgs = json.load(open(tj))["packages"]
for root, dirs, files in os.walk(repo):
    dirs[:] = [d for d in dirs if not d.startswith(".")]
    if "package.xml" in files:
        m = re.search(r"<name>\s*(\S+)\s*</name>", open(os.path.join(root, "package.xml")).read())
        if m and m.group(1) in pkgs:
            print(os.path.relpath(root, repo))
PY
}
echo "{" > "$HERE/patches/base.json"
first=1
for r in core/autoware_core universe/autoware_universe launcher/autoware_launch; do
  name=$(basename $r)
  repo="$WS/src/$r"
  paths=$(paths_of "$repo")
  if [ "$name" = autoware_launch ]; then
    paths="tier4_universe_launch/tier4_control_launch/launch/control.launch.xml autoware_launch/config/localization/ndt_scan_matcher/ndt_scan_matcher.param.yaml"
  fi
  git -C "$repo" diff -- $paths > "$HERE/patches/$name.patch"
  [ $first = 1 ] || echo "," >> "$HERE/patches/base.json"; first=0
  printf ' "%s": {"commit": "%s", "patch": "%s.patch", "paths": "%s", "lines": %s}' "$name" "$(git -C "$repo" rev-parse HEAD)" "$name" "$(echo $paths | tr '\n' ' ')" "$(wc -l < "$HERE/patches/$name.patch")" >> "$HERE/patches/base.json"
done
echo "" >> "$HERE/patches/base.json"; echo "}" >> "$HERE/patches/base.json"
ls -la "$HERE/patches"
