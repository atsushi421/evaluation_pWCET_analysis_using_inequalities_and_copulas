# Mälardalen WCET benchmarks used in the paper

This directory holds unmodified copies of the Mälardalen (MRTC) WCET benchmark kernels evaluated in

> A. Yano, H. Toba, T. Azumi, "pWCET Estimation Based on Probabilistic Inequalities and Copulas Utilizing Static Analysis Information" (IEEE Access, under review), Section "Evaluation", Table "Benchmark programs".

They are kept here so the benchmark stage of the evaluation can be reproduced without depending on the availability of the upstream server. The first submission used five kernels (`bsort100`, `fdct`, `fir`, `matmult`, `sqrt`); the revision screens all 35 programs of the suite with three stated criteria (see "Selection" below) and evaluates twelve: `bsort100`, `fir`, `matmult`, `edn`, `ndes`, `st`, `lms`, `prime`, `cnt`, `ludcmp`, `select`, `qsort-exam`. `fdct.c` and `sqrt.c` are kept for reference and remain usable with the harness.

## Provenance

- Official page: http://www.mrtc.mdh.se/projects/wcet/benchmarks.html (Mälardalen Real-Time Research Centre, maintainer listed on the page: jan.gustafsson@mdh.se)
- Retrieved: 2026-08-29 (first five files) and 2026-08-30 (the other nine), via `http://www.mrtc.mdh.se/projects/wcet/wcet_bench/<name>/<name>.c`
- Upstream version: the `$Id$` header of every file points to the 2018 revisions of the MDH WCET benchmark suite (SVN r7800 for `bsort100.c`, `matmult.c`, `cnt.c`, `ludcmp.c`; r7801 for `fdct.c`, `fir.c`, `sqrt.c`, `ndes.c`, `st.c`, `lms.c`, `prime.c`, `select.c`, `qsort-exam.c`; r7927 of 2018-08-01 for `edn.c`). These are the newest revisions published on the server.
- Files are byte-identical to upstream. SHA-256 at retrieval time:

| File | SHA-256 |
|------|---------|
| `bsort100.c` | `bab10cd151b3ac715b60f8d4346057cbba9d42455480e8ad9ec8b650a1676616` |
| `fdct.c` | `80b5fe2b1b527c0a32c178c83ae999f1b2ccd0c299a646539eb8053c3d96bfa5` |
| `fir.c` | `34a18386c7921d46081e4c92613051083076ed3533698468ff98d1fae76ffc56` |
| `matmult.c` | `6e721924b72964d11e06e5f3e28ce41e9cbd5fd2a9bf5872a2d044c78e22dc43` |
| `sqrt.c` | `5a4ce9b20f634eee2c57e0157f6a577094467dec4038dd2cc25d3cb69ddbdb30` |
| `edn.c` | `5f74b6c6c038950efd3781c8720dd7c1cd5e02ce6fcc313d976808a58df79385` |
| `ndes.c` | `49c3086b57f864164836a8807e6b300ada66bf2163824dc71e6ba52b7d9ff3fd` |
| `st.c` | `2ca305d7baa5b288f30b9eab43ae5d08757b4a0a65abd65ca5aed768e562dd8c` |
| `lms.c` | `e9512d71fcd2e03003a8ffd5b1c01c65e661ee8ac8267ef56b5245875e714185` |
| `prime.c` | `dfecf9fa269b3cde68f93173fe64c4ed381edc93c43d82653e5341db830fc248` |
| `cnt.c` | `700dd9d26232e4c7ae1313b52b98c9985ab1169b7e6c826bb15cbc771d764538` |
| `ludcmp.c` | `b90ca16cc844f3afd791e63baf1e0026acfdd8b19316a69c0fd26b7db90bb2dd` |
| `select.c` | `001ad711296a8af4ca23f372d553b5d892ed248cacba3b34ef75d2f914e09668` |
| `qsort-exam.c` | `50fa53e19b2e002b6b89adfbba0c99b51079aebe9bbddeff902817c7bca3c48f` |

