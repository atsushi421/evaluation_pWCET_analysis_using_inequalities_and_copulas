# ipoint: unit-level execution-time instrumentation for CHB-COP

`ipoint` collects the per-unit execution-time traces that the pWCET estimators
in this repository consume. It implements the *Instrumentation Points*
(IPoints) of the paper: a C program is decomposed by static analysis into basic
units (function bodies, the alternatives of every `if`, loops and loop bodies),
an IPoint is placed at every entry and exit of a unit, and each IPoint records
a serialized timestamp. The end-to-end time of a run is the interval between
the outermost IPoint pair, so the end-to-end baseline and the decomposed
methods share exactly the same measurements.

```
ipoint/
├── include/ipoint.h          runtime probe (header-only C11/C++17)
├── src/ipoint_probe_bench.c  probe cost and TSC calibration
├── tools/
│   ├── ipoint_instrument.py  static analysis (libclang) + IPoint insertion + schema.json
│   ├── ipoint_parse.py       raw trace -> per-unit samples, path signatures, statistics
│   ├── ipoint_check.py       consistency checks of a parsed trace
│   ├── ipoint_overhead.py    OFF vs TIMING comparison (probe effect)
│   ├── ipoint_coverage.py    path-coverage statistics from hit counts
│   ├── run_campaign.py       the whole measurement campaign
│   ├── ipoint_schema.py      schema data model shared by the tools
│   └── sysinfo.sh            environment description (JSON)
├── bench/                    harness for the Mälardalen kernels in ../benchmarks/malardalen
├── scripts/                  frequency pinning (sudo) and core pinning helpers
└── tests/                    toy programs, unit tests, end-to-end smoke test
```

## Quick start

```bash
pip install libclang numpy                      # libclang: python bindings with a bundled libclang.so
sudo ipoint/scripts/fix_frequencies.bash        # governor=userspace, nominal frequency, boost off
cd ipoint
python3 tools/run_campaign.py --probe-bench --out traces        # probe cost of every timestamp implementation
python3 tools/run_campaign.py --bench all --out traces --core 3 # instrument, pilot, build, run, parse
python3 tests/test_instrument.py && tests/test_roundtrip.sh     # self-tests
```

`run_campaign.py` runs, per benchmark, the stages `instrument`, `pilot`,
`build`, `run` and `parse` (select with `--stages`). Defaults reproduce the
paper's setting: `gcc -O2 -fno-builtin`, `10^7` runs, the first `10^5` runs
fully traced, `10^5` uninstrumented runs for the overhead experiment and `10^7`
coverage runs. Results go to `traces/<bench>/`:

| Path | Content |
|---|---|
| `timing/trace.bin`, `timing/summary.bin`, `timing/meta.json` | raw records of the fully traced runs, one summary row per run, harness metadata |
| `off/`, `coverage/` | the same for the uninstrumented and the coverage build |
| `parsed/units/<uid>.npy` | samples of one unit (TSC ticks, trace order); `.self.npy`, `.iters.npy`, `.gap<k>.npy` for containers, loops and functions |
| `parsed/sample/<uid>.pkl` | the same as pickled lists (input format of `copulas.ipynb`) |
| `parsed/e2e.npy`, `parsed/e2e_all.npy` | end-to-end times of the traced runs / of every run |
| `parsed/paths.csv`, `parsed/stats.json` | per-run path signatures, per-unit statistics |
| `overhead.json`, `coverage.json` | experiments E2-6 and E2-4 |
| `schema_full.json`, `schema_timing.json`, `exclusions.json`, `<bench>.ipoint.c` | the scope tree, the instrumented units and the instrumented source |
| `campaign.json` | environment (`sysinfo.sh`), configuration and every command executed |

## The probe

`IPOINT(id)` expands, in the `TIMING` build, to

```c
rdtscp ; lfence            /* serialized read of the invariant TSC, IA32_TSC_AUX = core */
buf[pos++] = {tsc, id, aux} /* thread-local buffer, 16 bytes per record */
```

as `asm volatile` with a `"memory"` clobber. `rdtscp` waits until every
preceding instruction has retired and the `lfence` behind it keeps subsequent
instructions from issuing before the timestamp has been read, so consecutive
IPoints partition the instruction stream of the thread: the sum of the unit
intervals of a run equals the outermost interval exactly (checked by
`ipoint_check.py`). The compiler cannot move memory accesses across a probe.
No `noinline` attribute is used; a probe stays at its source position when
the function is inlined, so the measured binary is the `-O2` binary plus the
probes. The TSC is invariant (`constant_tsc`, `nonstop_tsc`) and its frequency
is calibrated against `CLOCK_MONOTONIC_RAW` at the start and the end of every
campaign (`meta.json: tsc_hz_start/end`).

Alternative implementations for comparison (`-DIPOINT_TS_IMPL=...`):
`lfence; rdtsc; lfence` (Linux `rdtsc_ordered()`), `cpuid; rdtsc` (Intel's
benchmarking white paper, Paoloni 2010) and `clock_gettime(CLOCK_MONOTONIC_RAW)`.
Measured on the Xeon Silver 4216 (TSC 2095.077 MHz), distance between two
back-to-back IPoints, `10^6` pairs:

