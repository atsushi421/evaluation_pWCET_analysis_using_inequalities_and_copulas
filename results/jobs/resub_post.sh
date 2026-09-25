#!/bin/bash
# Post-processing of the resubmission recompute (02_experiments_plan.md section 8.16): merge the job
# outputs into the stored result sets and regenerate the tables. Run from the repository root after
# resub_bench.txt, resub_aw.txt and the three ipoint/e214/estimate.py runs have finished.
#   results/jobs/resub_post.sh
set -eo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
T=results/tables

# Sections 1 and 2 run only once: a second --diff would compare the merged values with themselves.
if [ ! -f $T/resub_diff.md ]; then
# 1. benchmarks: diff against the stored values, then merge (backup in results/backup_pre_resub)
$PY tools/merge_monotone.py --jobs results/jobs/resub_bench.txt --tag resub --diff --out $T/resub_diff.md > /dev/null
$PY tools/merge_monotone.py --jobs results/jobs/resub_bench.txt --tag resub --apply
$PY tools/multiwindow_table.py --out $T/multiwindow.md > /dev/null
for p in 1e-4 1e-5 1e-6; do
  { echo "Benchmarks, window 0 (n = 1e4), resubmission pipeline (count-aware loops, tanh leaf)."; echo; echo '```';
    $PY tools/estimates_table.py --dir results/estimates --p $p; echo '```'; } > $T/w0_p$p.md
done
{ echo "Fine-granularity bsort100 (100 ns floor), window 0; @inst = per-instance loop rule."; echo; echo '```';
  for p in 1e-4 1e-5 1e-6; do
    $PY tools/estimates_table.py --dir results/estimates_fine --p $p \
      --methods E2E-CHB,E2E-MEMIK,E2E-EVT-PoT,EVT-COP,MEMIK-COP,CHB-IND,CHB-COMONO,CHB-COP,CHB-IND@inst,CHB-COP@inst; done; echo '```'; } > $T/fine_bsort100.md

# 2. E2-14: the two qsort-exam windows into estimates.json (select already holds both windows)
$PY - <<'EOF'
import json
a = json.load(open("results/e214/estimates_qsort_w0.json"))
b = json.load(open("results/e214/estimates_qsort_w1.json"))
a["windows"].update(b["windows"])
json.dump(a, open("results/e214/estimates.json", "w"), indent=1)
L = ["E2-14: estimates relative to the killer median (killer max, uniform-input reference in brackets at 1e-4), windows 0 and 1.", ""]
for f in ("results/e214/estimates.json", "results/e214/estimates_select.json"):
    d = json.load(open(f))
    L += [f"## {d['bench']} (killer median / uniform reference(1e-4) = {d['killer_median'] / d['rand_ref']['0.0001']:.2f})", "",
          "| method | window | 1e-4 | 1e-5 | 1e-6 | vs killer max (1e-4) | vs uniform ref (1e-4) |", "|---|---|---|---|---|---|---|"]
    methods = list(next(iter(d["windows"].values()))["methods"])
    for m in methods:
        for w, wr in d["windows"].items():
            e = wr["methods"].get(m)
            if e is None:
                continue
            km = e["vs_killer_median"]
            L.append(f"| {m} | {w} | {km['0.0001']:.3f} | {km['1e-05']:.3f} | {km['1e-06']:.3f} | "
                     f"{e['vs_killer_max']['0.0001']:.3f} | {e['vs_rand_ref']['0.0001']:.3f} |")
    L.append("")
open("results/tables/e214.md", "w").write("\n".join(L))
EOF

fi

# 3. Autoware: window 0 of both variants (cb4 and cb7 merged from the per-method jobs), windows 1-9 steady state
AW=results/jobs
for var in warm1 all; do
  D=results/estimates_autoware_$var; mkdir -p $D
  for cb in cb1 cb2 cb3 cb5 cb6; do cp $AW/resub_aw_$var/$cb/$cb.json $D/$cb.json; done
  for cb in cb4 cb7; do rm -f $D/$cb.json; $PY tools/merge_estimates.py --into $D/$cb.json $AW/resub_aw_${var}_$cb/*/$cb.json; done
done
D=results/estimates_autoware_warm1_mw; mkdir -p $D
for cb in cb1 cb2 cb3 cb4 cb5 cb6 cb7; do cp $AW/resub_aw_warm1_mw/$cb/$cb.json $D/$cb.json; done
for var in warm1 all; do
  if [ $var = warm1 ]; then h="steady state: the first nominal invocation of every replay dropped (make_bench.py --warmup 1)"
  else h="all nominal invocations"; fi
  { echo "Autoware case study, window 0 (n = 1e4 nominal invocations), $h; resubmission pipeline."; echo; echo '```';
    for p in 1e-4 1e-5; do $PY tools/estimates_table.py --dir results/estimates_autoware_$var --p $p; done; echo '```'; } > $T/autoware_w0_$var.md
done
$PY tools/multiwindow_table.py --w0 results/estimates_autoware_warm1 --mw results/estimates_autoware_warm1_mw \
  --benches cb1,cb2,cb3,cb4,cb5,cb6,cb7 --out $T/autoware_multiwindow.md > /dev/null
echo "post-processing done"
