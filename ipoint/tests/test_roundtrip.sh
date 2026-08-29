#!/bin/bash
# End-to-end smoke test: instrument bsort100 with the default pilot policy,
# build all three modes, run a short campaign into a temporary directory and
# run the consistency checks on the result.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
OUT=$(mktemp -d)
trap 'rm -rf "$OUT"' EXIT
python3 "$ROOT/tools/run_campaign.py" --bench bsort100,sqrt --out "$OUT" \
  --runs 5000 --full 2000 --overhead-runs 2000 --coverage-runs 5000 --pilot-runs 300 --warmup 100 \
  --core "${IPOINT_TEST_CORE:-3}" 2> "$OUT/log.txt" || { cat "$OUT/log.txt"; exit 1; }
for b in bsort100 sqrt; do
  python3 "$ROOT/tools/ipoint_check.py" --schema "$OUT/$b/schema_timing.json" --trace-dir "$OUT/$b/timing" --parsed "$OUT/$b/parsed"
  python3 - "$OUT/$b" <<'PY'
import json, sys, numpy as np
d = sys.argv[1]
st = json.load(open(f"{d}/parsed/stats.json"))
ov = json.load(open(f"{d}/overhead.json"))
cov = json.load(open(f"{d}/coverage.json"))
assert st["runs_parsed"] == 2000, st["runs_parsed"]
assert ov["off"]["n"] == 2000 and ov["timing"]["n"] == 5000
assert cov["runs"] == 5000
e2e = np.load(f"{d}/parsed/e2e_all.npy")
assert len(e2e) == 5000 and (e2e > 0).all()
print(f"{d}: ok ({len(st['units'])} units, overhead ratio {ov['overhead_ratio_median']:.2f})")
PY
done
echo "roundtrip OK"