### Size patches (`patches/`)

Three kernels are too short at their upstream problem sizes for unit-level measurement (criterion (ii) below) but are the only input-dependent sorting/selection/counting kernels of the suite. For them a one-line size patch is applied by `ipoint/tools/run_campaign.py` into `ipoint/bench/build/<name>/<name>.c` before instrumentation; the files in this directory stay unmodified. Varying these sizes has precedent in the MBPTA literature (DBL-MBPTA, RTSS 2024, uses insertion/quick sort with 10 to 1500 elements and `cnt` with up to 100).

| Patch | Change | Note |
|-------|--------|------|
| `patches/qsort-exam.size.patch` | `float arr[20]` to `float arr[1000]` | the kernel sorts `arr[1..n]`; the harness calls `sort(999)` |
| `patches/select.size.patch` | `float arr[20]` to `float arr[1000]` | the kernel indexes `arr[0..n-1]`; the harness calls `select(500, 1000)` |
| `patches/cnt.size.patch` | `#define MAXSIZE 10` to `100` | 100 is the value the upstream comment records as the original (`/* #define MAXSIZE 100 Changed JG/Ebbe */`) |

`ludcmp` needs no patch: its arrays are `a[50][50]`, so the harness calls `ludcmp(49, eps)` instead of the `n = 5` of the stock `main`.

`bsort100.ann` is the SWEET annotation file shipped next to `bsort100.c` upstream (the only one of the five kernels that has one). It declares `Array` as 100 unconstrained 32-bit integers at the entry of `main` (`ASSIGN Array 32 32 100 TOP_INT`), which is the input-range assumption the paper refers to as "the default parameters specified in the annotation files provided with the benchmarks".

The upstream directories also contain SWEET/ALF artefacts (`.alf`, `.aral`, `.arm`, `.map`, `.nic`, `.tcd`) and, on the index page, call graphs (`.cg.pdf`), scope hierarchy graphs (`.sgh.pdf`) and loop-bound results (`.facit.txt`). They are tool-specific and are not copied here.

## Name mapping and characteristics

The paper abbreviates `bsort100` as `bsort`; all other names are identical to upstream.

