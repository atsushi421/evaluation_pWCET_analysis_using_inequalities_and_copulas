#!/bin/bash
# Merge the outputs of results/jobs/noderows.txt (the copula of a node is fitted over the runs in which the node
# executes, J1 of the paper repo .review/2026-10-04-revision-fifth-check.md) into results/ and regenerate the
# tables and figures that use them. The results before the change are in results/backup_pre_noderows/.
#   results/jobs/noderows_post.sh
set -eo pipefail
export LC_ALL=C
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
T=results/tables
O=results/jobs/noderows
CBS="cb1 cb2 cb3 cb4 cb5 cb6 cb7"

w0_tables() {   # w0_tables <dir> <file> <header> <p...>, as in full_post.sh
  local dir=$1 out=$2 head=$3; shift 3
  { echo "$head"; echo; echo '```'; for p in "$@"; do $PY tools/estimates_table.py --dir "$dir" --p "$p"; done; echo '```'; } > "$out"
}

for v in warm1 all; do
  for cb in cb1 cb4 cb6; do
    $PY tools/merge_estimates.py --into results/estimates_autoware_$v/$cb.json $O/${v}_${cb}_*/$cb.json > /dev/null
  done
done
for v in warm1 all; do
  if [ $v = warm1 ]; then h="steady state: the first nominal invocation of every replay dropped"; else h="all nominal invocations"; fi
  w0_tables results/estimates_autoware_$v $T/autoware_w0_$v.md "Autoware, window 0 (n = 1e4 nominal invocations), $h; RESTK n_sims 1000." 1e-4 1e-5
done
$PY tools/multiwindow_table.py --w0 results/estimates_autoware_warm1 --mw results/estimates_autoware_warm1 \
  --benches ${CBS// /,} --out $T/autoware_multiwindow.md > /dev/null

for cb in cb1 cb4; do
  for f in gaussian student clayton gumbel frank joe bb1 tawn; do
    cp $O/e25_${cb}_$f/$cb.json results/jobs/full_e25/${cb}_$f/$cb.json
  done
done
results/jobs/full_post.sh e25

$PY tools/paper_tables.py > /dev/null
$PY tools/fig_tightness.py > /dev/null
echo "merged; after noderows_cost.sh, copy $O/cost_scope/cb{1,4,6}.json to results/cost_scope/ and run"
echo "  $PY tools/scope_cost.py --table > $T/cost_scope.md"
