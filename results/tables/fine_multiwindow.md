Unsafe windows (tightness < 1) / windows with an estimate, 1 benchmarks, windows per benchmark 10-10; 95 % Clopper-Pearson interval of the unsafe rate in %; median tightness.

| method | p=0.0001 | p=1e-05 | p=1e-06 |
|---|---|---|---|
| E2E-CHB | 0/10 [0.0, 30.8] med 1.026 | 6/10 [26.2, 87.8] med 0.971 | 9/10 [55.5, 99.7] med 0.911 |
| E2E-MEMIK | 0/10 [0.0, 30.8] med 1.044 | 5/10 [18.7, 81.3] med 1.002 | 9/10 [55.5, 99.7] med 0.965 |
| E2E-CANTELLI | 0/10 [0.0, 30.8] med 4.439 | 0/10 [0.0, 30.8] med 11.324 | 0/10 [0.0, 30.8] med 31.654 |
| E2E-EVT-PoT | 7/10 [34.8, 93.3] med 0.987 | 9/10 [55.5, 99.7] med 0.952 | 10/10 [69.2, 100.0] med 0.882 |
| E2E-EVT-BM | 1/3 [0.8, 90.6] med 1.018 | 1/3 [0.8, 90.6] med 1.037 | 1/3 [0.8, 90.6] med 1.096 |
| EVT-COP | 0/10 [0.0, 30.8] med 1.124 | 0/10 [0.0, 30.8] med 1.044 | 8/10 [44.4, 97.5] med 0.977 |
| MEMIK-COP | 0/10 [0.0, 30.8] med 1.265 | 0/10 [0.0, 30.8] med 1.200 | 0/10 [0.0, 30.8] med 1.189 |
| CHB-IND | 0/10 [0.0, 30.8] med 1.191 | 0/10 [0.0, 30.8] med 1.135 | 0/10 [0.0, 30.8] med 1.080 |
| CHB-COMONO | 0/10 [0.0, 30.8] med 1.328 | 0/10 [0.0, 30.8] med 1.288 | 0/10 [0.0, 30.8] med 1.231 |
| CHB-COP | 0/10 [0.0, 30.8] med 1.170 | 0/10 [0.0, 30.8] med 1.111 | 0/10 [0.0, 30.8] med 1.055 |
| CHB-IND@inst | 0/10 [0.0, 30.8] med 6.922 | 0/10 [0.0, 30.8] med 16.296 | 0/10 [0.0, 30.8] med 24.656 |
| CHB-COP@inst | 0/10 [0.0, 30.8] med 6.778 | 0/10 [0.0, 30.8] med 16.481 | 0/10 [0.0, 30.8] med 35.024 |

Tightness at p=0.0001: mean, SD, [min, max] over windows, unsafe windows.

| bench | E2E-CHB | E2E-MEMIK | E2E-CANTELLI | E2E-EVT-PoT | E2E-EVT-BM | EVT-COP | MEMIK-COP | CHB-IND | CHB-COMONO | CHB-COP | CHB-IND@inst | CHB-COP@inst |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bsort100 | 1.037±0.036 [1.001,1.100] 0/10 | 1.048±0.028 [1.016,1.098] 0/10 | 4.445±0.034 [4.408,4.524] 0/10 | 0.995±0.018 [0.978,1.037] 7/10 | 1.008±0.030 [0.975,1.032] 1/3 | 1.130±0.041 [1.103,1.241] 0/10 | 1.289±0.072 [1.187,1.407] 0/10 | 1.210±0.048 [1.165,1.307] 0/10 | 1.341±0.081 [1.257,1.515] 0/10 | 1.193±0.049 [1.153,1.303] 0/10 | 6.961±0.390 [6.405,7.612] 0/10 | 6.768±0.422 [6.012,7.478] 0/10 |

Paired comparison at p=0.0001 over the windows where both methods have an estimate: windows unsafe for A only and for B only, exact McNemar p-value, median tightness ratio A/B and Wilcoxon signed-rank p-value of the log ratios.

| A vs B | windows | A only | B only | McNemar p | median A/B | Wilcoxon p |
|---|---|---|---|---|---|---|
| CHB-COP vs E2E-CHB | 10 | 0 | 0 | 1 | 1.147 | 0.002 |
| CHB-COP vs CHB-COP@inst | 10 | 0 | 0 | 1 | 0.179 | 0.002 |
