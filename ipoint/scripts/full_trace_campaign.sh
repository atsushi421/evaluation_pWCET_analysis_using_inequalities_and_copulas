#!/bin/bash
# Second benchmark campaign with every run fully traced (paper repo
# review_comments_ieeeaccess_first/answers_draft/09_additional_evaluation.md, decision D1 (b1)).
#
# The first campaign (traces/, traces_fine/, 2026-08-31) kept the IPoint records of the first 1e5
# runs only. Those runs have a heavier far tail than the summary-only runs from which the reference
# quantiles came, so the training windows were optimistic. This campaign runs the TIMING build of the
# same instrumented sources (traces/<b>/<b>.ipoint.c) with --full-trace-runs = --runs and the same
# seeds, core and arguments, and the OFF build of the same session for the probe effect. The COVERAGE
# runs of the first campaign are reused (same binary and seeds). The harness adapters of qsort-exam and
# select are taken from the revision before the adversarial inputs (b7dc73b), as in the first campaign.
#
#   ipoint/scripts/full_trace_campaign.sh build        # binaries into bench/build/full/, objdump check
#   ipoint/scripts/full_trace_campaign.sh run          # measurement on isolated core 6 (keep the machine idle)
#   ipoint/scripts/full_trace_campaign.sh parse [P]    # per-unit samples, consistency check, overhead, SMI censoring
# Outputs: traces_full/<b>/ (12 kernels, 1e7 runs) and traces_fine_full/bsort100/ (2e6 runs).
set -euo pipefail
cd "$(dirname "$0")/.."
IP=$PWD
BENCHES="bsort100 fir matmult edn ndes st lms prime cnt ludcmp select qsort-exam"
CORE=6
ADAPTER_REV=b7dc73b~1

# name src_dir out_dir runs
targets() {
  for b in $BENCHES; do echo "$b traces/$b traces_full/$b 10000000"; done
  echo "bsort100 traces_fine/bsort100 traces_fine_full/bsort100 2000000"
}
build_dir() { [ "$2" = traces_fine/bsort100 ] && echo "build/full/bsort100_fine" || echo "build/full/$1"; }
ids() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); u={x["uid"]: x for x in d["units"]}[d["entry_function"]]; print(u["entry"], u["exit"], d["max_id"])' "$1"; }

do_build() {
  targets | while read -r b src out runs; do
    bd=$(build_dir "$b" "$src")
    defs=""; [ "$b" = select ] && defs="-std=c11 -Dselect=mrtc_select"
    adapter=$IP/bench/$b/bench_$b.c
    if [ "$b" = select ] || [ "$b" = qsort-exam ]; then
      mkdir -p "bench/$bd"
      adapter=$IP/bench/$bd/bench_$b.first_campaign.c
      git show "$ADAPTER_REV:ipoint/bench/$b/bench_$b.c" > "$adapter"
    fi
    for mode in timing off; do
      make -s -C bench BENCH="$b" MODE=$mode SRC="$IP/$src/$b.ipoint.c" BUILD="$bd/$mode" \
        ADAPTER="$adapter" KERNEL_DEFS="$defs"
    done
    ref=bench/build/$b/timing/kernel.objdump
    [ "$b" = select ] && ref=bench/build/select.coarse/timing/kernel.objdump
    if [ "$src" = "traces/$b" ] && [ -f "$ref" ] && cmp -s <(tail -n +3 "$ref") <(tail -n +3 "bench/$bd/timing/kernel.objdump"); then
      echo "$b ($src): kernel identical to the first-campaign build"
    else
      echo "$b ($src): no first-campaign objdump to compare"
    fi
  done
}

