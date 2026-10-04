#!/bin/bash
# Analysis time of CHB-COP (window 0) for the callbacks whose node copulas change with noderows.txt, one process
# per isolated core while the recompute runs on the other cores, as for loopself_cost.sh.
# Output: results/jobs/noderows/cost_scope/.
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
O=results/jobs/noderows/cost_scope
mkdir -p $O
run() {   # run <core> <callback>
  taskset -c "$1" .venv/bin/python tools/scope_cost.py --traces ipoint/autoware/traces/autoware/bench_warm1 \
    --bench "$2" --n-mc 1e7 --out $O > $O/$2.log 2>&1
  echo "$2 exit $?" >> $O/done.txt
}
run 6 cb4 &
run 7 cb1 &
run 8 cb6 &
wait
