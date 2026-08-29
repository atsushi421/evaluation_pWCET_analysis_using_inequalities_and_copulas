# Copula pool x selection criterion study (synthetic)

scenarios: ['bb1', 'clayton180_t0.5', 'clayton_t0.5', 'frank_t0.5', 'gauss_t-0.4', 'gauss_t0.5', 'gumbel_t0.2', 'gumbel_t0.5', 'indep', 'joe_t0.5', 'mix_gauss_clayton180', 'mix_gauss_indep', 't3_t0.5', 'tawn']; replicates per scenario: 20; n = 10000

Composed quantiles are computed exactly by numerical integration of P(X+Y > t) over the copula
(trapezoidal rule on a 47k-point grid refined toward both ends, bisection in t); no Monte-Carlo noise.

Validation of the integration against a 1e8-sample Monte-Carlo truth (relative difference exact/MC - 1):

| scenario | p=1e-3 | p=1e-4 | p=1e-5 | p=1e-6 (MC has ~100 exceedances) |
|---|---|---|---|---|
| bb1 | +0.0011 | +0.0027 | +0.0020 | -0.0005 |
| clayton180_t0.5 | +0.0011 | +0.0019 | +0.0023 | +0.0053 |
| clayton_t0.5 | +0.0008 | +0.0007 | +0.0031 | +0.0027 |
| frank_t0.5 | +0.0008 | +0.0013 | +0.0020 | -0.0005 |
| gauss_t-0.4 | +0.0009 | +0.0001 | +0.0063 | +0.0020 |
| gauss_t0.5 | +0.0009 | +0.0024 | +0.0054 | +0.0109 |
| gumbel_t0.2 | +0.0012 | +0.0028 | +0.0015 | -0.0016 |
| gumbel_t0.5 | +0.0013 | +0.0020 | +0.0046 | +0.0033 |
| indep | +0.0007 | +0.0004 | +0.0035 | +0.0008 |
| joe_t0.5 | +0.0011 | +0.0015 | +0.0024 | +0.0068 |
| mix_gauss_clayton180 | +0.0010 | -0.0040 | -0.0134 | -0.0270 |
| mix_gauss_indep | +0.0009 | -0.0045 | -0.0065 | -0.0342 |
| t3_t0.5 | +0.0011 | +0.0031 | +0.0004 | -0.0035 |
| tawn | +0.0010 | +0.0024 | +0.0009 | +0.0013 |

Metrics per (pool, pretest, criterion), averaged over scenarios and replicates:
`recover` = share of data sets whose winner has the true family and rotation (scenarios whose truth is in the pool);
`|dlamU|` = mean absolute error of the upper-tail dependence coefficient; `oos_gap` = mean per-observation
out-of-sample log-likelihood deficit against the true copula; `mre_p` = mean relative error of the
composed quantile at exceedance probability p; `min_p` = worst relative error (negative = underestimation);
`unsafe_p` = share of data sets with relative error below -5%.

