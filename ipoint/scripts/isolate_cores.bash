#!/bin/bash
# Keep the cores dedicated to the instrumented Autoware callbacks free of
# interrupts and, after a reboot, of every task that is not pinned there.
#
#   sudo scripts/isolate_cores.bash [--target 6-9,12-15] [--rest 0-5,10-11] [--grub] [--isolcpus 6-9]
#
# --target: cores kept free of IRQs (all measurement cores).
# --isolcpus (with --grub): cores put on the isolcpus/nohz_full/rcu_nocbs kernel
#   command line. Only the SINGLE-CORE measurement cores belong here: the
#   scheduler does not balance load between isolated CPUs, so a multi-threaded
#   process pinned to a *group* of isolated cores piles up on one of them.
#   Multi-core groups (the pointcloud container on 12-15) stay non-isolated and
#   rely on the runner's confinement of every other process.
#
# Without --grub (no reboot needed):
#   * stops irqbalance and moves the affinity of every movable IRQ to the rest cores
#   * sets the default affinity of new IRQs to the rest cores
# With --grub: appends isolcpus/nohz_full/rcu_nocbs for the target cores to
# GRUB_CMDLINE_LINUX_DEFAULT in /etc/default/grub and runs update-grub; the
# isolation takes effect after a reboot (check /sys/devices/system/cpu/isolated).
# The runner records both states in campaign.json.
set -eo pipefail
TARGET=6-9,12-15
REST=0-5,10-11
ISOL=6-9
GRUB=0
while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET=$2; shift 2;;
    --rest) REST=$2; shift 2;;
    --grub) GRUB=1; shift;;
    --isolcpus) ISOL=$2; shift 2;;
    *) echo "unknown option $1" >&2; exit 1;;
  esac
done
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

echo "== IRQ affinity -> cores $REST"
systemctl stop irqbalance 2>/dev/null && echo "irqbalance stopped (re-enable with: systemctl start irqbalance)" || true
moved=0; fixed=0
for f in /proc/irq/*/smp_affinity_list; do
  irq=$(basename "$(dirname "$f")")
  [ "$irq" = default ] && continue
  if echo "$REST" > "$f" 2>/dev/null; then moved=$((moved+1)); else fixed=$((fixed+1)); fi
done
# default affinity of new IRQs is a hex mask (no *_list variant)
mask=$(python3 -c "
m=0
for p in '$REST'.split(','):
    if '-' in p:
        a,b=p.split('-'); m|=sum(1<<i for i in range(int(a),int(b)+1))
    elif p: m|=1<<int(p)
print(format(m,'x'))")
echo "$mask" > /proc/irq/default_smp_affinity 2>/dev/null && echo "default IRQ affinity mask -> 0x$mask" || true
echo "moved $moved IRQs, $fixed could not be moved (per-CPU or unmovable interrupts)"
echo "IRQs still allowed on target cores:"
for f in /proc/irq/*/smp_affinity_list; do
  irq=$(basename "$(dirname "$f")")
  lst=$(cat "$f" 2>/dev/null) || continue
  python3 - "$lst" "$TARGET" "$irq" <<'PY' || true
import sys
def cores(s):
    out=set()
    for p in s.split(','):
        if not p: continue
        if '-' in p:
            a,b=p.split('-'); out|=set(range(int(a),int(b)+1))
        else: out.add(int(p))
    return out
if cores(sys.argv[1]) & cores(sys.argv[2]):
    print("  irq", sys.argv[3], "->", sys.argv[1])
PY
done | head -20

if [ $GRUB = 1 ]; then
  line="isolcpus=$ISOL nohz_full=$ISOL rcu_nocbs=$ISOL"
  cp /etc/default/grub /etc/default/grub.bak.ipoint
  # drop any previous isolcpus/nohz_full/rcu_nocbs from the active line, then append the new ones
  sed -i -E '/^GRUB_CMDLINE_LINUX_DEFAULT=/ s/ ?(isolcpus|nohz_full|rcu_nocbs)=[^ "]*//g' /etc/default/grub
  sed -i "s/^GRUB_CMDLINE_LINUX_DEFAULT=\"\(.*\)\"/GRUB_CMDLINE_LINUX_DEFAULT=\"\1 $line\"/" /etc/default/grub
  sed -i -E '/^GRUB_CMDLINE_LINUX_DEFAULT=/ s/"  +/" /; s/  +/ /g' /etc/default/grub
  grep -E '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub
  update-grub
  echo "reboot to activate; verify with: cat /sys/devices/system/cpu/isolated  (expected $ISOL)"
  echo "revert: restore /etc/default/grub.bak.ipoint and run update-grub"
else
  echo "== isolcpus (needs a reboot): re-run with --grub to set"
  echo "   isolcpus=$ISOL nohz_full=$ISOL rcu_nocbs=$ISOL  in GRUB_CMDLINE_LINUX_DEFAULT"
fi
echo "current isolated cpus: '$(cat /sys/devices/system/cpu/isolated 2>/dev/null)'"
