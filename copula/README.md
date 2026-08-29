# `copula/`: dependence modeling for CHB-COP

Fits the copula that couples the basic units of a timing schema and composes
the unit-level distributions into a program-level one by Monte-Carlo. It
replaces the two-unit, hard-coded `copulas.ipynb` (kept for reference) and is
the place where the candidate-family pool and the family-selection criterion
of the paper (Section IV.C.1) are defined and evaluated.

Backend: [pyvinecopulib](https://github.com/vinecopulib/pyvinecopulib) 0.7.6
(Python bindings of vinecopulib, the C++ engine behind the R package
`rvinecopulib`). The earlier implementation used `vinecopulas` 2.0.3, whose
family set is only Gaussian, Student-t, Frank and the four rotations of
Gumbel, Clayton and Joe (15 families, AIC, no independence, no BB families);
that set is kept here as the pool `vc15` for comparison.

## Layout

| file | content |
|---|---|
| `families.py` | candidate pools (`vc15`, `par`, `all`), rotation preselection by the sign of Kendall's tau, analytic lower/upper tail-dependence coefficients of every family (Joe 2014), numeric tail concentration from the CDF |
| `select.py` | fits every candidate once, evaluates all criteria (`loglik`, `aic`, `bic`, `mbic`, `cv`, `tcf`, `hybrid`), Kendall's tau independence test, `select()` for one pair |
| `vine.py` | Dissmann's tree-wise maximum-spanning-tree R-vine construction with `select()` on every edge, conversion to a `pyvinecopulib.Vinecop` (verified by a log-likelihood identity), native pyvinecopulib fit for comparison |
| `compose.py` | chunked Monte-Carlo composition (sum or max) through a fitted copula or the independence / comonotonic / countermonotonic couplings; exact bivariate composition by numerical integration (`exact_sum_quantiles`); (inverse) CDFs from pWCET dictionaries or samples |
| `study_selection.py` | experiment E2-5: pools x criteria on synthetic copulas with known tails (`synthetic`) and on measured unit traces (`traces`) |
| `tests/` | pytest suite (tail coefficients, argument swapping, selection, vine vs. native, composition) |
| `results/` | outputs of `study_selection.py` (`synthetic_truth.json`, `synthetic_rows.csv`, `synthetic_summary.md`) |

## Environment

The system Python of this machine has numpy 2 in the user site together with
the distribution's scipy 1.8, which is binary-incompatible with numpy 2
(`scipy.stats` fails to import). Use the virtual environment:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest copula/tests -q   # ROS 2 registers pytest plugins that need lark
```

## Usage (from the repository root)

```python
import numpy as np
from copula import select, vine, compose

x = np.column_stack([samples_unit_a, samples_unit_b])      # aligned per run
u = select.pseudo_obs(x)                                   # rank transform, ties averaged
sel = select.select(u, pool="par", criterion="bic", indep_alpha=0.05)
sel.label, sel.tau, sel.indep_pvalue, [c.as_dict() for c in sel.candidates]

U = select.pseudo_obs(np.column_stack([s1, s2, s3]))       # three or more units: R-vine
fit = vine.fit_vine(U, pool="par", criterion="bic", indep_alpha=0.05)
fit.edges()                                                # tree, conditioned/conditioning sets, family, tau, lambda_U

icdfs = [compose.icdf_from_pwcet_dict(pwcet_a), compose.icdf_from_pwcet_dict(pwcet_b)]
res = compose.compose(sel.bicop, icdfs, exceed_probs=[1e-4, 1e-5, 1e-6], n_samples=int(1e8))
res.quantiles                                              # {p: quantile of the sum at 1 - p}
compose.exact_sum_quantiles(sel.bicop, cdf_a, icdf_a, cdf_b, icdf_b, [1e-5])   # two units: no MC noise
compose.compose("comono", icdfs, [1e-5])                   # comonotonic (upper bracket)
compose.compose("indep", icdfs, [1e-5])                    # independence (lower bracket)
```

## Candidate pools

| pool | families | rotations |
|---|---|---|
| `vc15` | Gaussian, Student-t, Frank, Gumbel, Clayton, Joe | 0/90/180/270 for Gumbel, Clayton, Joe (15 candidates, as in `vinecopulas` 2.0.3) |
| `par` | independence, Gaussian, Student-t, Clayton, Gumbel, Frank, Joe, BB1, BB6, BB7, BB8, Tawn | 0/90/180/270 for the Archimedean, BB and Tawn families (37 candidates) |
| `all` | `par` + TLL (transformation local-likelihood, nonparametric) | as `par` (38 candidates) |

Rotation preselection: with Kendall's tau >= 0 only rotations 0 and 180 are
fitted, otherwise 90 and 270 (Dissmann et al. 2013), which halves the cost.
Upper-tail dependence (lambda_U > 0): Student-t, Gumbel, Joe, BB1, BB6, BB7,
Tawn, BB8 (only for delta = 1) and the 180-degree rotation of Clayton.

## Selection criteria

All candidates are fitted once by maximum likelihood (pyvinecopulib); every
criterion is evaluated on the same fits.

| criterion | definition | reference |
|---|---|---|
| `loglik` | maximum log-likelihood | - |
| `aic` | 2k - 2 loglik | Akaike 1974 |
| `bic` | k ln n - 2 loglik | Schwarz 1978 |
| `mbic` | BIC with a prior probability psi0 = 0.9 of non-independence (the pair-level term of mBICV) | Nagler, Bumann, Czado 2019 |
| `cv` | 5-fold out-of-sample log-likelihood | cross-validation copula information criterion, Gronneberg & Hjort 2014; Jordanger & Tjostheim 2014 |
| `tcf` | tail-concentration fit: sum over q in {0.90, 0.95, 0.98, 0.99, 0.995} of (p_hat(q) - p(q))^2 / Var, with p(q) = 1 - 2q + C(q, q) (model) and p_hat(q) the empirical share of pairs with both pseudo-observations above q (Wald-type, upper tail only) | diagnostic in the spirit of the tail-weighted measures of Krupskii & Joe 2015 |
| `hybrid` | smallest `tcf` among the candidates whose BIC is within 10 of the best BIC | - |

Independence: the pool `par`/`all` contains the independence copula as a
candidate; in addition `indep_alpha` applies Kendall's tau asymptotic
independence test first (as VineCopula's `BiCopIndTest`), which is the only
route to independence for the pool `vc15`.

## Study `study_selection.py`

```bash
.venv/bin/python -m copula.study_selection synthetic --n 10000 --reps 20 --n-mc 2e7 --n-truth 1e8 --workers 12
.venv/bin/python -m copula.study_selection traces --parsed-dir traces/bsort100/parsed --units <uid_a> <uid_b> --train 10000
```

Synthetic scenarios (n = 10^4 pseudo-observations per data set, 20
replicates): independence; Gaussian (tau 0.5 and -0.4); Student-t (nu = 3);
Gumbel (tau 0.5 and 0.2); Clayton 180 (upper tail) and Clayton 0 (lower tail
only); Joe; Frank; BB1; Tawn (asymmetric); and two mixtures that no candidate
matches (Gaussian + independence, Gaussian + Clayton 180). For every data set
the largest pool is fitted once and the winner of every (pool, pretest,
criterion) is recorded with its lambda_U, its out-of-sample log-likelihood on
10^5 fresh observations and the quantiles at p = 10^-3 ... 10^-6 of X + Y
(lognormal marginals, sigma = 1.0 and 0.7), compared with the truth from the
true copula. Both are computed exactly by numerical integration
(`compose.exact_sum_quantiles`: P(X+Y > t) = 1 - F1(t) + int [1 - h1(u, F2(t - F1^{-1}(u)))] du
on a 47k-point grid refined toward both ends, then bisection in t), which
agrees with a 10^8-sample Monte-Carlo truth within 0.1-0.5 % at p >= 10^-5
(`results/synthetic_truth_mc1e8.json`, table in the summary). The marginals
are the true ones, so the error isolates the copula choice.
Results: `results/synthetic_summary.md` (aggregate and per-scenario tables)
and `results/synthetic_rows.csv`.

The `traces` mode aligns unit samples by run index (per-run totals for
multi-instance units), fits on the first `--train` runs, uses the empirical
quantile functions of all runs as marginals and compares the composed sum
with the empirical sum quantiles of all runs (tightness).

## Results (2026-08-30) and decision

`results/synthetic_summary.md` (generated) and the decision tables in the
paper repository (`notes/copula_selection/`) summarize the run
`synthetic --n 10000 --reps 20 --cv-folds 5` (280 data sets). Pool `par`,
independence pretest on, 240 data sets whose generating family is in the pool
(relative error of the composed quantile, negative = underestimation):

| criterion | true family recovered | mean abs error of lambda_U | worst error p=1e-5 | worst error p=1e-6 | share below -5 % |
|---|---|---|---|---|---|
| bic | 99.2 % | 0.003 | -0.5 % | -0.4 % | 0 % |
| mbic | 98.8 % | 0.003 | -0.5 % | -0.4 % | 0 % |
| aic | 90.4 % | 0.010 | -7.1 % | -10.1 % | 0.8 % |
| cv (5-fold) | 84.2 % | 0.010 | -7.1 % | -10.1 % | 0.8 % |
| loglik | 68.3 % | 0.016 | -8.0 % | -10.7 % | 1.3 % |
| tcf | 46.3 % | 0.026 | -10.5 % | -11.0 % | 0.4 % |
| hybrid | 68.3 % | 0.023 | -8.0 % | -10.7 % | 0.4 % |

Pool `vc15` (the old 15 families) underestimates the quantile by 2 to 3 %
when the true dependence is BB1-like; pool `all` never selects TLL under BIC,
but the likelihood-based criteria select it and then underestimate by 5 to
12 %. For the two misspecified mixtures every parametric selection
overestimates by 5 to 8 %. Decision: pool `par`, criterion `bic`
(`mbicv` in vines), Kendall's tau pretest at 0.05; TLL excluded.

## Notes

- `vinecopulas.pseudodata` maps ranks to `(rank - 1) / (n - 1)`, so the
  smallest and largest observations become exactly 0 and 1; pyvinecopulib's
  `to_pseudo_obs` uses `rank / (n + 1)`. Execution-time traces contain many
  ties (integer ticks); ties are averaged by default (`ties_method`), which
  biases rank-based estimates toward independence when ties are heavy
  (Li et al. 2020). pyvinecopulib can fit discrete margins (`var_types`) if
  this matters for very short units.
- pyvinecopulib seeds must be below 2^31; `compose` reduces them modulo 2^31 - 1.
- Simulation cost: about 3.5 s per 10^7 bivariate samples of a one-parameter
  family, 1 s per 10^6 samples of a 4-dimensional vine; Tawn and BB copulas
  simulate at about 10^5 samples/s and TLL at 1.7 x 10^4 samples/s, so use
  `exact_sum_quantiles` for two units and reserve Monte-Carlo for vines.