| Paper name | Upstream file | Description | Kernel origin (from the file header) | Entry function and input supplied by the harness |
|------------|---------------|-------------|--------------------------------------|--------------------------------------------------|
| `bsort` | `bsort100.c` | Bubble sort of `NUMELEMS = 100` integers | MRTC | `BubbleSort`; 100 unconstrained 32-bit integers (`bsort100.ann`). The stock `Initialize()` fills `Array[i] = i` (ascending; `-DWORSTCASE` descending) |
| `fir` | `fir.c` | Integer FIR filter, 35 taps over 700 samples | "C Algorithms for DSP", adapted for WCET benchmarking in 2000 | `fir_filter_int`; 7-bit samples, the kernel's coefficients; values do not affect control flow |
| `matmult` | `matmult.c` | Multiplication of two 20x20 integer matrices (`UPPERLIMIT = 20`) | Thomas Lundqvist (Chalmers), Uppsala WCET variant | `Multiply`; entries in `[0, 8095)`, the range of the built-in LCG |
| `edn` | `edn.c` | Vector/FIR/IIR/lattice/DCT DSP kernels over 200-element arrays | MRTC (Uppsala) | `main` (constant arrays declared inside `main`); single path |
| `ndes` | `ndes.c` | DES block cipher with key schedule, bit operations | Numerical Recipes style DES, MRTC | `des`; uniform 64-bit block and key, fresh key schedule, random direction |
| `st` | `st.c` | Sum, mean, variance and correlation of two 1000-element `double` arrays | MRTC (Uppsala) | `main` (fixed-seed generator inside `main`); single path |
| `lms` | `lms.c` | NLMS adaptive filter, 20 taps over 201 float samples | "C Algorithms for DSP" | `main`; the test signal comes from the kernel's own `lms_rand()`, whose `static` state persists across runs, so the input differs from run to run (deterministic given the run order); the global step size `mu` is restored before every run |
| `prime` | `prime.c` | Trial-division primality test | MRTC | `prime`; `x ~ U(0, 2^32)`; the loop bound depends on the input (at most 32767 iterations) |
| `cnt` | `cnt.c` | Sum and count of positive and negative matrix entries | MRTC | `Sum`; signed entries in `[-8095, 8095)` over the 100x100 matrix of the size patch |
| `ludcmp` | `ludcmp.c` | LU decomposition and solve, `double` | SNU-RT benchmark suite | `ludcmp(49, 1e-6)`; diagonally dominant random system, so the pivot check never exits early |
| `select` | `select.c` | Selection of the k-th smallest of a float array (Numerical Recipes `select`) | SNU-RT benchmark suite | `select(500, 1000)`; 1000 values `U(0, 1000)` (size patch). The kernel object is compiled with `-std=c11 -Dselect=mrtc_select` because glibc declares `select()` through `<stdlib.h>` under the GNU feature set |
| `qsort-exam` | `qsort-exam.c` | Non-recursive quicksort of a float array (Numerical Recipes `sort`) | SNU-RT benchmark suite | `sort(999)`; 999 values `U(0, 1000)` (size patch) |
| `fdct` (v1 only) | `fdct.c` | Forward DCT of one 8x8 block, integer arithmetic (`fdct(block, 8)`) | MRTC | `fdct`; 8-bit samples; single path |
| `sqrt` (v1 only) | `sqrt.c` | Square root by Newton iteration, at most 20 iterations, early exit on `|diff| <= 1e-5` (`sqrtfcn(float)`) | SNU-RT benchmark suite, public-domain code | `sqrtfcn`; `val ~ U(0, 65536)`, `val = 0` with probability `--param` |

Feature flags used in the paper's table: S = single path, L = loops, N = nested loops, A = arrays/matrices, B = bit operations, F = floating point (from the upstream table, `sqrt`/`select`/`qsort-exam`/`ludcmp`/`st`/`lms` are the floating-point kernels).

| Kernel | S | L | N | A | B | F |
|--------|---|---|---|---|---|---|
| `bsort` |   | x | x | x |   |   |
| `fir` |   | x | x | x |   |   |
| `matmult` | x | x | x | x |   |   |
| `edn` | x | x | x | x | x |   |
| `ndes` |   | x |   | x | x |   |
| `st` | x | x |   | x |   | x |
| `lms` | x | x |   | x |   | x |
| `prime` | x | x |   |   |   |   |
| `cnt` |   | x | x | x |   |   |
| `ludcmp` |   | x | x | x |   | x |
| `select` |   | x | x | x |   | x |
| `qsort-exam` |   | x | x | x |   | x |
| `fdct` (v1) | x | x |   | x | x |   |
| `sqrt` (v1) | x | x |   |   |   | x |

## Selection

All 35 programs of the suite were screened with three criteria (details, measurements and the reviewer-facing table: paper repository `notes/malardalen_benchmark_selection.md`):

1. Structured control flow that the unit rules (function, `if`, loop) can decompose: excludes the `switch`-dominated `cover`, `duff`, `lcdnum`, `statemate`, the `goto`-based `compress`, and the recursive `fac` and `recursion` (whose upstream source also references an undefined symbol `In` and does not link).
2. Unit-level measurability: an uninstrumented end-to-end median of at least 2 us (about 100 probe costs of 22 ns), so that unit probes do not dominate. At upstream problem sizes this excludes `adpcm` (the codec itself takes 0.1-0.2 us per call), `bs`, `crc`, `expint`, `fft1`, `fibcall`, `insertsort`, `janne_complex`, `jfdctint`, `minver`, `ns`, `nsichneu`, `qurt`, `ud`, and also `fdct` and `sqrt` of the first submission. `cnt`, `select` and `qsort-exam` are recovered by the size patches and `ludcmp` by calling it at the largest order its arrays admit. `prime` is kept although its median is below the threshold, because its bimodal execution time (early exit for composite inputs, long trial division for primes) is the heavy-tailed case the paper discusses.
3. Loop bounds derivable from the source or from the declared input range: every loop of the selected kernels either has a literal/macro bound or a documented bound in `ipoint/bench/bounds/<name>.bounds.json`.

