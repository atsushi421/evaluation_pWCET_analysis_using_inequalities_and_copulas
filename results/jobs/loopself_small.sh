#!/bin/bash
# The stress tests (E2-14), X2, and X3 with the loop rule that includes the self time of the loop (J1 of the
# paper repo .review/2026-10-02-revision-fourth-check.md). Outputs go to results/jobs/loopself/{e214,x2,x3}/;
# loopself_post.sh moves them into results/.
set -e
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
O=results/jobs/loopself
mkdir -p $O/e214 $O/x2 $O/x3
PY=.venv/bin/python
for w in 0 1; do
  $PY ipoint/e214/estimate.py --windows $w --out $O/e214/estimates_qsort_w$w.json > $O/e214/estimate_qsort_w$w.log 2>&1
  $PY ipoint/e214/estimate.py --bench select --windows $w --out $O/e214/estimates_select_w$w.json > $O/e214/estimate_select_w$w.log 2>&1
done
$PY ipoint/e214/estimate.py --bench select --windows 0,1 --methods CHB-COP,CHB-IND,CHB-COMONO --bound select.L1=500 \
  --out $O/e214/estimates_select_b500.json > $O/e214/estimate_select_b500.log 2>&1
# X2 and X3: keep the end-to-end entries, recompute the decomposed ones
$PY - <<'EOF'
import json
d = json.load(open("results/x2/x2_cb1.json"))
json.dump({k: v for k, v in d.items() if not k.split("/")[-1].startswith("CHB")}, open("results/jobs/loopself/x2/x2_cb1.json", "w"), indent=1)
for b in ("qsort-exam", "select"):
    d = json.load(open(f"results/x3/x3_{b}.json"))
    json.dump({k: {m: v for m, v in ms.items() if not m.startswith("CHB")} for k, ms in d.items()},
              open(f"results/jobs/loopself/x3/x3_{b}.json", "w"), indent=1)
EOF
WORKERS=2 $PY tools/x2_queue_full.py ipoint/autoware/traces/x2_queuefull/bench_warm1 $O/x2/x2_cb1.json > $O/x2/x2.log 2>&1
for b in qsort-exam select; do
  $PY tools/x3_mixing_sweep.py $b $O/x3/x3_$b.json --like results/x3/x3_$b.json --workers 2 > $O/x3/x3_$b.log 2>&1
done
echo done > $O/small.done
