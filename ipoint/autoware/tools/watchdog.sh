#!/bin/bash
# Resume the production campaign when the runner stopped before the campaign completed.
#   nohup tools/watchdog.sh traces/autoware [max_restarts=3] [interval_s=600] &
# Every interval: if no runner is running and the last line of <out>/campaign.log is not "done: ...",
# stop leftover Autoware processes, resume with run_production.sh (which skips the existing replays)
# and count one restart; give up after max_restarts. Log: <out>/watchdog.log.
set -o pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-traces/autoware}; MAX=${2:-3}; INTERVAL=${3:-600}
cd "$HERE" || exit 1
LOG=$OUT/watchdog.log
restarts=0
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
log "watchdog started (max_restarts=$MAX, interval=${INTERVAL}s)"
while true; do
  sleep "$INTERVAL"
  if pgrep -f "run_replay_campaign.py --out $OUT" > /dev/null; then
    continue
  fi
  last=$(tail -1 "$OUT/campaign.log" 2>/dev/null)
  if [[ "$last" == *" done: "* ]]; then
    log "campaign complete: $last"; exit 0
  fi
  if [ "$restarts" -ge "$MAX" ]; then
    log "runner stopped again ($last); $MAX restarts used, giving up"; exit 1
  fi
  left=$(pgrep -f "component_container|autoware_.*_node|ros2 launch|ros2 bag")
  if [ -n "$left" ]; then
    log "stopping leftover Autoware processes: $(echo $left | wc -w)"
    kill -TERM $left 2>/dev/null; sleep 20; kill -KILL $left 2>/dev/null; sleep 2
  fi
  restarts=$((restarts + 1))
  log "runner not running (last: $last); restart $restarts/$MAX"
  cp "$OUT/runner.out" "$OUT/runner.out.$(date +%Y%m%d-%H%M%S)" 2>/dev/null
  ./run_production.sh --out "$OUT" --min-replays 470 --min-samples 1e5 >> "$LOG" 2>&1
done
