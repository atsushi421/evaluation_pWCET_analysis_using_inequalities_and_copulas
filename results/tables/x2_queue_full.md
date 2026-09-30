queue-full invocations 2839, median 2511 us, max 3542 us; windows 10

steady state: median 1777 us, reference at p = 0.0001 2976 us; per-run average of one pose update: steady state median 176 us (max 1670 us), queue full median 169 us (max 345 us)

### p = 0.0001

| method | estimate / normal reference | estimate / queue-full median | queue-full exceedance (median, max over windows) | windows with exceedance > p |
|---|---|---|---|---|
| E2E-CANTELLI | 7.21 [7.13, 7.37] | 8.55 [8.46, 8.73] | 0.00%, 0.00% | 0/10 |
| E2E-CHB | 1.08 [1.04, 1.17] | 1.28 [1.24, 1.39] | 0.49%, 0.67% | 10/10 |
| E2E-EVT-PoT | 0.98 [0.96, 1.06] | 1.17 [1.14, 1.26] | 3.10%, 4.83% | 10/10 |
| E2E-MEMIK | 1.08 [1.05, 1.17] | 1.29 [1.24, 1.39] | 0.42%, 0.67% | 10/10 |
| CHB-COMONO | 4.67 [3.64, 6.13] | 5.53 [4.31, 7.27] | 0.00%, 0.00% | 0/10 |
| CHB-IND | 2.63 [2.06, 3.83] | 3.11 [2.45, 4.54] | 0.00%, 0.00% | 0/10 |
| CHB-IND@max | 2.83 [2.10, 3.83] | 3.36 [2.49, 4.55] | 0.00%, 0.00% | 0/10 |

### p = 1e-05

| method | estimate / normal reference | estimate / queue-full median | queue-full exceedance (median, max over windows) | windows with exceedance > p |
|---|---|---|---|---|
| E2E-CANTELLI | 19.00 [18.78, 19.43] | 25.50 [25.20, 26.07] | 0.00%, 0.00% | 0/10 |
| E2E-CHB | 1.03 [0.96, 1.12] | 1.38 [1.28, 1.50] | 0.05%, 0.49% | 6/10 |
| E2E-EVT-PoT | 0.93 [0.85, 0.98] | 1.25 [1.15, 1.32] | 0.63%, 3.95% | 10/10 |
| E2E-MEMIK | 1.05 [0.95, 1.11] | 1.40 [1.28, 1.49] | 0.05%, 0.49% | 6/10 |
| CHB-COMONO | 6.36 [4.57, 8.82] | 8.53 [6.14, 11.84] | 0.00%, 0.00% | 0/10 |
| CHB-IND | 2.80 [2.00, 5.06] | 3.75 [2.68, 6.79] | 0.00%, 0.00% | 0/10 |
| CHB-IND@max | 2.90 [2.03, 5.08] | 3.90 [2.73, 6.81] | 0.00%, 0.00% | 0/10 |

