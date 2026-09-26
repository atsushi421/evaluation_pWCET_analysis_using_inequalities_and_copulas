#!/bin/bash
# Post-processing of the second benchmark campaign and the n_sims-1000 recompute (paper repo answers_draft/09,
# J13-J15; 02_experiments_plan.md section 8.17). Each section merges finished job outputs into the stored result
# sets and regenerates its tables; the first call backs up the stored results of the first campaign.
#   results/jobs/full_post.sh bench|n1e5|fine|aw|e25|e214|cert|tables
set -eo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
T=results/tables
BK=results/backup_pre_full
BENCHES="bsort100 fir matmult edn ndes st lms prime cnt ludcmp select qsort-exam"
CBS="cb1 cb2 cb3 cb4 cb5 cb6 cb7"

if [ ! -d $BK ]; then
  mkdir -p $BK/e214
  for d in estimates estimates_multiwindow estimates_fine estimates_n1e5 estimates_autoware_warm1 estimates_autoware_all \
           estimates_autoware_warm1_mw certification synthetic tables figs; do cp -a results/$d $BK/; done
  cp results/e214/estimates*.json $BK/e214/
fi

merge_into() {   # merge_into <dir> <name> <part.json...>: a fresh <dir>/<name>.json from the parts
  local dir=$1 name=$2; shift 2
  mkdir -p "$dir"; rm -f "$dir/$name.json"
  $PY tools/merge_estimates.py --into "$dir/$name.json" "$@" > /dev/null
}

w0_tables() {   # w0_tables <dir> <file> <header> <p...>
  local dir=$1 out=$2 head=$3; shift 3
  { echo "$head"; echo; echo '```'; for p in "$@"; do $PY tools/estimates_table.py --dir "$dir" --p "$p"; done; echo '```'; } > "$out"
}

case "${1:-}" in
bench)
  for b in $BENCHES; do merge_into results/estimates $b results/jobs/full/${b}_w*/$b.json; done
  rm -rf results/estimates_multiwindow
  $PY tools/multiwindow_table.py --w0 results/estimates --mw results/estimates --out $T/multiwindow.md > /dev/null
  $PY tools/multiwindow_table.py --w0 results/estimates --mw results/estimates --p 1e-05 --out $T/multiwindow_p1e-5.md > /dev/null
  for p in 1e-4 1e-5 1e-6; do
    w0_tables results/estimates $T/w0_p$p.md "Benchmarks, second campaign (every run traced), window 0 (n = 1e4)." $p
  done ;;
n1e5)
  for b in $BENCHES; do merge_into results/estimates_n1e5 $b results/jobs/full_n1e5/${b}_w*/$b.json; done
  w0_tables results/estimates_n1e5 $T/n1e5.md "J1(b): training windows of n = 1e5 runs (second campaign), window 0; SMI-censored reference of all 1e7 runs." 1e-4 1e-5 1e-6
  $PY tools/multiwindow_table.py --w0 results/estimates_n1e5 --mw results/estimates_n1e5 --p 1e-05 \
    --pairs E2E-CHB:E2E-MEMIK,CHB-COP:MEMIK-COP --out $T/n1e5_multiwindow.md > /dev/null ;;
fine)
  merge_into results/estimates_fine bsort100 results/jobs/full_fine/bsort100_w*/bsort100.json
  M=E2E-CHB,E2E-MEMIK,E2E-EVT-PoT,EVT-COP,MEMIK-COP,CHB-IND,CHB-COMONO,CHB-COP,CHB-IND@inst,CHB-COP@inst
  { echo "Fine-granularity bsort100 (100 ns floor), second campaign (2e6 runs, all traced), window 0; @inst = per-instance loop rule."
    echo; echo '```'; for p in 1e-4 1e-5 1e-6; do $PY tools/estimates_table.py --dir results/estimates_fine --p $p --methods $M; done
    echo '```'; } > $T/fine_bsort100.md
  $PY tools/multiwindow_table.py --w0 results/estimates_fine --mw results/estimates_fine --benches bsort100 \
    --pairs CHB-COP:E2E-CHB,CHB-COP:CHB-COP@inst --out $T/fine_multiwindow.md > /dev/null ;;
