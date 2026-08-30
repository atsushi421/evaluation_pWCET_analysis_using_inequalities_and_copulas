#!/bin/bash
# Install the IPoint instrumentation into an Autoware workspace and build it.
#   apply.sh [--ws ~/autoware] [--mode TIMING|OFF] [--no-build]
# Steps: copy the ipoint_runtime package into <ws>/src, instrument the target
# sources in place (targets.json), patch the launch files, build the runtime
# and the instrumented packages with the flags of the original build.
set -eo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WS=$HOME/autoware
MODE=TIMING
BUILD=1
while [ $# -gt 0 ]; do
  case "$1" in
    --ws) WS=$2; shift 2;;
    --mode) MODE=$2; shift 2;;
    --no-build) BUILD=0; shift;;
    *) echo "unknown option $1"; exit 1;;
  esac
done
PKGS="autoware_ekf_localizer autoware_twist2accel autoware_stop_filter autoware_trajectory_follower_node autoware_mpc_lateral_controller autoware_pid_longitudinal_controller autoware_ground_segmentation autoware_lane_departure_checker autoware_ndt_scan_matcher"

echo "== runtime package -> $WS/src/ipoint_runtime"
rm -rf "$WS/src/ipoint_runtime"
cp -rL "$HERE/ipoint_runtime" "$WS/src/ipoint_runtime"
echo "== instrumenting sources"
python3 "$HERE/tools/instrument_autoware.py" --ws "$WS"
echo "== launch patches"
python3 "$HERE/tools/patch_launch.py" --ws "$WS"
if [ $BUILD = 1 ]; then
  echo "== building (IPOINT_MODE=$MODE)"
  set +u
  source /opt/ros/humble/setup.bash
  source "$WS/install/setup.bash"
  cd "$WS"
  colcon build --symlink-install --packages-select ipoint_runtime $PKGS \
    --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    "-DCMAKE_CXX_FLAGS=-Wno-deprecated-declarations -Wno-attributes -isystem/usr/include/pcl-1.12" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DIPOINT_MODE=$MODE
  echo "== probes per library (rdtscp count)"
  for p in $PKGS; do
    for so in "$WS"/install/$p/lib/*.so; do
      [ -f "$so" ] && printf "%-70s %s\n" "$(basename "$so")" "$(objdump -d "$so" | grep -c rdtscp)"
    done
  done
fi
