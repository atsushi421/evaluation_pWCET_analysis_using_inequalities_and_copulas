#!/bin/bash
# Start (or resume) the production replay campaign in the background.
#   run_production.sh [--out traces/autoware] [--min-replays 470] [--min-samples 1e5] [extra runner args...]
# Checks first that the clock is fixed (boost off) and that no Autoware process is running.
set -eo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=traces/autoware; MINR=470; MINS=1e5; EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT=$2; shift 2;;
    --min-replays) MINR=$2; shift 2;;
    --min-samples) MINS=$2; shift 2;;
    *) EXTRA+=("$1"); shift;;
  esac
done
boost=$(cat /sys/devices/system/cpu/cpufreq/boost 2>/dev/null || echo "?")
gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo "?")
khz=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo "?")
echo "cpu: boost=$boost governor=$gov cur=${khz} kHz"
if [ "$boost" != "0" ]; then
  echo "WARNING: turbo boost is on; run 'sudo $HERE/../scripts/fix_frequencies.bash' first for the production campaign" >&2
  [ "${IPOINT_ALLOW_BOOST:-0}" = 1 ] || exit 1
fi
iso=$(cat /sys/devices/system/cpu/isolated 2>/dev/null)
echo "isolated cpus: '${iso:-none}' (sudo $HERE/../scripts/isolate_cores.bash [--grub] moves IRQs / adds isolcpus)"
python3 - <<'PY'
import glob
def cores(s):
    out=set()
    for p in s.split(','):
        if not p: continue
        if '-' in p:
            a,b=p.split('-'); out|=set(range(int(a),int(b)+1))
        else: out.add(int(p))
    return out
target=cores("6-9,12-15"); n=t=0
for f in glob.glob("/proc/irq/*/smp_affinity_list"):
    try: lst=cores(open(f).read().strip())
    except Exception: continue
    t+=1; n+= bool(lst & target)
print(f"IRQs allowed on the target cores: {n}/{t}")
PY
echo "the runner moves this user's other processes (desktop) to the rest cores at every replay (--no-confine disables it)"
# root processes cannot be moved; on this machine the MobiControl MDM agent runs `journalctl --verify`
# almost continuously at 100 % CPU on any core. Without isolcpus that activity lands on the target
# cores and the runner rejects the affected replays (foreign fraction > 2 %).
busy=$(ps -eo user,pcpu,comm --no-headers | awk '$1!="'"$USER"'" && $2>50 {printf "%s(%s%%) ", $3, $2}')
if [ -z "$iso" ] && [ -n "$busy" ]; then
  echo "WARNING: no isolated cpus and busy root processes: $busy" >&2
  echo "         run 'sudo $HERE/../scripts/isolate_cores.bash --grub' and reboot, or stop the job; set IPOINT_ALLOW_FOREIGN=1 to start anyway" >&2
  [ "${IPOINT_ALLOW_FOREIGN:-0}" = 1 ] || exit 1
fi
if pgrep -f "component_container|autoware_.*_node|ros2 launch" > /dev/null; then
  echo "Autoware processes are running; stop them first" >&2; exit 1
fi
set +u
source /opt/ros/humble/setup.bash
source "$HOME/autoware/install/setup.bash"
cd "$HERE"
mkdir -p "$OUT"
echo "starting the campaign into $OUT (log: $OUT/runner.out); follow with: python3 tools/campaign_status.py --campaign $OUT"
nohup python3 tools/run_replay_campaign.py --out "$OUT" --min-replays "$MINR" --min-samples "$MINS" "${EXTRA[@]}" > "$OUT/runner.out" 2>&1 &
echo "runner pid $!"
