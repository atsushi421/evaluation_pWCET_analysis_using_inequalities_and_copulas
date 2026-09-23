#!/bin/bash
# E2-14 measurements (rare-path stress test, 02_experiments_plan.md section 7/8.2) under the
# campaign conditions: boost off, 2.1 GHz, isolated core 6, this user's estimation jobs paused
# (SIGSTOP) while measuring and resumed on exit. Needs the OFF kernel objects of the campaign
# builds (bench/build/<bench>/off/kernel.o). Output: results/e214/.
#   ipoint/e214/run.sh
set -eo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
OUT=$REPO/results/e214
CORE=6
[ "$(cat /sys/devices/system/cpu/cpufreq/boost)" = 0 ] || { echo "boost is on; run ipoint/scripts/fix_frequencies.bash first" >&2; exit 1; }
grep -qw $CORE <<<"$(tr ',-' '  ' < /sys/devices/system/cpu/isolated)" || { echo "core $CORE is not isolated" >&2; exit 1; }
mkdir -p "$OUT"
make -s -C "$HERE"
PIDS=$(pgrep -f "chb_cop_from_schema.py|certification_curve.py|tools/tables.py|synthetic_study.py" || true)
resume() { [ -n "$PIDS" ] && kill -CONT $PIDS 2>/dev/null; echo "resumed $(echo $PIDS | wc -w) processes"; }
trap resume EXIT
[ -n "$PIDS" ] && kill -STOP $PIDS
echo "paused $(echo $PIDS | wc -w) processes"
sleep 5
# 1. bsort100: candidate adversarial inputs against uniform random input (OFF kernel object)
taskset -c $CORE "$HERE/probe_bsort100" $CORE | tee "$OUT/bsort100_inputs.txt"
# 2. qsort-exam: McIlroy's adversary against uniform random input (OFF kernel object)
taskset -c $CORE "$HERE/killer_qsort" $CORE | tee "$OUT/qsort_killer_off.txt"
# 3. qsort-exam at the fine granularity (100 ns floor, no probe budget): 2e4 uniform runs (pilot
#    pruning, TIMING, OFF, COVERAGE), then 2e3 killer runs on the same build (--stages build,run,parse
#    reuse the pilot's exclusions in bench/build/qsort-exam)
cd "$REPO/ipoint"
C="--min-unit-ns 100 --max-probe-share 0 --probe-ns 31.5 --core $CORE"
/usr/bin/python3 tools/run_campaign.py --bench qsort-exam --out "$OUT/rand" --runs 2e4 --full 2e4 \
  --overhead-runs 1e4 --coverage-runs 2e4 --param 0 $C > "$OUT/rand.log" 2>&1
/usr/bin/python3 tools/run_campaign.py --bench qsort-exam --out "$OUT/killer" --stages build,run,parse --runs 2e3 --full 2e3 \
  --overhead-runs 1e3 --coverage-runs 2e3 --param 1 $C > "$OUT/killer.log" 2>&1
cat /sys/devices/system/cpu/cpufreq/boost > "$OUT/boost_after.txt"
echo "measurement done"
