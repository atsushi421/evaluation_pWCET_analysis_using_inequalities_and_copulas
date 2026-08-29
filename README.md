# pWCET Analysis using Inequalities and Copulas

Research code accompanying our work on probabilistic Worst-Case Execution Time (pWCET) estimation. This repository provides two complementary tools:

1. **Inequality-based pWCET estimation** of a single execution-time time series, using Markov's inequality with power-of-k under three different envelope functions ($f(x) = x^k$, $\arctan(x/d)^k$, $\tanh(x/d)^k$).
2. **Copula-based composition** of two units' pWCET distributions into a joint / summed pWCET distribution.

All source code lives under [`chb-cop-main/`](chb-cop-main/).

## Repository layout

```
chb-cop-main/
├── memik/                # Inequality-based estimation with f(x) = x^k
├── atan/                 # Inequality-based estimation with f(x) = arctan(x/d)^k
├── tanh/                 # Inequality-based estimation with f(x) = tanh(x/d)^k
├── benchmarks/
│   └── malardalen/       # Unmodified Mälardalen WCET kernels evaluated in the paper
├── chb_main.ipynb        # End-to-end example of inequality-based estimation
├── copulas.ipynb         # End-to-end example of copula-based composition
└── requirements.txt
```

## Setup

```bash
cd chb-cop-main
pip install -r requirements.txt
```

Dependencies: `numpy`, `scikit-learn`, `PyYAML`, `tqdm`, `pandas`, `vinecopulas`.

## Usage

### 1. Inequality-based pWCET estimation

Open and run [`chb-cop-main/chb_main.ipynb`](chb-cop-main/chb_main.ipynb).

**Inputs** (not included in this repository):

- `chb-cop-main/synthetic_samples/<dist>.npy` — a 1D `np.ndarray` of execution-time samples.
- `chb-cop-main/synthetic_ground_truth/<dist>.npy` — a pickled `dict[float, float]` mapping each exceedance probability to its ground-truth WCET (used to evaluate tightness; not needed for estimation itself).

**Outputs**:

- `chb-cop-main/synthetic_tightness_{memik,atan,tanh}/<dist>.yaml` — tightness ratio, predicted WCET, and the selected hyperparameters at each target exceedance probability.

The notebook runs all three envelope functions in turn. Each subdirectory (`memik/`, `atan/`, `tanh/`) implements the same pipeline:

1. Estimate the $k$-th moment of $f(X)$ from the samples.
2. Invert Markov's inequality $P(f(X) \ge \tau) \le E[f(X)^k] / \tau^k$ to predict a quantile.
3. Bootstrap to find, for each target probability $p$, the largest $k$ whose predicted quantile still upper-bounds the empirical quantile.
4. Linearly extrapolate $k$ from a small set of test probabilities to all target probabilities (in $\log_{10} p$ space).
5. Take the minimum envelope across $k$ (and across the bandwidth $d$ for atan / tanh) as the final pWCET prediction.

Bootstrap simulations are parallelised with `ProcessPoolExecutor`.

### 2. Copula-based composition

Open and run [`chb-cop-main/copulas.ipynb`](chb-cop-main/copulas.ipynb).

**Inputs** (not included in this repository):

- `chb-cop-main/sample/u0101.pkl`, `u0102.pkl` — pickled lists of per-unit execution-time samples.
- `chb-cop-main/pwcet/u0101.pkl`, `u0102.pkl` — pickled `dict[float, float]` of each unit's pWCET (e.g. the output of step 1 above).

**Pipeline**:

1. Convert the two time series to uniform-margin pseudo-observations.
2. Fit a vine copula (`vinecopulas.vinecopula.fit_vinecop`) over copula families 1–15 with structure `'R'`.
3. Draw $10^7$ joint $(u_1, u_2)$ samples from the fitted copula.
4. Map each marginal back to the execution-time scale via an inverse-CDF built from the per-unit pWCET dictionary.
5. Sum the two marginals and re-quantise at the requested exceedance probabilities to obtain the joint pWCET.

## Benchmark programs

[`chb-cop-main/benchmarks/malardalen/`](chb-cop-main/benchmarks/malardalen/) contains byte-identical copies of the five Mälardalen WCET kernels used in the paper's benchmark evaluation (`bsort100`, `fdct`, `fir`, `matmult`, `sqrt`), the upstream SWEET annotation file for `bsort100`, and a README recording their provenance (URLs, upstream revision, SHA-256), the paper-to-upstream name mapping, the compile flags (`gcc -O2 -fno-builtin`), each kernel's fixed input configuration, and mirror locations. The execution-time traces are not included.
