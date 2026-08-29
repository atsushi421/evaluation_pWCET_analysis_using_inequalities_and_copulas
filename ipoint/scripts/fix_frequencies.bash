#!/bin/bash
# Pin every core to the nominal frequency and disable turbo boost (needs sudo).
# Usage: sudo scripts/fix_frequencies.bash [FREQ_KHZ]   (default: nominal = second entry
# of scaling_available_frequencies, which excludes the "turbo" pseudo-frequency)
set -e
CPU0=$(cut -d, -f1 /sys/devices/system/cpu/online | cut -d- -f1)
AVAIL=$(cat /sys/devices/system/cpu/cpu$CPU0/cpufreq/scaling_available_frequencies)
FREQ=${1:-$(echo "$AVAIL" | awk '{print ($1 % 1000 == 0) ? $1 : $2}')}
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo userspace > "$g"; done
for s in /sys/devices/system/cpu/cpu*/cpufreq/scaling_setspeed; do echo "$FREQ" > "$s"; done
[ -w /sys/devices/system/cpu/cpufreq/boost ] && echo 0 > /sys/devices/system/cpu/cpufreq/boost
echo "governor=userspace setspeed=$FREQ kHz boost=$(cat /sys/devices/system/cpu/cpufreq/boost 2>/dev/null)"