| pool | pretest | criterion | recover | \|dlamU\| | oos_gap | mre_1e-4 | min_1e-4 | unsafe_1e-4 | mre_1e-5 | min_1e-5 | unsafe_1e-5 | mre_1e-6 | min_1e-6 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vc15 | 0 | loglik | 0.99 | 0.045 | 0.0076 | 0.007 | -0.031 | 0.00 | 0.008 | -0.030 | 0.00 | 0.008 | -0.028 |
| vc15 | 1 | loglik | 0.98 | 0.045 | 0.0076 | 0.007 | -0.031 | 0.00 | 0.008 | -0.030 | 0.00 | 0.008 | -0.028 |
| vc15 | 0 | aic | 0.99 | 0.045 | 0.0076 | 0.007 | -0.031 | 0.00 | 0.008 | -0.030 | 0.00 | 0.008 | -0.028 |
| vc15 | 1 | aic | 0.98 | 0.045 | 0.0076 | 0.007 | -0.031 | 0.00 | 0.008 | -0.030 | 0.00 | 0.008 | -0.028 |
| vc15 | 0 | bic | 0.99 | 0.045 | 0.0076 | 0.008 | -0.031 | 0.00 | 0.008 | -0.030 | 0.00 | 0.008 | -0.028 |
| vc15 | 1 | bic | 0.98 | 0.045 | 0.0076 | 0.007 | -0.031 | 0.00 | 0.008 | -0.030 | 0.00 | 0.008 | -0.028 |
| vc15 | 0 | mbic | 0.99 | 0.045 | 0.0076 | 0.008 | -0.031 | 0.00 | 0.008 | -0.030 | 0.00 | 0.008 | -0.028 |
| vc15 | 1 | mbic | 0.98 | 0.045 | 0.0076 | 0.007 | -0.031 | 0.00 | 0.008 | -0.030 | 0.00 | 0.008 | -0.028 |
| vc15 | 0 | cv | 0.98 | 0.045 | 0.0076 | 0.007 | -0.031 | 0.00 | 0.008 | -0.030 | 0.00 | 0.008 | -0.028 |
| vc15 | 1 | cv | 0.97 | 0.045 | 0.0076 | 0.007 | -0.031 | 0.00 | 0.008 | -0.030 | 0.00 | 0.008 | -0.028 |
| vc15 | 0 | tcf | 0.79 | 0.044 | 0.0085 | 0.006 | -0.031 | 0.00 | 0.006 | -0.030 | 0.00 | 0.007 | -0.028 |
| vc15 | 1 | tcf | 0.81 | 0.044 | 0.0085 | 0.005 | -0.031 | 0.00 | 0.006 | -0.030 | 0.00 | 0.007 | -0.028 |
| vc15 | 0 | hybrid | 0.97 | 0.045 | 0.0076 | 0.007 | -0.031 | 0.00 | 0.008 | -0.030 | 0.00 | 0.008 | -0.028 |
| vc15 | 1 | hybrid | 0.96 | 0.045 | 0.0076 | 0.007 | -0.031 | 0.00 | 0.008 | -0.030 | 0.00 | 0.008 | -0.028 |
| par | 0 | loglik | 0.61 | 0.043 | 0.0018 | 0.008 | -0.030 | 0.00 | 0.009 | -0.080 | 0.01 | 0.028 | -0.106 |
| par | 1 | loglik | 0.68 | 0.043 | 0.0018 | 0.008 | -0.030 | 0.00 | 0.009 | -0.080 | 0.01 | 0.028 | -0.106 |
| par | 0 | aic | 0.87 | 0.038 | 0.0018 | 0.008 | -0.021 | 0.00 | 0.009 | -0.071 | 0.01 | 0.011 | -0.101 |
| par | 1 | aic | 0.90 | 0.038 | 0.0018 | 0.008 | -0.021 | 0.00 | 0.009 | -0.071 | 0.01 | 0.011 | -0.101 |
| par | 0 | bic | 0.99 | 0.032 | 0.0017 | 0.008 | -0.006 | 0.00 | 0.009 | -0.005 | 0.00 | 0.009 | -0.004 |
| par | 1 | bic | 0.99 | 0.032 | 0.0017 | 0.008 | -0.006 | 0.00 | 0.009 | -0.005 | 0.00 | 0.009 | -0.004 |
| par | 0 | mbic | 0.97 | 0.032 | 0.0017 | 0.008 | -0.006 | 0.00 | 0.009 | -0.005 | 0.00 | 0.009 | -0.004 |
| par | 1 | mbic | 0.99 | 0.032 | 0.0017 | 0.008 | -0.006 | 0.00 | 0.009 | -0.005 | 0.00 | 0.009 | -0.004 |
| par | 0 | cv | 0.80 | 0.038 | 0.0018 | 0.008 | -0.021 | 0.00 | 0.009 | -0.071 | 0.01 | 0.011 | -0.101 |
| par | 1 | cv | 0.84 | 0.038 | 0.0018 | 0.008 | -0.021 | 0.00 | 0.009 | -0.071 | 0.01 | 0.011 | -0.101 |
| par | 0 | tcf | 0.40 | 0.042 | 0.0093 | 0.007 | -0.082 | 0.00 | 0.008 | -0.105 | 0.00 | 0.014 | -0.110 |
| par | 1 | tcf | 0.46 | 0.042 | 0.0092 | 0.007 | -0.082 | 0.00 | 0.008 | -0.105 | 0.00 | 0.014 | -0.110 |
| par | 0 | hybrid | 0.62 | 0.049 | 0.0018 | 0.008 | -0.030 | 0.00 | 0.009 | -0.080 | 0.00 | 0.015 | -0.106 |
| par | 1 | hybrid | 0.68 | 0.049 | 0.0018 | 0.008 | -0.030 | 0.00 | 0.009 | -0.080 | 0.00 | 0.015 | -0.106 |
| all | 0 | loglik | 0.03 | 0.221 | 0.0049 | -0.037 | -0.094 | 0.47 | -0.057 | -0.120 | 0.60 | -0.047 | -0.128 |
| all | 1 | loglik | 0.11 | 0.221 | 0.0047 | -0.037 | -0.094 | 0.47 | -0.057 | -0.120 | 0.60 | -0.047 | -0.128 |
| all | 0 | aic | 0.87 | 0.040 | 0.0010 | 0.000 | -0.076 | 0.03 | -0.001 | -0.085 | 0.07 | 0.000 | -0.101 |
| all | 1 | aic | 0.90 | 0.040 | 0.0010 | -0.000 | -0.076 | 0.03 | -0.001 | -0.085 | 0.07 | 0.000 | -0.101 |
| all | 0 | bic | 0.99 | 0.032 | 0.0017 | 0.008 | -0.006 | 0.00 | 0.009 | -0.005 | 0.00 | 0.009 | -0.004 |
| all | 1 | bic | 0.99 | 0.032 | 0.0017 | 0.008 | -0.006 | 0.00 | 0.009 | -0.005 | 0.00 | 0.009 | -0.004 |
| all | 0 | mbic | 0.97 | 0.032 | 0.0017 | 0.008 | -0.006 | 0.00 | 0.009 | -0.005 | 0.00 | 0.009 | -0.004 |
| all | 1 | mbic | 0.99 | 0.032 | 0.0017 | 0.008 | -0.006 | 0.00 | 0.009 | -0.005 | 0.00 | 0.009 | -0.004 |
| all | 0 | cv | 0.80 | 0.028 | 0.0009 | -0.005 | -0.076 | 0.04 | -0.007 | -0.085 | 0.10 | -0.005 | -0.101 |
| all | 1 | cv | 0.84 | 0.028 | 0.0009 | -0.005 | -0.076 | 0.04 | -0.007 | -0.085 | 0.10 | -0.005 | -0.101 |
| all | 0 | tcf | 0.24 | 0.045 | 0.0086 | -0.000 | -0.094 | 0.04 | -0.002 | -0.119 | 0.09 | 0.004 | -0.126 |
| all | 1 | tcf | 0.30 | 0.045 | 0.0085 | -0.000 | -0.094 | 0.04 | -0.002 | -0.119 | 0.09 | 0.004 | -0.126 |
| all | 0 | hybrid | 0.62 | 0.049 | 0.0018 | 0.008 | -0.030 | 0.00 | 0.009 | -0.080 | 0.00 | 0.015 | -0.106 |
| all | 1 | hybrid | 0.68 | 0.049 | 0.0018 | 0.008 | -0.030 | 0.00 | 0.009 | -0.080 | 0.00 | 0.015 | -0.106 |

