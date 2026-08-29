# pWCET Analysis using Inequalities and Copulas

Research code accompanying our work on probabilistic Worst-Case Execution Time (pWCET) estimation. This repository provides two complementary tools:

1. **Inequality-based pWCET estimation** of a single execution-time time series, using Markov's inequality with power-of-k under three different envelope functions ($f(x) = x^k$, $\arctan(x/d)^k$, $\tanh(x/d)^k$).
2. **Copula-based composition** of the units' pWCET distributions into a joint / summed pWCET distribution (`copula/`, generalizing the two-unit example in `copulas.ipynb`).

## Repository layout

```
.
├── memik/                # Inequality-based estimation with f(x) = x^k
├── atan/                 # Inequality-based estimation with f(x) = arctan(x/d)^k
├── tanh/                 # Inequality-based estimation with f(x) = tanh(x/d)^k
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

[`benchmarks/malardalen/`](benchmarks/malardalen/) contains byte-identical copies of the five Mälardalen WCET kernels used in the paper's benchmark evaluation (`bsort100`, `fdct`, `fir`, `matmult`, `sqrt`), the upstream SWEET annotation file for `bsort100`, and a README recording their provenance (URLs, upstream revision, SHA-256), the paper-to-upstream name mapping, the compile flags (`gcc -O2 -fno-builtin`), each kernel's fixed input configuration, and mirror locations. The execution-time traces are not included.

## Collecting execution-time traces

[`ipoint/`](ipoint/) contains the instrumentation toolkit used to collect the per-unit traces: a libclang-based tool that decomposes a C source into basic units and inserts IPoints, a header-only probe (`rdtscp; lfence`), the harness for the Mälardalen kernels, and the scripts that turn the raw traces into the sample files expected by the estimators above. `ipoint/README.md` documents the workflow (`tools/run_campaign.py`), the trace formats and the measured probe cost.
