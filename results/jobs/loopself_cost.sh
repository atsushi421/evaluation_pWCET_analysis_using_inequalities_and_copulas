#!/bin/bash
# Analysis time of CHB-COP (window 0) for the callbacks with a composed loop, after the loop rule includes the
# self time of the loop (J1). One process per isolated core, started when the recompute job on that core ends,
# as in the stored measurement (four processes in parallel). Output: results/jobs/loopself/cost_scope/.
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
O=results/jobs/loopself/cost_scope
mkdir -p $O
run() {   # run <pid to wait for> <core> <callback>
  while kill -0 "$1" 2>/dev/null; do sleep 30; done
  taskset -c "$2" .venv/bin/python tools/scope_cost.py --traces ipoint/autoware/traces/autoware/bench_warm1 \
    --bench "$3" --n-mc 1e7 --out $O > $O/$3.log 2>&1
  echo "$3 exit $?" >> $O/done.txt
}
run 1877902 6 cb4 &
run 1877923 7 cb1 &
run 1877919 8 cb6 &
run 1877912 9 cb7 &
wait
