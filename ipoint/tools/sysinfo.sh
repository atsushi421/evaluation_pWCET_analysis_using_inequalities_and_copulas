#!/bin/bash
# Print the measurement environment as JSON (consumed by run_campaign.py).
CORE=${1:-0}
CPUDIR=/sys/devices/system/cpu/cpu$CORE/cpufreq
j() { python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"; }
cat <<JSON
{
  "hostname": $(j "$(hostname)"),
  "kernel": $(j "$(uname -r)"),
  "cmdline": $(j "$(cat /proc/cmdline)"),
  "os": $(j "$(. /etc/os-release && echo "$PRETTY_NAME")"),
  "cpu_model": $(j "$(grep -m1 'model name' /proc/cpuinfo | sed 's/.*: //')"),
  "n_cpus": $(nproc),
  "cpu_flags_tsc": $(j "$(grep -m1 -o -w 'constant_tsc\|nonstop_tsc\|rdtscp\|tsc_reliable' /proc/cpuinfo | sort -u | tr '\n' ' ')"),
  "clocksource": $(j "$(cat /sys/devices/system/clocksource/clocksource0/current_clocksource 2>/dev/null)"),
  "core": $CORE,
  "scaling_governor": $(j "$(cat $CPUDIR/scaling_governor 2>/dev/null)"),
  "scaling_cur_freq_khz": $(cat $CPUDIR/scaling_cur_freq 2>/dev/null || echo null),
  "scaling_setspeed_khz": $(j "$(cat $CPUDIR/scaling_setspeed 2>/dev/null)"),
  "boost": $(cat /sys/devices/system/cpu/cpufreq/boost 2>/dev/null || echo null),
  "isolated_cpus": $(j "$(cat /sys/devices/system/cpu/isolated 2>/dev/null)"),
  "gcc": $(j "$(gcc --version | head -1)"),
  "smt_active": $(cat /sys/devices/system/cpu/smt/active 2>/dev/null || echo null),
  "git_sha": $(j "$(git -C "$(dirname "$0")" rev-parse HEAD 2>/dev/null)"),
  "git_dirty": $([ -n "$(git -C "$(dirname "$0")" status --porcelain 2>/dev/null)" ] && echo true || echo false),
  "date": $(j "$(date -Is)")
}
JSON