| implementation | min | median | p99 | notes |
|---|---|---|---|---|
| `rdtscp; lfence` (default) | 20.0 ns | 22.0 ns | 23.9 ns | serializing, carries the core id |
| `lfence; rdtsc; lfence` | 20.0 ns | 22.0 ns | 23.9 ns | serializing |
| `cpuid; rdtsc` | 36.3 ns | 41.0 ns | 44.9 ns | fully serializing, slow |
| `clock_gettime(CLOCK_MONOTONIC_RAW)` | 20.0 ns | 22.0 ns | 24.0 ns | vDSO, not serializing |

Build modes: `-DIPOINT_MODE_TIMING` (records), `-DIPOINT_MODE_COVERAGE`
(per-id hit counters, no timestamps) and `-DIPOINT_MODE_OFF` (the probe
expands to nothing; the uninstrumented baseline of the overhead experiment).

## Static analysis and instrumentation

`ipoint_instrument.py` parses the source with libclang, builds the scope tree
of every function definition and assigns IPoint ids on the *full* tree
(depth-first, so ids do not depend on the granularity policy). Units:

| kind | IPoints | timing schema |
|---|---|---|
| `function` | entry after `{`, exit before every `return` and the closing `}` | `W = self + sum(children)` |
| `loop` | before and after the loop statement | `W = self + sum over iterations of body` |
| `loop_body` | inside the body (braces are added to a single-statement body) | one sample per iteration; the static bound comes from `for (i = c0; i < c1; ...)` with literal or macro bounds, otherwise from `bench/bounds/<bench>.bounds.json` |
| `branch` | none (container) | `W = max` over alternatives |
| `alternative` | inside each `then`/`else`; a missing or empty `else` is a single marker IPoint | |

Before every `return`, `break` and `continue` the exits of all instrumented
units that the jump leaves are emitted, innermost first, so every entry is
matched by exactly one exit. `switch` statements are not decomposed (none of
the kernels uses one). The result is `schema.json`: the unit tree with ids,
kinds, loop bounds and the calls made from each unit, which `ipoint_parse.py`
uses to pair the records of a run and to attribute self time to parents.

Granularity is decided by data (`pilot` stage): every unit is instrumented,
a short pilot is measured, and units whose median duration is below
`--min-unit-ns` (default 300 ns, about 14 probe costs) lose their probes;
this is repeated until it converges, because a parent shrinks once its
children lose their probes. `--max-depth N` replaces the pilot by a fixed
policy. Excluding a unit excludes its descendants. The `coverage` build always
instruments every unit, so path coverage (`coverage.json`) is measured at the
finest granularity while timing is measured at the granularity the probe
effect allows.

## Harness

`bench/common/bench_main.c` links the instrumented kernel (its `main` is
renamed away) with a per-benchmark adapter that generates the input from the
run seed (`splitmix64(seed0 + run)`, then `xoshiro256**`), calls the kernel's
entry function once and folds the output into a `volatile` sink. Inputs are
written from another translation unit, so `-O2` cannot constant-fold the
kernel (the stock `bsort100` with its fixed initialiser is folded to a few
dozen instructions). Input ranges: `bsort100` 100 unconstrained 32-bit
integers (`bsort100.ann`, the only kernel with an upstream annotation),
`matmult` `[0, 8095)` as the kernel's own generator, `fdct` 8-bit samples,
`fir` 7-bit samples with the kernel's coefficients, `sqrt` `val ~ U(0, 65536)`
with `val = 0` with probability `--param` (default `10^-3`).

The harness pins itself to `--core`, locks its memory, warms up, and for every
run records one summary row (`run, seed, e2e_ticks, harness_ticks, sink,
n_records, overflow, hits[]`). The complete IPoint trace is kept for the first
`--full-trace-runs` runs; afterwards only the summary row is written, so a
`10^7`-run campaign stays at about 1 GB per benchmark. Sample order is the
execution order, so serial dependence can be examined later.

## Data formats

* `trace.bin`: little-endian records `u64 ts, u32 id, u32 aux` (`aux` =
  `IA32_TSC_AUX`, bits 0-11 are the core). Runs are delimited by sentinel ids
  `0xFFFFFFF0` (ts = run index), `0xFFFFFFF1` (ts = seed) and `0xFFFFFFF2`
  (ts = timestamp at the end of the run).
* `summary.bin`: rows `u64 run, u64 seed, u64 e2e_ticks, u64 harness_ticks,
  u64 sink, u32 n_records, u32 overflow, u32 hits[max_id + 1]`.
* Ticks convert to nanoseconds with `meta.json: tsc_hz_start`
  (`ipoint_parse.py --ns` does it).

## Using the samples with the estimators

`parsed/units/<uid>.npy` is a 1-D array of strictly positive ticks and can be
fed to `memik`, `atan` and `tanh` directly (`chb_main.ipynb` expects
`synthetic_samples/<name>.npy`). `parsed/sample/<uid>.pkl` matches the input
of `copulas.ipynb`; `ipoint_parse.py --legacy-names map.json` writes them under
the names used there (`u0101`, `u0102`). `<uid>.run.npy` gives the run index of
every sample, which aligns the samples of different units for copula fitting.
