#!/bin/bash
# Launch the commands of QUEUE in order, each as soon as the running venv Python processes (estimation jobs and the
# workers of earlier commands) plus its weight fit into MAXPROC. Lines: "<weight> <shell command>"; '#' comments.
# Commands run from the repository root; their output goes to <log dir>/<line number>.log.
#   tools/run_queue.sh QUEUE MAXPROC [LOGDIR]
cd "$(dirname "$0")/.."
q=$1 max=$2 logs=${3:-results/jobs/queue_logs}
mkdir -p "$logs"
i=0
while read -r w cmd; do
  i=$((i + 1))
  [ -z "$w" ] || [[ $w == \#* ]] && continue
  while :; do
    n=$(pgrep -fc '(^|/)\.venv/bin/python ')
    [ $((n + w)) -le "$max" ] && break
    sleep 60
  done
  echo "$(date +%H:%M:%S) line $i start ($n running): $cmd"
  nohup bash -c "$cmd" > "$logs/$i.log" 2>&1 &
  sleep 180      # the command spawns its workers before the next count
done < "$q"
wait
echo "$(date +%H:%M:%S) queue done"
