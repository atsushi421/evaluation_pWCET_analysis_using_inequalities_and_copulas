# Values of the paper without another table

## Common windows of the copula-based methods (02 §2)

The 400 windows where CHB-COP, MEMIK-COP and EVT-COP have an estimate (windows 0-49 of seven kernels, 0-9 of the five R-vine kernels). Per method: unsafe windows (tightness < 1) / windows with an estimate (E2E-EVT-BM counts only the windows where a block size was accepted), median, and 10 % and 90 % points (numpy linear) of the tightness. 'training max' is the largest run of the training window after the SMI exclusion of the reference, over the reference. Sources: results/estimates/*.json, ipoint/traces_full/*/parsed.

| method | unsafe 1e-4 | median 1e-4 | 10 % point 1e-4 | 90 % point 1e-4 | unsafe 1e-5 | median 1e-5 |
|---|---|---|---|---|---|---|
| E2E-CHB | 22/400 | 1.030 | 1.007 | 1.101 | 251/400 | 0.960 |
| E2E-MEMIK | 16/400 | 1.086 | 1.018 | 1.121 | 145/400 | 1.047 |
| E2E-CANTELLI | 0/400 | 2.373 | 1.605 | 15.767 | 0/400 | 5.133 |
| E2E-EVT-PoT | 186/400 | 1.001 | 0.976 | 3.435 | 291/400 | 0.938 |
| E2E-EVT-BM | 54/93 | 0.998 | 0.951 | 1.012 | 86/93 | 0.948 |
| EVT-COP | 135/400 | 1.009 | 0.988 | 4.718 | 274/400 | 0.945 |
| MEMIK-COP | 9/400 | 1.087 | 1.027 | 1.185 | 116/400 | 1.054 |
| CHB-IND | 16/400 | 1.040 | 1.007 | 1.140 | 233/400 | 0.976 |
| CHB-COMONO | 10/400 | 1.059 | 1.009 | 1.272 | 197/400 | 1.004 |
| CHB-COP | 16/400 | 1.042 | 1.007 | 1.141 | 225/400 | 0.980 |
| training max | 127/400 | 1.007 | 0.990 | 1.084 | 362/400 | 0.929 |

CHB-COP vs E2E-MEMIK on these windows at p = 1e-4:

| A vs B | windows | A only | B only | McNemar p | median A/B | Wilcoxon p |
|---|---|---|---|---|---|---|
| CHB-COP vs E2E-MEMIK | 400 | 4 | 4 | 1 | 0.990 | 2.2e-15 |

Training-window maximum over all 600 windows (the IID expectation is the probability that none of the n training runs reaches the reference quantile, averaged over the windows):

| p | unsafe windows | unsafe % [95 % Clopper-Pearson] | IID expectation (1-p)^n % |
|---|---|---|---|
| 0.0001 | 194/600 | 32.3 [28.6, 36.2] | 36.8 |
| 1e-05 | 547/600 | 91.2 [88.6, 93.3] | 90.5 |
| 1e-06 | 596/600 | 99.3 [98.3, 99.8] | 99.0 |

10 % and 90 % points over all windows of each method (600, 400 for the copula-based methods):

| method | windows | 10 % point 1e-4 | 90 % point 1e-4 |
|---|---|---|---|
| E2E-CHB | 600 | 1.007 | 1.122 |
| E2E-MEMIK | 600 | 1.019 | 1.143 |
| E2E-CANTELLI | 600 | 1.574 | 10.588 |
| E2E-EVT-PoT | 600 | 0.970 | 5.291 |
| E2E-EVT-BM | 98 | 0.954 | 1.011 |
| EVT-COP | 400 | 0.988 | 4.718 |
| MEMIK-COP | 400 | 1.027 | 1.185 |
| CHB-IND | 600 | 1.009 | 1.244 |
| CHB-COMONO | 600 | 1.011 | 1.692 |
| CHB-COP | 400 | 1.007 | 1.141 |


## Paired comparisons (02 §2)

