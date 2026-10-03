#!/bin/bash
# Merge the outputs of results/jobs/loopself.txt and loopself_small.sh, which recompute every result that composes
# a loop with the loop rule that includes the self time of the loop (J1 of the paper repo
# .review/2026-10-02-revision-fourth-check.md), into results/ and regenerate the tables and figures that use them.
# The results before the change are in results/backup_pre_loopself/. full_post.sh fine and aw rebuild their result
# sets from the job outputs of the full campaign, so this script merges the new entries into the stored sets instead.
#   results/jobs/loopself_post.sh
set -eo pipefail
export LC_ALL=C
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
T=results/tables
O=results/jobs/loopself
CBS="cb1 cb2 cb3 cb4 cb5 cb6 cb7"

w0_tables() {   # w0_tables <dir> <file> <header> <p...>, as in full_post.sh
  local dir=$1 out=$2 head=$3; shift 3
  { echo "$head"; echo; echo '```'; for p in "$@"; do $PY tools/estimates_table.py --dir "$dir" --p "$p"; done; echo '```'; } > "$out"
}

# Autoware: the decomposed entries of the callbacks with a composed loop, in both variants
for v in warm1 all; do
  for cb in cb1 cb4 cb6 cb7; do
    $PY tools/merge_estimates.py --into results/estimates_autoware_$v/$cb.json $O/${v}_${cb}_*/$cb.json > /dev/null
  done
done
for v in warm1 all; do
  if [ $v = warm1 ]; then h="steady state: the first nominal invocation of every replay dropped"; else h="all nominal invocations"; fi
  w0_tables results/estimates_autoware_$v $T/autoware_w0_$v.md "Autoware, window 0 (n = 1e4 nominal invocations), $h; RESTK n_sims 1000." 1e-4 1e-5
done
$PY tools/multiwindow_table.py --w0 results/estimates_autoware_warm1 --mw results/estimates_autoware_warm1 \
  --benches ${CBS// /,} --out $T/autoware_multiwindow.md > /dev/null

# fine-grained bsort100: the decomposed entries of windows 0-9
$PY tools/merge_estimates.py --into results/estimates_fine/bsort100.json $O/fine/bsort100.json > /dev/null
M=E2E-CHB,E2E-MEMIK,E2E-EVT-PoT,EVT-COP,MEMIK-COP,CHB-IND,CHB-COMONO,CHB-COP,CHB-IND@max,CHB-COP@max
{ echo "Fine-granularity bsort100 (100 ns floor), second campaign (2e6 runs, all traced), window 0; @max = per-run slowest-iteration loop rule."
  echo; echo '```'; for p in 1e-4 1e-5 1e-6; do $PY tools/estimates_table.py --dir results/estimates_fine --p $p --methods $M; done
  echo '```'; } > $T/fine_bsort100.md
$PY tools/multiwindow_table.py --w0 results/estimates_fine --mw results/estimates_fine --benches bsort100 \
  --pairs CHB-COP:E2E-CHB,CHB-COP:CHB-COP@max --out $T/fine_multiwindow.md > /dev/null

# fixed copula families of cb1, cb4, cb7 (cb5 has no composed loop)
for cb in cb1 cb4 cb7; do
  for f in gaussian student clayton gumbel frank joe bb1 tawn; do
    cp $O/e25_${cb}_$f/$cb.json results/jobs/full_e25/${cb}_$f/$cb.json
  done
done
results/jobs/full_post.sh e25

# stress tests, X2, X3
cp $O/e214/estimates_*.json results/e214/
results/jobs/full_post.sh e214
cp $O/x2/x2_cb1.json results/x2/x2_cb1.json
results/jobs/full_post.sh x2
for b in qsort-exam select; do cp $O/x3/x3_$b.json results/x3/x3_$b.json; done
results/jobs/full_post.sh x3

# tables and figures of the paper
$PY tools/paper_tables.py > /dev/null
$PY tools/fig_tightness.py > /dev/null
$PY tools/fig_mixing.py > /dev/null
echo "merged; measure the analysis time of cb1, cb4, cb6, cb7 with tools/scope_cost.py, then"
echo "  $PY tools/scope_cost.py --table > $T/cost_scope.md"
