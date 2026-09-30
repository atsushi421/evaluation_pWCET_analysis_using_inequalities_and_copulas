# pWCET Analysis using Inequalities and Copulas

Research code accompanying our work on probabilistic Worst-Case Execution Time (pWCET) estimation (A. Yano, H. Toba, T. Azumi, "pWCET Estimation Based on Probabilistic Inequalities and Copulas Utilizing Static Analysis Information", IEEE Access, under review).

The evaluation of the revised paper runs on the pipeline in `estimation/`, `copula/`, `tools/`, and `results/` (see [Reproducing the evaluation](#reproducing-the-evaluation)). It compares ten estimators on the same instrumented runs. The five end-to-end estimators are E2E-EVT-BM, E2E-EVT-PoT, E2E-CANTELLI, E2E-MEMIK, and E2E-CHB (called E2E in the first submission). The five decomposed estimators are EVT-COP, MEMIK-COP, CHB-IND, CHB-COMONO, and CHB-COP, the proposed method.

The notebooks of the first submission are kept for reference. They provide two tools:

1. **Inequality-based pWCET estimation** of a single execution-time time series, using Markov's inequality with power-of-k under three different envelope functions ($f(x) = x^k$, $\arctan(x/d)^k$, $\tanh(x/d)^k$).
2. **Copula-based composition** of the units' pWCET distributions into a joint / summed pWCET distribution (`copula/`, generalizing the two-unit example in `copulas.ipynb`).

## Repository layout

```
.
├── estimation/           # Estimators of the revised evaluation (saturating Chebyshev and MEMIK bounds, EVT, KL certificate, composition tree)
├── tools/                # Job runner, per-benchmark estimation (chb_cop_from_schema.py), tables, figures, timing
├── results/              # Job files (results/jobs/), estimates, and the tables of the paper (results/tables/)
├── external/TailID/      # TailID threshold selection used by the EVT estimators (git submodule)
├── memik/                # First submission: inequality-based estimation with f(x) = x^k
├── atan/                 # First submission: inequality-based estimation with f(x) = arctan(x/d)^k
├── tanh/                 # First submission: inequality-based estimation with f(x) = tanh(x/d)^k
├── copula/               # Copula family pools, selection criteria, R-vines, MC composition (see copula/README.md)
├── benchmarks/
│   └── malardalen/       # Unmodified Mälardalen WCET kernels evaluated in the paper
├── ipoint/               # IPoint instrumentation toolkit and measurement harness (see ipoint/README.md)
├── chb_main.ipynb        # End-to-end example of inequality-based estimation
├── copulas.ipynb         # Two-unit example of copula-based composition (vinecopulas; superseded by copula/)
└── requirements.txt
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest copula/tests -q
```

Dependencies (pinned in `requirements.txt`): `numpy` 2, `scipy`, `scikit-learn`, `PyYAML`, `tqdm`, `pandas`, `matplotlib`, `pyvinecopulib` 0.7.6 (copula backend), `vinecopulas` 2.0.3 (only for `copulas.ipynb`). A virtual environment is recommended because a numpy 2 user installation breaks a distribution-provided scipy 1.8; `PYTEST_DISABLE_PLUGIN_AUTOLOAD` avoids the ROS 2 pytest plugins when a ROS environment is sourced.

## Usage

### 1. Inequality-based pWCET estimation

From the repository root, open and run [`chb_main.ipynb`](chb_main.ipynb) (the notebooks resolve their data directories relative to the working directory, so start Jupyter from the repository root).

**Inputs** (not included in this repository):

- `synthetic_samples/<dist>.npy` — a 1D `np.ndarray` of execution-time samples.
- `synthetic_ground_truth/<dist>.npy` — a pickled `dict[float, float]` mapping each exceedance probability to its ground-truth WCET (used to evaluate tightness; not needed for estimation itself).

**Outputs**:

- `synthetic_tightness_{memik,atan,tanh}/<dist>.yaml` — tightness ratio, predicted WCET, and the selected hyperparameters at each target exceedance probability.

The notebook runs all three envelope functions in turn. Each subdirectory (`memik/`, `atan/`, `tanh/`) implements the same pipeline:

1. Estimate the $k$-th moment of $f(X)$ from the samples.
2. Invert Markov's inequality $P(f(X) \ge \tau) \le E[f(X)^k] / \tau^k$ to predict a quantile.
3. Bootstrap to find, for each target probability $p$, the largest $k$ whose predicted quantile still upper-bounds the empirical quantile.
4. Linearly extrapolate $k$ from a small set of test probabilities to all target probabilities (in $\log_{10} p$ space).
5. Take the minimum envelope across $k$ (and across the bandwidth $d$ for atan / tanh) as the final pWCET prediction.

Bootstrap simulations are parallelised with `ProcessPoolExecutor`.

### 2. Copula-based composition

The `copula/` subpackage (see [`copula/README.md`](copula/README.md)) fits the pair copula or R-vine that couples the units and composes their distributions by Monte-Carlo:

```python
from copula import select, vine, compose
u = select.pseudo_obs(x)                                            # x: samples aligned per run, one column per unit
sel = select.select(u, pool="par", criterion="bic", indep_alpha=0.05)  # two units
fit = vine.fit_vine(u, pool="par", criterion="bic", indep_alpha=0.05)  # three or more units
res = compose.compose(sel.bicop, [icdf_a, icdf_b], exceed_probs=[1e-4, 1e-5, 1e-6], n_samples=int(1e8))
```

Candidate pools (`vc15`, `par`, `all`), the selection criteria (`loglik`, `aic`, `bic`, `mbic`, `cv`, `tcf`, `hybrid`) and the study that compares them (`copula/study_selection.py`, results in `copula/results/`) are documented there.

The original two-unit example is [`copulas.ipynb`](copulas.ipynb) (uses `vinecopulas`):

**Inputs** (not included in this repository):

- `sample/u0101.pkl`, `u0102.pkl` — pickled lists of per-unit execution-time samples.
- `pwcet/u0101.pkl`, `u0102.pkl` — pickled `dict[float, float]` of each unit's pWCET (e.g. the output of step 1 above).

**Pipeline**:

1. Convert the two time series to uniform-margin pseudo-observations.
2. Fit a vine copula (`vinecopulas.vinecopula.fit_vinecop`) over copula families 1–15 with structure `'R'`.
3. Draw $10^7$ joint $(u_1, u_2)$ samples from the fitted copula.
4. Map each marginal back to the execution-time scale via an inverse-CDF built from the per-unit pWCET dictionary.
5. Sum the two marginals and re-quantise at the requested exceedance probabilities to obtain the joint pWCET.

## Benchmark programs

[`benchmarks/malardalen/`](benchmarks/malardalen/) contains byte-identical copies of the twelve Mälardalen WCET kernels of the revised evaluation and of `fdct` and `sqrt` of the first submission, the upstream SWEET annotation file for `bsort100`, the size patches, and a README. The README records their provenance (URLs, upstream revision, SHA-256), the selection criteria, the compile flags (`gcc -O2 -fno-builtin`), the input configuration of each kernel, and mirror locations. The execution-time traces are not included.

## Collecting execution-time traces

[`ipoint/`](ipoint/) contains the instrumentation toolkit used to collect the per-unit traces: a libclang-based tool that decomposes a C source into basic units and inserts IPoints, a header-only probe (`rdtscp; lfence`), the harness for the Mälardalen kernels, and the scripts that turn the raw traces into the sample files expected by the estimators above. `ipoint/README.md` documents the workflow (`tools/run_campaign.py`), the trace formats and the measured probe cost.

## Reproducing the evaluation

The execution-time traces are not part of this repository. They are collected with `ipoint/` (`ipoint/tools/run_campaign.py` for the kernels and `ipoint/autoware/` for the Autoware callbacks) and are archived separately. The paper gives the DOI.

1. Estimate. `tools/run_jobs.sh <job file> [P]` runs the lines of a job file with `P` parallel processes. Each line is one call of `tools/chb_cop_from_schema.py`, and finished outputs are skipped, so a rerun resumes. The job files of the paper are `results/jobs/full_bench.txt` (12 kernels, 50 training windows each), `full_aw.txt` (Autoware callbacks), `full_fine.txt` (fine-grained `bsort100`), `full_n1e5.txt` (training windows of 10^5 runs), and `full_e25.txt` (fixed copula families).
2. Post-process. `results/jobs/full_post.sh bench|n1e5|fine|aw|e25|e214|cert|tables` merges the outputs into `results/estimates*/` and regenerates the tables in `results/tables/`.
   The two stress tests without new benchmark runs have their own scripts, and `full_post.sh x2|x3` regenerates their tables.
   - `tools/x2_queue_full.py` trains on the steady-state windows of the EKF callback (cb1) and compares with the replays whose measurement queue is full (`results/x2/x2_cb1.json`).
   - `tools/x3_mixing_sweep.py` mixes adversarial runs of `qsort-exam` and `select` into the training windows (`results/x3/x3_<kernel>.json`). With `--like <json>`, it recomputes the stored entries.
3. Read the tables. The main ones are the following.
   - `multiwindow.md` and `multiwindow_p1e-5.md` (benchmarks, all training windows) and `w0_p1e-4.md` to `w0_p1e-6.md` (window 0).
   - `autoware_multiwindow.md` and `autoware_w0_warm1.md` (Autoware callbacks, steady state).
   - `e214.md` (adversarial inputs), `x2_queue_full.md` (full measurement queue), `x3_mixing_qsort-exam.md` and `x3_mixing_select.md` (mixing-rate sweep), `e25_families.md` (fixed copula families), `certification.md` (finite-sample certificate), and `orderstat.md` (upper order statistics of training window 0 for comparison, from `tools/orderstat.py`).
   - `overhead.md` (probe effect), `coverage.md`, `tails.md`, `neff.md`, `neff_autoware.md`, and `refci.md` (intervals of the references).
   - `cost.md`, `cost_scope.md`, and `static_analysis_time.md` (analysis time).

Run the Python tools with `.venv/bin/python` (see Setup). The instrumenter in `ipoint/` and `tools/static_analysis_time.py` run with the system `python3`, because the instrumenter needs the libclang of llvm-14.
