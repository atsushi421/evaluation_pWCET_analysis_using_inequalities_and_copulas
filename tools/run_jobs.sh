#!/bin/bash
# Run estimation jobs in parallel; each line of JOBFILE is
#   <traces> <bench> <windows> <methods> <window_size> <out_dir> [<n_mc> [<window_stride>]]
# and becomes one chb_cop_from_schema.py process (log in <out_dir>/log.txt).
# Jobs whose <out_dir>/<bench>.json exists are skipped, so a rerun resumes. A running job holds a lock on
# <out_dir>/.lock, so several runners (e.g. one per isolated core) can share one job file.
#   tools/run_jobs.sh JOBFILE [PARALLEL]
set -e
cd "$(dirname "$0")/.."
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
run_one() {
  read -r traces bench windows methods wsize out nmc stride <<<"$1"
  [ -f "$out/$bench.json" ] && exit 0
  mkdir -p "$out"
  exec 9>"$out/.lock"
  flock -n 9 || exit 0
  [ -f "$out/$bench.json" ] && exit 0
  .venv/bin/python tools/chb_cop_from_schema.py --traces "$traces" --bench "$bench" --windows "$windows" \
    --methods "$methods" --window-size "$wsize" --n-mc "${nmc:-1e8}" --window-stride "${stride:-0}" --out "$out" \
    >"$out/log.txt" 2>&1 \
    || echo "FAILED: $1" >&2
}
export -f run_one
grep -v '^#' "$1" | grep . | xargs -d '\n' -P "${2:-10}" -I{} bash -c 'run_one "$@"' _ {}