## Per scenario, pool `par`, no pretest: winner shares and relative error at p = 1e-5

### indep (true indep, lambda_U = 0.000, true q(1e-5) = 72.48)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | bb8180 (20%), bb890 (15%), bb8270 (10%), bb8 (10%), joe90 (5%), bb7180 (5%), gaussian (5%), clayton90 (5%), joe270 (5%), bb6180 (5%), bb1 (5%), clayton180 (5%), joe (5%) | 0.000 | +0.001 | +0.001 | -0.002 |
| aic | indep (45%), joe90 (10%), frank (10%), clayton180 (10%), clayton (5%), joe270 (5%), joe180 (5%), gaussian (5%), gumbel180 (5%) | 0.000 | +0.000 | +0.000 | -0.002 |
| bic | indep (100%) | 0.000 | +0.000 | +0.000 | +0.000 |
| mbic | indep (80%), joe270 (5%), gaussian (5%), joe90 (5%), gumbel180 (5%) | 0.000 | +0.000 | +0.000 | -0.002 |
| cv | indep (35%), clayton180 (10%), frank (10%), gumbel180 (10%), clayton (5%), bb8270 (5%), bb790 (5%), joe270 (5%), gaussian (5%), bb7 (5%), joe90 (5%) | 0.000 | +0.000 | +0.000 | -0.002 |
| tcf | indep (20%), student (15%), joe (15%), gaussian (10%), bb7 (10%), bb790 (5%), clayton270 (5%), bb6 (5%), bb7270 (5%), bb8180 (5%), frank (5%) | 0.001 | +0.002 | +0.002 | -0.002 |
| hybrid | indep (30%), joe (20%), frank (15%), gaussian (10%), gumbel (10%), clayton270 (5%), clayton90 (5%), joe180 (5%) | 0.002 | +0.002 | +0.002 | -0.001 |