Windows unsafe for one method only, exact McNemar test, median tightness ratio and Wilcoxon test (as in multiwindow.md) at p = 1e-4 on the common windows; the kernels are grouped by the number of parts of the root of their composition tree (CHB-COP meta). Sources: results/estimates/*.json.

| A vs B | windows | A only | B only | McNemar p | median A/B | Wilcoxon p |
|---|---|---|---|---|---|---|
| CHB-COMONO vs CHB-COP | 400 | 0 | 6 | 0.031 | 1.001 | 4.1e-59 |
| > 2 parts (5 kernels): CHB-COP vs E2E-CHB | 50 | 0 | 4 | 0.12 | 1.076 | 1.8e-15 |
| <= 2 parts (7 kernels): CHB-COP vs E2E-CHB | 350 | 0 | 2 | 0.5 | 1.000 | 2.7e-11 |

Windows unsafe for one method only:

| bench | window | CHB-COMONO | CHB-COP | CHB-COMONO/CHB-COP |
|---|---|---|---|---|
| bsort100 | 49 | 1.0097 | 0.9976 | 1.012 |
| matmult | 38 | 1.1725 | 0.9874 | 1.187 |
| matmult | 8 | 1.0005 | 0.9947 | 1.006 |
| select | 33 | 1.1729 | 0.9974 | 1.176 |
| select | 41 | 1.1220 | 0.9955 | 1.127 |
| select | 9 | 1.1075 | 0.9834 | 1.126 |

| bench | window | CHB-COP | E2E-CHB | CHB-COP/E2E-CHB |
|---|---|---|---|---|
| bsort100 | 15 | 1.0011 | 0.9945 | 1.007 |
| bsort100 | 43 | 1.0001 | 0.9994 | 1.001 |
| edn | 3 | 1.0862 | 0.9714 | 1.118 |
| edn | 4 | 1.1970 | 0.9675 | 1.237 |
| edn | 6 | 1.3405 | 0.9903 | 1.354 |
| st | 3 | 1.1325 | 0.9960 | 1.137 |

CHB-COP / E2E-CHB per window at p = 1e-4:

| bench | root parts | windows | median | min | max |
|---|---|---|---|---|---|
| bsort100 | 2 | 50 | 1.000 | 0.999 | 1.007 |
| fir | 2 | 50 | 1.001 | 0.999 | 1.006 |
| matmult | 2 | 50 | 1.000 | 0.994 | 1.019 |
| edn | 3 | 10 | 1.162 | 1.052 | 1.354 |
| ndes | 4 | 10 | 1.099 | 1.040 | 1.203 |
| st | 5 | 10 | 1.144 | 1.073 | 1.181 |
| lms | 3 | 10 | 1.014 | 1.009 | 1.025 |
| prime | 1 | 50 | 0.998 | 0.974 | 1.023 |
| cnt | 2 | 50 | 1.000 | 0.993 | 1.004 |
| ludcmp | 5 | 10 | 1.049 | 1.023 | 1.065 |
| select | 2 | 50 | 1.000 | 0.998 | 1.034 |
| qsort-exam | 2 | 50 | 1.000 | 0.993 | 1.001 |
| pooled <= 2 parts (bsort100, fir, matmult, prime, cnt, select, qsort-exam) |  | 350 | 1.000 | 0.974 | 1.034 |


## Dependence effect (02 §2)

Per kernel over the common windows at p = 1e-4: CHB-COMONO/CHB-COP (the window of the maximum in brackets) and the relative difference CHB-COP/CHB-IND - 1 in % (window 0, minimum and maximum; the pooled row is over all 400 windows). Sources: results/estimates/*.json.

| bench | root parts | windows | COMONO/COP median | min | max | COP/IND-1 % w0 | min | max |
|---|---|---|---|---|---|---|---|---|
| bsort100 | 2 | 50 | 1.00 | 1.00 | 1.15 (w15) | +0.0 | +0.0 | +0.0 (w25) |
| fir | 2 | 50 | 1.00 | 1.00 | 1.10 (w5) | +0.0 | +0.0 | +0.4 (w40) |
| matmult | 2 | 50 | 1.00 | 1.00 | 1.27 (w35) | +0.0 | +0.0 | +0.1 (w35) |
| edn | 3 | 10 | 1.37 | 1.19 | 1.50 (w7) | +1.6 | -0.4 | +5.6 (w9) |
| ndes | 4 | 10 | 1.44 | 1.22 | 1.62 (w7) | -0.1 | -0.3 | +3.3 (w9) |
| st | 5 | 10 | 1.31 | 1.19 | 1.35 (w8) | +3.6 | +0.6 | +3.6 (w0) |
| lms | 3 | 10 | 1.06 | 1.03 | 1.07 (w8) | +0.0 | -0.0 | +0.0 (w3) |
| prime | 1 | 50 | 1.00 | 1.00 | 1.00 (w0) | +0.0 | +0.0 | +0.0 (w0) |
| cnt | 2 | 50 | 1.00 | 1.00 | 1.04 (w17) | +0.0 | +0.0 | +0.4 (w36) |
| ludcmp | 5 | 10 | 1.06 | 1.04 | 1.12 (w1) | -0.3 | -0.3 | +3.4 (w9) |
| select | 2 | 50 | 1.00 | 1.00 | 1.18 (w33) | +0.0 | +0.0 | +0.0 (w9) |
| qsort-exam | 2 | 50 | 1.00 | 1.00 | 1.04 (w8) | +0.0 | +0.0 | +0.0 (w29) |
| pooled |  |  |  |  |  |  | -0.4 (edn w7) | +5.6 (edn w9) |

Two-part kernels pooled (300 windows): CHB-COMONO/CHB-COP median 1.001, max 1.267 (matmult w35).

ndes windows 0-9: mean tightness CHB-COMONO 1.812, CHB-COP 1.258; ratio per window 1.22-1.62 (median 1.44); CHB-COMONO mean over all 50 windows 1.838.

st in the extrapolation region (CHB-IND over its 50 windows):

| p | CHB-IND unsafe | CHB-IND min | CHB-IND unsafe in w0-9 | CHB-IND w4 | CHB-COP w4 | CHB-COP unsafe (w0-9) | CHB-COMONO unsafe |
|---|---|---|---|---|---|---|---|
| 1e-05 | 7/50 | 0.987 | 4 | 0.997 | 1.053 | 0/10 | 0/50 |
| 1e-06 | 14/50 | 0.950 | 4 | 0.981 | 1.056 | 0/10 | 0/50 |


## cb7 marker loop (02 §3.1)

Loop `NDTScanMatcher::publish_marker.L1` of cb7 (steady state, every invocation, window 0 for the bound). Loop time: the interval of the loop unit (iterations and loop control); 'iterations only' sums the iteration bodies, which is what the rule bounds. The bound is recomputed with tree.loop_marginal and the production seed, and its (d, k) equals the stored CHB-COP meta. Sources: ipoint/autoware/traces/autoware/bench_warm1/cb7, results/estimates_autoware_warm1/cb7.json.

| value | cb7 |
|---|---|
| median iteration time, iterations 1-8 (us) | 2.48, 1.50, 1.03, 0.33, 1.12, 0.50, 0.37, 0.37 |
| iterations per invocation (all invocations), static bound | 2-8 (106554 invocations), bound 31 |
| Algorithm 1 bound on the per-run average at 1e-4, window 0 (d, k) | 126.7 us (d = 120405, k = 3) |
| window-0 maximum of the per-run average; bound / maximum | 74.5 us; 1.70 |
| run of that maximum: iterations, first iteration | run 3461: 4, 295.2 us |
| loop rule value (bound x Algorithm 1 bound) | 3.93 ms |
| 1e-4 quantile of the loop time over all invocations; rule / quantile (iterations only) | 0.264 ms; 14.9 (0.261 ms; 15.0) |
| callback reference at 1e-4; rule / reference | 92.46 ms; 4.2 % |
| iterations above 100 us (of them the first or second) | 32 (26) |
| loop time / callback time, median over invocations (iterations only) | 0.027 % (0.025 %) |


## E2-14: iteration times of the killer and random inputs (02 §4.1)

Per-run average iteration time in ns, median (max), and iterations per run, median (min-max), over the SMI-censored runs (killer: all runs; random: training windows 0 and 1). Unit bound: Algorithm 1 at 1e-4 on the per-run average of the window (tree.loop_marginal, production seed); 'bound / killer' divides it by the killer's median per-run average. Killer/random E2E: medians of all SMI-censored runs. Sources: results/e214/{rand,killer,select_rand,select_killer}.

| kernel | input | runs | per-run average ns | iterations per run | unit bound 1e-4 ns | bound / killer | killer / random E2E median |
|---|---|---|---|---|---|---|---|
| qsort-exam | killer | 2000 | 306.6 (325.9) | 993 (993-993) |  |  | 2.32 |
| qsort-exam | random w0 | 10000 | 349.3 (392.1) | 379 (351-411) | 392.4 | 1.28 |  |
| qsort-exam | random w1 | 9998 | 349.2 (384.6) | 381 (345-417) | 385.1 | 1.26 |  |
| select | killer | 2000 | 652.5 (714.9) | 252 (252-252) |  |  | 8.45 |
| select | random w0 | 10000 | 1794.6 (4135.4) | 11 (2-19) | 4942.2 | 7.57 |  |
| select | random w1 | 9999 | 1798.1 (4222.3) | 11 (2-21) | 4871.5 | 7.47 |  |

Cantelli break check at p = 1e-4: the killer median exceeds the Cantelli plug-in bound (mean + SD sqrt((1-p)/p) of the training window) iff killer median / mean > 1 + CV sqrt((1-p)/p):

| kernel | window | killer median / window mean | 1 + CV sqrt((1-p)/p) |
|---|---|---|---|
| qsort-exam | 0 | 2.320 | 2.529 |
| qsort-exam | 1 | 2.319 | 2.541 |
| select | 0 | 8.529 | 15.200 |
| select | 1 | 8.553 | 15.587 |


## X2: per-window exceedance of the queue-full invocations (02 §4.2)

Share of the 2839 queue-full cb1 invocations (pose loop at its bound 5) above the estimate of each training window (10 windows), minimum, median and maximum over the windows, as in tools/x2_summary.py (resolution 0.035 %). Sources: results/x2/x2_cb1.json, ipoint/autoware/traces/x2_queuefull/bench_warm1.

| method | p = 1e-4 | p = 1e-5 |
|---|---|---|
| E2E-CANTELLI | 0.00%, 0.00%, 0.00% | 0.00%, 0.00%, 0.00% |
| E2E-CHB | 0.07%, 0.49%, 0.67% | 0.00%, 0.05%, 0.49% |
| E2E-EVT-PoT | 0.60%, 3.10%, 4.83% | 0.25%, 0.63%, 3.95% |
| E2E-MEMIK | 0.07%, 0.42%, 0.67% | 0.00%, 0.05%, 0.49% |
| CHB-COMONO | 0.00%, 0.00%, 0.00% | 0.00%, 0.00%, 0.00% |
| CHB-IND | 0.00%, 0.00%, 0.00% | 0.00%, 0.00%, 0.00% |
| CHB-IND@max | 0.00%, 0.00%, 0.00% | 0.00%, 0.00%, 0.00% |


## Fine bsort100: loop rules (02 §5)

CHB-COP@max / CHB-COP (per-run slowest iteration vs per-run average rule) per window. Source: results/estimates_fine/bsort100.json.

| p | windows | median | min-max |
|---|---|---|---|
| 0.0001 | 10 | 20.9 | 17.8-26.2 |
| 1e-05 | 10 | 22.4 | 20.0-44.6 |
| 1e-06 | 10 | 23.4 | 19.0-47.1 |


## Repeated calls (02 §1)

c times the (1-p)-quantile of one call against the (1-p)-quantile of the per-run total of the c calls, p = 0.001, empirical quantiles (method 'higher', as the references) over all runs that call the function (benchmarks SMI-censored), in us. Sources: ipoint/autoware/traces/autoware/bench_warm1/cb4, ipoint/traces_full/st.

| program | function | runs | calls per run | one call | c x one call | per-run total | ratio |
|---|---|---|---|---|---|---|---|
| cb4 | `Controller::publishProcessingTime` | 335112 | 2-2 | 40.200 | 80.400 | 112.283 | 0.72 |
| st | `Calc_Var_Stddev` | 9999938 | 2-2 | 2.096 | 4.193 | 6.133 | 0.68 |


## Autoware tails (02 §9)

Same columns and definitions as tails.md (tools/tables.py tail_stats): quantile at 1-p over the median (when p*n >= 9), excess kurtosis, GPD shape above the 0.99 quantile; all steady-state invocations, no SMI censoring for Autoware. Source: ipoint/autoware/traces/autoware/bench_warm1.

| callback | series | n | q1e-3/med | q1e-4/med | q1e-5/med | q1e-6/med | ex. kurtosis | xi(0.99) |
|---|---|---|---|---|---|---|---|---|
| cb1 | E2E (steady state) | 538150 | 1.482 | 1.675 | - | - | 5.3 | 0.06 |
| cb2 | E2E (steady state) | 537681 | 1.961 | 3.092 | - | - | 10.9 | 0.22 |
| cb3 | E2E (steady state) | 538033 | 4.053 | 6.392 | - | - | 616.4 | 0.23 |
| cb4 | E2E (steady state) | 335112 | 1.202 | 1.241 | - | - | -1.1 | 0.13 |
| cb5 | E2E (steady state) | 129879 | 3.003 | 4.035 | - | - | 46.4 | -0.14 |
| cb6 | E2E (steady state) | 99948 | 1.583 | 2.554 | - | - | 223.7 | 0.47 |
| cb7 | E2E (steady state) | 106554 | 2.955 | 3.988 | - | - | 6.5 | -0.17 |


## Autoware analysis time of CHB-COP (02 §9)

Field `seconds` of the CHB-COP entry, window 0, one core. Source: results/estimates_autoware_warm1/*.json.

| callback | CHB-COP seconds |
|---|---|
| cb1 | 3990 |
| cb2 | 82 |
| cb3 | 15 |
| cb4 | 12715 |
| cb5 | 1279 |
| cb6 | 2067 |
| cb7 | 2042 |

