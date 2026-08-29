# Mälardalen WCET benchmarks used in the paper

This directory holds unmodified copies of the five Mälardalen (MRTC) WCET benchmark kernels evaluated in

> A. Yano, H. Toba, T. Azumi, "pWCET Estimation Based on Probabilistic Inequalities and Copulas Utilizing Static Analysis Information" (IEEE Access, under review), Section "Evaluation", Table "Benchmark programs".

They are kept here so the benchmark stage of the evaluation can be reproduced without depending on the availability of the upstream server.

## Provenance

- Official page: http://www.mrtc.mdh.se/projects/wcet/benchmarks.html (Mälardalen Real-Time Research Centre, maintainer listed on the page: jan.gustafsson@mdh.se)
- Retrieved: 2026-08-29, via `http://www.mrtc.mdh.se/projects/wcet/wcet_bench/<name>/<name>.c`
- Upstream version: the `$Id$` header of every file points to the 2018-01-19 revision of the MDH WCET benchmark suite (SVN r7800 for `bsort100.c` and `matmult.c`, r7801 for `fdct.c`, `fir.c`, `sqrt.c`). This is the newest revision published on the server.
- Files are byte-identical to upstream. SHA-256 at retrieval time:

| File | SHA-256 |
|------|---------|
| `bsort100.c` | `bab10cd151b3ac715b60f8d4346057cbba9d42455480e8ad9ec8b650a1676616` |
| `fdct.c` | `80b5fe2b1b527c0a32c178c83ae999f1b2ccd0c299a646539eb8053c3d96bfa5` |
| `fir.c` | `34a18386c7921d46081e4c92613051083076ed3533698468ff98d1fae76ffc56` |
| `matmult.c` | `6e721924b72964d11e06e5f3e28ce41e9cbd5fd2a9bf5872a2d044c78e22dc43` |
| `sqrt.c` | `5a4ce9b20f634eee2c57e0157f6a577094467dec4038dd2cc25d3cb69ddbdb30` |

`bsort100.ann` is the SWEET annotation file shipped next to `bsort100.c` upstream (the only one of the five kernels that has one). It declares `Array` as 100 unconstrained 32-bit integers at the entry of `main` (`ASSIGN Array 32 32 100 TOP_INT`), which is the input-range assumption the paper refers to as "the default parameters specified in the annotation files provided with the benchmarks".

The upstream directories also contain SWEET/ALF artefacts (`.alf`, `.aral`, `.arm`, `.map`, `.nic`, `.tcd`) and, on the index page, call graphs (`.cg.pdf`), scope hierarchy graphs (`.sgh.pdf`) and loop-bound results (`.facit.txt`). They are tool-specific and are not copied here.

## Name mapping and characteristics

The paper abbreviates `bsort100` as `bsort`; all other names are identical to upstream.

| Paper name | Upstream file | Description | Kernel origin (from the file header) | Fixed input in the stock source |
|------------|---------------|-------------|--------------------------------------|---------------------------------|
| `bsort` | `bsort100.c` | Bubble sort of `NUMELEMS = 100` integers | MRTC | `Initialize()` fills `Array[i] = i` (ascending); compiling with `-DWORSTCASE` fills it descending. The kernel is input-dependent, so the paper's harness supplies random arrays instead of this fixed initialiser. |
| `fdct` | `fdct.c` | Forward DCT of one 8x8 block, integer arithmetic (`fdct(block, 8)`) | MRTC | Hard-coded 64-element `block[]`; single path |
| `fir` | `fir.c` | Integer FIR filter, 35 taps over 700 samples (`fir_filter_int(in_data, output, 700, fir_int, 35, 285)`) | "C Algorithms for DSP", adapted for WCET benchmarking in 2000 | Hard-coded `in_data[701]`; iteration count fixed by the tap size, values do not affect control flow |
| `matmult` | `matmult.c` | Multiplication of two 20x20 integer matrices (`UPPERLIMIT = 20`) | Thomas Lundqvist (Chalmers), Uppsala WCET variant | Matrices filled by the built-in LCG `Seed = (Seed*133 + 81) % 8095` from `Seed = 0` |
| `sqrt` | `sqrt.c` | Square root by Newton iteration, at most 20 iterations, early exit on `|diff| <= 1e-5` (`sqrtfcn(float)`) | SNU-RT benchmark suite, public-domain code | No input in the file; the caller passes `val` (see below) |

Feature flags used in the paper's table: S = single path, L = loops, N = nested loops, A = arrays/matrices, B = bit operations, F = floating point.

| Kernel | S | L | N | A | B | F |
|--------|---|---|---|---|---|---|
| `bsort` |   | x | x | x |   |   |
| `fdct` | x | x |   | x | x |   |
| `fir` |   | x | x | x |   |   |
| `matmult` | x | x | x | x |   |   |
| `sqrt` | x | x |   |   |   | x |

## Building

The paper compiles every kernel with

```bash
gcc -O2 -fno-builtin <name>.c
```

`-fno-builtin` keeps the compiler from replacing standard-library calls with intrinsics so that the binary keeps the structure assumed by the decomposition.

Verified on 2026-08-29 (GCC 11, Ubuntu 22.04): `bsort100.c`, `fdct.c`, `fir.c` and `matmult.c` build as standalone executables with no warnings. `sqrt.c` contains no `main` (the MRTC version renamed the kernel to `sqrtfcn` to avoid clashing with libm's `sqrt`), so it must be linked against a driver that calls `sqrtfcn(val)`; linking it alone fails with `undefined reference to main`.

## How the paper uses them

- Each kernel is instrumented with IPoints at the boundaries of its basic units (function bodies, branch paths, loop bodies) and executed 10^7 times. The empirical (1 - 10^-6)-quantile of the end-to-end execution time over all 10^7 runs is the reference pWCET.
- Only the first 10^4 samples are fed to the estimators (E2E, EVT-COP, CHB-COP); the target exceedance probability is 10^-6.
- Inputs for the input-dependent kernels (`bsort`, `sqrt`) are drawn at random within the ranges implied by the annotation files; array sizes and constants are the defaults in the sources listed above.
- Platform: Intel Core i7-10700, 32 GB RAM, Ubuntu 22.04, CPU pinned and clock fixed at 2.9 GHz.

The execution-time traces themselves are not part of this repository.

## Mirrors

If the MRTC server is unavailable:

- https://github.com/t-crest/patmos-benchmarks/tree/master/Malardalen/src keeps `bsort100.c`, `fdct.c`, `fir.c`, `matmult.c`, `sqrt.c` under their original names, plus multi-path test inputs under `Malardalen/inout/`.
- https://github.com/TRDDC-TUM/wcet-benchmarks is a modified copy (`int` to `int32`, timing annotations for ATmega); do not use it for comparison with the paper.
- https://github.com/tacle/tacle-bench (TACLeBench) contains successors of these kernels under different names (`bsort`, `jfdctint`, `fir2dim`, `matrix1`, `isqrt`) with changed code; not interchangeable with the versions here.

## Citation and licensing

The upstream page carries no license text and asks only that publications using the benchmarks cite:

> J. Gustafsson, A. Betts, A. Ermedahl, B. Lisper, "The Mälardalen WCET Benchmarks: Past, Present and Future", Proc. 10th Int. Workshop on Worst-Case Execution Time Analysis (WCET), pp. 136-146, 2010. doi:10.4230/OASIcs.WCET.2010.136

The files are redistributed here unmodified, with their original headers, for reproducibility only. Individual kernels carry their own origin notes in the header comments (`sqrt.c` is marked public domain by SNU-RT; the others carry no explicit statement).