### gauss_t0.5 (true gaussian, lambda_U = 0.000, true q(1e-5) = 81.28)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | gaussian (100%) | 0.000 | +0.001 | +0.001 | -0.004 |
| aic | gaussian (100%) | 0.000 | +0.001 | +0.001 | -0.004 |
| bic | gaussian (100%) | 0.000 | +0.001 | +0.001 | -0.004 |
| mbic | gaussian (100%) | 0.000 | +0.001 | +0.001 | -0.004 |
| cv | gaussian (100%) | 0.000 | +0.001 | +0.001 | -0.004 |
| tcf | gaussian (85%), student (15%) | 0.001 | +0.002 | +0.002 | -0.004 |
| hybrid | gaussian (100%) | 0.000 | +0.001 | +0.001 | -0.004 |

### gauss_t-0.4 (true gaussian, lambda_U = 0.000, true q(1e-5) = 71.36)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | gaussian (95%), student (5%) | 0.000 | -0.000 | -0.000 | -0.000 |
| aic | gaussian (100%) | 0.000 | -0.000 | -0.000 | -0.000 |
| bic | gaussian (100%) | 0.000 | -0.000 | -0.000 | -0.000 |
| mbic | gaussian (100%) | 0.000 | -0.000 | -0.000 | -0.000 |
| cv | gaussian (90%), student (10%) | 0.000 | -0.000 | -0.000 | -0.000 |
| tcf | gaussian (80%), student (20%) | 0.000 | -0.000 | -0.000 | -0.000 |
| hybrid | gaussian (100%) | 0.000 | -0.000 | -0.000 | -0.000 |

### t3_t0.5 (true student, lambda_U = 0.454, true q(1e-5) = 87.67)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | student (100%) | 0.456 | +0.000 | +0.000 | -0.001 |
| aic | student (100%) | 0.456 | +0.000 | +0.000 | -0.001 |
| bic | student (100%) | 0.456 | +0.000 | +0.000 | -0.001 |
| mbic | student (100%) | 0.456 | +0.000 | +0.000 | -0.001 |
| cv | student (100%) | 0.456 | +0.000 | +0.000 | -0.001 |
| tcf | student (50%), bb1 (25%), bb1180 (15%), bb7180 (10%) | 0.455 | +0.004 | +0.003 | -0.001 |
| hybrid | student (100%) | 0.456 | +0.000 | +0.000 | -0.001 |

### gumbel_t0.5 (true gumbel, lambda_U = 0.586, true q(1e-5) = 89.45)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | bb6 (45%), tawn (30%), bb1 (25%) | 0.588 | +0.000 | +0.000 | -0.003 |
| aic | gumbel (75%), bb6 (15%), bb1 (10%) | 0.586 | +0.000 | +0.000 | -0.003 |
| bic | gumbel (95%), bb1 (5%) | 0.585 | -0.000 | -0.000 | -0.003 |
| mbic | gumbel (95%), bb1 (5%) | 0.585 | -0.000 | -0.000 | -0.003 |
| cv | bb6 (40%), gumbel (35%), bb1 (25%) | 0.587 | +0.000 | +0.000 | -0.003 |
| tcf | bb6 (45%), bb1 (35%), bb1180 (10%), tawn (10%) | 0.590 | +0.001 | +0.000 | -0.003 |
| hybrid | bb6 (55%), bb1 (35%), gumbel (10%) | 0.588 | +0.000 | +0.000 | -0.003 |

