#!/bin/bash
# Run a command pinned to one core, optionally under SCHED_FIFO.
# Usage: scripts/run_pinned.bash CORE [--fifo PRIO] -- cmd args...
CORE=$1; shift
FIFO=""
if [ "$1" = "--fifo" ]; then FIFO=$2; shift 2; fi
[ "$1" = "--" ] && shift
if [ -n "$FIFO" ]; then
  exec sudo chrt -f "$FIFO" taskset -c "$CORE" "$@"
else
  exec taskset -c "$CORE" "$@"
fi
