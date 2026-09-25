#!/bin/bash
# E2-14 second kernel (select with McIlroy's adversary, 08_resubmission_breakthrough.md section 12.2)
# under the conditions of run.sh: boost off, 2.1 GHz, isolated core 6, estimation jobs paused.
# The coarse build in bench/build/select is moved to bench/build/select.coarse first, because the
# fine pilot overwrites it (the coarse traces keep their own copies of the schema and exclusions).
# Output: results/e214/select_*.
#   ipoint/e214/run_select.sh
set -eo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
OUT=$REPO/results/e214
CORE=6
[ "$(cat /sys/devices/system/cpu/cpufreq/boost)" = 0 ] || { echo "boost is on; run ipoint/scripts/fix_frequencies.bash first" >&2; exit 1; }
grep -qw $CORE <<<"$(tr ',-' '  ' < /sys/devices/system/cpu/isolated)" || { echo "core $CORE is not isolated" >&2; exit 1; }
B=$REPO/ipoint/bench/build
[ -d "$B/select.coarse" ] || cp -a "$B/select" "$B/select.coarse"
mkdir -p "$OUT"
make -s -C "$HERE" probe_select
PIDS=$(pgrep -f "chb_cop_from_schema.py|certification_curve.py|tools/tables.py|synthetic_study.py|resubmission_prototype" || true)
resume() { [ -n "$PIDS" ] && kill -CONT $PIDS 2>/dev/null; echo "resumed $(echo $PIDS | wc -w) processes"; }
trap resume EXIT
[ -n "$PIDS" ] && kill -STOP $PIDS
echo "paused $(echo $PIDS | wc -w) processes"
sleep 5
# 1. OFF kernel object of the coarse build: random, adversarial, and subnormal-scaled inputs
taskset -c $CORE "$HERE/probe_select" $CORE | tee "$OUT/select_killer_off.txt"
# 2. fine granularity (100 ns floor, no probe budget): 2e4 uniform runs, then 2e3 adversarial runs
#    on the same build
cd "$REPO/ipoint"
C="--min-unit-ns 100 --max-probe-share 0 --probe-ns 31.5 --core $CORE"
/usr/bin/python3 tools/run_campaign.py --bench select --out "$OUT/select_rand" --runs 2e4 --full 2e4 \
  --overhead-runs 1e4 --coverage-runs 2e4 --param 0 $C > "$OUT/select_rand.log" 2>&1
/usr/bin/python3 tools/run_campaign.py --bench select --out "$OUT/select_killer" --stages build,run,parse --runs 2e3 --full 2e3 \
  --overhead-runs 1e3 --coverage-runs 2e3 --param 1 $C > "$OUT/select_killer.log" 2>&1
cat /sys/devices/system/cpu/cpufreq/boost > "$OUT/select_boost_after.txt"
echo "measurement done"