### gumbel_t0.2 (true gumbel, lambda_U = 0.259, true q(1e-5) = 84.59)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | bb6 (55%), bb1 (35%), gumbel (5%), bb7 (5%) | 0.265 | +0.002 | +0.002 | -0.005 |
| aic | gumbel (75%), bb6 (10%), bb1 (10%), bb7 (5%) | 0.263 | +0.001 | +0.001 | -0.005 |
| bic | gumbel (100%) | 0.259 | +0.000 | +0.000 | -0.003 |
| mbic | gumbel (100%) | 0.259 | +0.000 | +0.000 | -0.003 |
| cv | gumbel (75%), bb1 (15%), bb6 (10%) | 0.259 | +0.000 | +0.000 | -0.005 |
| tcf | bb6 (20%), tawn (20%), bb7180 (15%), clayton180 (15%), bb1180 (10%), bb1 (10%), bb8 (5%), bb7 (5%) | 0.228 | -0.008 | -0.010 | -0.105 |
| hybrid | bb6 (40%), gumbel (30%), bb1 (25%), bb1180 (5%) | 0.258 | +0.000 | +0.000 | -0.018 |

### clayton180_t0.5 (true clayton180, lambda_U = 0.707, true q(1e-5) = 90.27)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | clayton180 (50%), bb1180 (20%), bb7180 (15%), bb6 (10%), bb7 (5%) | 0.708 | -0.000 | +0.000 | -0.001 |
| aic | clayton180 (90%), bb6 (5%), bb7 (5%) | 0.708 | -0.000 | +0.000 | -0.001 |
| bic | clayton180 (95%), joe (5%) | 0.708 | +0.000 | +0.000 | -0.001 |
| mbic | clayton180 (95%), joe (5%) | 0.708 | +0.000 | +0.000 | -0.001 |
| cv | clayton180 (80%), bb6 (10%), bb7180 (10%) | 0.707 | -0.000 | -0.000 | -0.001 |
| tcf | bb1180 (50%), bb6 (25%), bb7180 (10%), joe (5%), bb7 (5%), bb8 (5%) | 0.674 | +0.000 | +0.000 | -0.001 |
| hybrid | bb1180 (50%), bb7180 (25%), clayton180 (10%), bb7 (5%), joe (5%), bb6 (5%) | 0.708 | +0.000 | +0.000 | -0.001 |

### clayton_t0.5 (true clayton, lambda_U = 0.000, true q(1e-5) = 73.31)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | clayton (55%), bb7 (20%), bb1 (15%), bb8180 (5%), bb6180 (5%) | 0.003 | +0.003 | +0.003 | -0.001 |
| aic | clayton (90%), bb1 (5%), bb6180 (5%) | 0.001 | +0.001 | +0.001 | -0.000 |
| bic | clayton (100%) | 0.000 | +0.000 | +0.000 | -0.000 |
| mbic | clayton (100%) | 0.000 | +0.000 | +0.000 | -0.000 |
| cv | clayton (80%), bb7 (10%), bb1 (5%), bb6180 (5%) | 0.001 | +0.001 | +0.001 | -0.000 |
| tcf | clayton (30%), bb6180 (15%), joe180 (15%), bb1 (15%), bb7180 (10%), bb8180 (10%), bb7 (5%) | 0.001 | +0.002 | +0.002 | -0.001 |
| hybrid | clayton (45%), bb1 (20%), bb7 (15%), bb6180 (10%), joe180 (5%), bb8180 (5%) | 0.001 | +0.001 | +0.001 | -0.001 |

### joe_t0.5 (true joe, lambda_U = 0.725, true q(1e-5) = 90.33)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | bb7 (30%), bb6 (25%), joe (25%), bb8 (20%) | 0.580 | -0.003 | -0.007 | -0.080 |
| aic | joe (65%), bb6 (15%), bb8 (10%), bb7 (10%) | 0.652 | -0.002 | -0.006 | -0.071 |
| bic | joe (100%) | 0.726 | +0.000 | +0.000 | -0.000 |
| mbic | joe (100%) | 0.726 | +0.000 | +0.000 | -0.000 |
| cv | joe (60%), bb6 (15%), bb7 (15%), bb8 (10%) | 0.652 | -0.002 | -0.006 | -0.071 |
| tcf | joe (30%), bb8 (20%), bb6 (20%), bb7180 (10%), bb1180 (10%), clayton180 (5%), bb7 (5%) | 0.577 | -0.000 | +0.001 | -0.001 |
| hybrid | bb8 (30%), joe (30%), bb6 (30%), clayton180 (5%), bb7 (5%) | 0.507 | -0.002 | -0.003 | -0.080 |