## Building

The paper compiles every kernel with

```bash
gcc -O2 -fno-builtin <name>.c
```

`-fno-builtin` keeps the compiler from replacing standard-library calls with intrinsics so that the binary keeps the structure assumed by the decomposition.

Verified on 2026-08-29 (GCC 11, Ubuntu 22.04): `bsort100.c`, `fdct.c`, `fir.c` and `matmult.c` build as standalone executables with no warnings. `sqrt.c` contains no `main` (the MRTC version renamed the kernel to `sqrtfcn` to avoid clashing with libm's `sqrt`), so it must be linked against a driver that calls `sqrtfcn(val)`; linking it alone fails with `undefined reference to main`. The nine kernels added on 2026-08-30 all build standalone; `st.c` needs `-lm`, `edn.c` declares `main` without a return type (implicit `int`), `ndes.c` contains unsequenced modifications (`ie.r = (ie.r <<= 1) | ...`, `itmp`) that GCC reports with `-Wsequence-point` and clang with `-Wunsequenced`, and `select.c` defines a function named `select` that clashes with the libc declaration once `<stdlib.h>` is included with GNU extensions.

## How the paper uses them

- Each kernel is instrumented with IPoints at the boundaries of its basic units (function bodies, branch paths, loop bodies) and executed 10^7 times. The empirical (1 - 10^-6)-quantile of the end-to-end execution time over all 10^7 runs is the reference pWCET.
- Only the first 10^4 samples are fed to the estimators (E2E, EVT-COP, CHB-COP); the target exceedance probability is 10^-6.
- Inputs are generated per run from a seed by the adapters in `ipoint/bench/<name>/` (ranges in the table above and in `ipoint/README.md`); array sizes and constants are the upstream defaults except for the three size patches.
- Platform of the revision: Intel Xeon Silver 4216 (2.10 GHz, fixed), Ubuntu 22.04, `taskset`-pinned core; the first submission used an Intel Core i7-10700 at 2.9 GHz.

The execution-time traces themselves are not part of this repository.

## Mirrors

If the MRTC server is unavailable:

- https://github.com/t-crest/patmos-benchmarks/tree/master/Malardalen/src keeps the kernels under their original names, plus multi-path test inputs under `Malardalen/inout/`.
- https://github.com/TRDDC-TUM/wcet-benchmarks is a modified copy (`int` to `int32`, timing annotations for ATmega); do not use it for comparison with the paper.
- https://github.com/tacle/tacle-bench (TACLeBench) contains successors of these kernels under different names (`bsort`, `jfdctint`, `fir2dim`, `matrix1`, `isqrt`) with changed code; not interchangeable with the versions here.

## Citation and licensing

The upstream page carries no license text and asks only that publications using the benchmarks cite:

> J. Gustafsson, A. Betts, A. Ermedahl, B. Lisper, "The Mälardalen WCET Benchmarks: Past, Present and Future", Proc. 10th Int. Workshop on Worst-Case Execution Time Analysis (WCET), pp. 136-146, 2010. doi:10.4230/OASIcs.WCET.2010.136

The files are redistributed here unmodified, with their original headers, for reproducibility only. Individual kernels carry their own origin notes in the header comments (`sqrt.c` is marked public domain by SNU-RT; the others carry no explicit statement).