do_run() {
  targets | while read -r b src out runs; do
    bd=$(build_dir "$b" "$src")
    read -r e x m < <(ids "$src/schema_timing.json")
    mkdir -p "$out"
    cmds=()
    for mode in timing off; do
      n=$runs full=$runs
      [ $mode = off ] && n=100000 full=0
      cmd=(taskset -c $CORE "$IP/bench/$bd/$mode/bench_$b" --out "$out/$mode" --runs $n --full-trace-runs $full
           --seed0 20260829 --core $CORE --warmup 1000 --param 0.0 --entry-id "$e" --exit-id "$x" --max-id "$m" --calib 1)
      echo "+ ${cmd[*]}" >&2
      "${cmd[@]}"
      cmds+=("${cmd[*]}")
    done
    for f in schema_full.json schema_timing.json exclusions.json "$b.ipoint.c" "$b.ipoint_full.c" coverage.json; do
      cp "$src/$f" "$out/$f"
    done
    ln -sfn "$IP/$src/coverage" "$out/coverage"
    python3 - "$out/campaign.json" "$src" "$(tools/sysinfo.sh $CORE)" "${cmds[@]}" <<'EOF'
import json, sys
path, src, sysinfo, *cmds = sys.argv[1:]
json.dump({"first_campaign": src, "note": "every TIMING run fully traced; coverage/ links to the first campaign",
           "sysinfo": json.loads(sysinfo), "commands": cmds}, open(path, "w"), indent=1)
EOF
  done
}

# the parser keeps every unit instance in Python lists (about 150 bytes each), so the traces are parsed in chunks
# of at most CHUNK_INSTANCES instances and merged
CHUNK_INSTANCES=30000000
parse_chunk() {
  read -r out skip n <<<"$1"
  mkdir -p "$out/chunks"
  python3 tools/ipoint_parse.py --schema "$out/schema_timing.json" --trace-dir "$out/timing" --out "$out/chunks/$skip" \
    --lean --skip-runs "$skip" --max-runs "$n" > "$out/chunks/$skip.log" 2>&1 || echo "FAILED: parse $out $skip" >&2
}
chunks() {   # <out> <runs> <first-campaign dir>: one line per chunk, sized by the first campaign's instances per run
  local out=$1 runs=$2 per
  per=$(python3 -c 'import json,sys; s=json.load(open(sys.argv[1])); n=s["runs_parsed"]; print(sum(v.get("n", 0) for v in s["units"].values()) / n)' "$3/parsed/stats.json")
  local size=$(python3 -c "import math; print(min($runs, max(10000, int($CHUNK_INSTANCES / max($per, 1)) // 10000 * 10000)))")
  for ((k = 0; k < runs; k += size)); do echo "$out $k $((runs - k < size ? runs - k : size))"; done
}
parse_one() {
  read -r b src out runs <<<"$1"
  python3 tools/merge_parsed.py --out "$out/parsed" $(ls -d "$out"/chunks/*/ | sort -t/ -k4 -n) > "$out/parse.log" 2>&1 \
    && rm -rf "$out/chunks" || { echo "FAILED: merge $out" >&2; return; }
  python3 tools/ipoint_check.py --schema "$out/schema_timing.json" --trace-dir "$out/timing" --parsed "$out/parsed" \
    > "$out/check.log" 2>&1 || true
  python3 tools/ipoint_overhead.py --off "$out/off" --timing "$out/timing" --coverage "$out/coverage" \
    --out "$out/overhead.json" > /dev/null
  echo "parsed $out: $(tail -1 "$out/check.log")"
}

case "${1:-}" in
  build) do_build ;;
  run) do_run ;;
  parse)
    export -f parse_one parse_chunk
    targets | while read -r b src out runs; do chunks "$out" "$runs" "$src"; done \
      | xargs -d '\n' -P "${2:-8}" -I{} bash -c 'parse_chunk "$@"' _ {}
    targets | xargs -d '\n' -P 4 -I{} bash -c 'parse_one "$@"' _ {}
    python3 tools/smi_censor.py --traces traces_full --bench "${BENCHES// /,}"
    python3 tools/smi_censor.py --traces traces_fine_full --bench bsort100 ;;
  *) echo "usage: $0 build|run|parse [P]" >&2; exit 2 ;;
esac