### frank_t0.5 (true frank, lambda_U = 0.000, true q(1e-5) = 73.84)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | frank (100%) | 0.000 | +0.000 | +0.000 | -0.000 |
| aic | frank (100%) | 0.000 | +0.000 | +0.000 | -0.000 |
| bic | frank (100%) | 0.000 | +0.000 | +0.000 | -0.000 |
| mbic | frank (100%) | 0.000 | +0.000 | +0.000 | -0.000 |
| cv | frank (100%) | 0.000 | +0.000 | +0.000 | -0.000 |
| tcf | frank (85%), tawn180 (5%), bb8 (5%), bb6180 (5%) | 0.000 | +0.004 | +0.003 | -0.000 |
| hybrid | frank (100%) | 0.000 | +0.000 | +0.000 | -0.000 |

### bb1 (true bb1, lambda_U = 0.413, true q(1e-5) = 87.56)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | bb1 (100%) | 0.412 | -0.000 | -0.000 | -0.005 |
| aic | bb1 (100%) | 0.412 | -0.000 | -0.000 | -0.005 |
| bic | bb1 (100%) | 0.412 | -0.000 | -0.000 | -0.005 |
| mbic | bb1 (100%) | 0.412 | -0.000 | -0.000 | -0.005 |
| cv | bb1 (100%) | 0.412 | -0.000 | -0.000 | -0.005 |
| tcf | bb1 (75%), bb7180 (10%), bb1180 (10%), student (5%) | 0.398 | -0.002 | -0.002 | -0.023 |
| hybrid | bb1 (95%), bb1180 (5%) | 0.407 | -0.001 | -0.001 | -0.013 |

### tawn (true tawn, lambda_U = 0.451, true q(1e-5) = 87.50)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | tawn (100%) | 0.450 | -0.000 | -0.000 | -0.003 |
| aic | tawn (100%) | 0.450 | -0.000 | -0.000 | -0.003 |
| bic | tawn (100%) | 0.450 | -0.000 | -0.000 | -0.003 |
| mbic | tawn (100%) | 0.450 | -0.000 | -0.000 | -0.003 |
| cv | tawn (100%) | 0.450 | -0.000 | -0.000 | -0.003 |
| tcf | bb1180 (40%), bb7180 (30%), tawn (20%), bb6 (5%), bb1 (5%) | 0.449 | +0.008 | +0.007 | -0.003 |
| hybrid | tawn (100%) | 0.450 | -0.000 | -0.000 | -0.003 |

### mix_gauss_indep (true mixture, lambda_U = 0.000, true q(1e-5) = 79.03)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | student (100%) | 0.217 | +0.046 | +0.054 | +0.048 |
| aic | student (100%) | 0.217 | +0.046 | +0.054 | +0.048 |
| bic | student (100%) | 0.217 | +0.046 | +0.054 | +0.048 |
| mbic | student (100%) | 0.217 | +0.046 | +0.054 | +0.048 |
| cv | student (100%) | 0.217 | +0.046 | +0.054 | +0.048 |
| tcf | bb1180 (50%), bb7180 (45%), student (5%) | 0.135 | +0.032 | +0.040 | +0.017 |
| hybrid | student (100%) | 0.217 | +0.046 | +0.054 | +0.048 |

### mix_gauss_clayton180 (true mixture, lambda_U = 0.252, true q(1e-5) = 82.06)

| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |
|---|---|---|---|---|---|
| loglik | bb1 (100%) | 0.446 | +0.069 | +0.072 | +0.070 |
| aic | bb1 (100%) | 0.446 | +0.069 | +0.072 | +0.070 |
| bic | bb1 (100%) | 0.446 | +0.069 | +0.072 | +0.070 |
| mbic | bb1 (100%) | 0.446 | +0.069 | +0.072 | +0.070 |
| cv | bb1 (100%) | 0.446 | +0.069 | +0.072 | +0.070 |
| tcf | bb1180 (100%) | 0.391 | +0.063 | +0.067 | +0.063 |
| hybrid | bb1 (100%) | 0.446 | +0.069 | +0.072 | +0.070 |

## Cost

mean seconds per data set: fit all candidates of pool `all` 8.02, cross-validation + tail statistics 30.03, one exact composition 1.72