aw)
  for v in warm1 all; do
    for cb in $CBS; do
      parts=(results/jobs/full_aw/${v}_${cb}_w*/$cb.json)
      mkdir -p results/estimates_autoware_$v
      cp $BK/estimates_autoware_$v/$cb.json results/estimates_autoware_$v/$cb.json     # keeps MEMIK-COP, EVT-COP of window 0
      $PY tools/merge_estimates.py --into results/estimates_autoware_$v/$cb.json "${parts[@]}" > /dev/null
    done
  done
  rm -rf results/estimates_autoware_warm1_mw
  for v in warm1 all; do
    if [ $v = warm1 ]; then h="steady state: the first nominal invocation of every replay dropped"; else h="all nominal invocations"; fi
    w0_tables results/estimates_autoware_$v $T/autoware_w0_$v.md "Autoware, window 0 (n = 1e4 nominal invocations), $h; RESTK n_sims 1000." 1e-4 1e-5
  done
  $PY tools/multiwindow_table.py --w0 results/estimates_autoware_warm1 --mw results/estimates_autoware_warm1 \
    --benches ${CBS// /,} --out $T/autoware_multiwindow.md > /dev/null ;;
e25)
  F=CHB-COP,CHB-IND,CHB-COMONO,CHB-FAM-gaussian,CHB-FAM-student,CHB-FAM-clayton,CHB-FAM-gumbel,CHB-FAM-frank,CHB-FAM-joe,CHB-FAM-bb1,CHB-FAM-tawn
  for b in $BENCHES cb1 cb4 cb5 cb7; do merge_into results/jobs/full_e25/merged $b results/jobs/full_e25/${b}_*/$b.json; done
  { echo "E2-5: every pair copula fixed to one family (BIC picks the rotation, no independence pre-test), window 0;"
    echo "CHB-COP/CHB-IND/CHB-COMONO of the stored window 0 for comparison. Benchmarks: second campaign; callbacks: steady state."
    echo; echo '```'
    for p in 1e-4 1e-5 1e-6; do
      $PY tools/estimates_table.py --dirs results/estimates,results/estimates_autoware_warm1,results/jobs/full_e25/merged --p $p --methods $F
    done; echo '```'; } > $T/e25_families.md ;;
e214)
  $PY - <<'EOF'
import json
a = json.load(open("results/e214/estimates_qsort_w0.json"))
b = json.load(open("results/e214/estimates_qsort_w1.json"))
a["windows"].update(b["windows"])
json.dump(a, open("results/e214/estimates.json", "w"), indent=1)
L = ["E2-14: estimates relative to the killer median (killer max, uniform-input reference in brackets at 1e-4), windows 0 and 1; RESTK n_sims 1000.", ""]
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
  ;;
cert)
  $PY tools/certification_table.py --dir results/certification --out $T/certification.md > /dev/null
  $PY tools/fig_pwcet_concept.py --traces ipoint/traces_full --out results/figs/pwcet_concept.pdf ;;
tables)
  $PY tools/tables.py --traces ipoint/traces_full --results results/estimates --multiwindow results/estimates > /dev/null
  $PY tools/neff_table.py --traces ipoint/traces_full --results results/estimates --out $T/neff.md > /dev/null
  $PY tools/neff_table.py --traces ipoint/autoware/traces/autoware/bench_warm1 --results results/estimates_autoware_warm1 \
    --benches ${CBS// /,} --out $T/neff_autoware.md > /dev/null ;;
*) echo "usage: $0 bench|n1e5|fine|aw|e25|e214|cert|tables" >&2; exit 2 ;;
esac
echo "full_post $1 done"
