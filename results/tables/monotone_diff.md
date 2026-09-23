# Monotone-curve recompute vs stored estimates

Jobs without JSON: 0

Compared entries: 798 (bench, window, method); 2394 values.

## Relative change new/old - 1 (all stored sets)

| method | p | n | changed | median | p90 | max | min |
|---|---|---|---|---|---|---|---|
| E2E-CHB | 0.0001 | 133 | 0 | +0.00% | +0.00% | +0.00% | +0.00% |
| E2E-CHB | 1e-05 | 133 | 34 | +0.00% | +0.54% | +1.75% | +0.00% |
| E2E-CHB | 1e-06 | 133 | 14 | +0.00% | +0.04% | +3.63% | +0.00% |
| E2E-MEMIK | 0.0001 | 133 | 0 | +0.00% | +0.00% | +0.00% | +0.00% |
| E2E-MEMIK | 1e-05 | 133 | 9 | +0.00% | +0.00% | +3.27% | +0.00% |
| E2E-MEMIK | 1e-06 | 133 | 2 | +0.00% | +0.00% | +0.87% | +0.00% |
| CHB-COP | 0.0001 | 133 | 40 | +0.00% | +0.00% | +0.32% | -1.89% |
| CHB-COP | 1e-05 | 133 | 61 | +0.00% | +0.27% | +5.42% | -9.84% |
| CHB-COP | 1e-06 | 133 | 53 | +0.00% | +1.02% | +9.14% | -16.68% |
| CHB-IND | 0.0001 | 133 | 41 | +0.00% | +0.00% | +0.31% | -0.17% |
| CHB-IND | 1e-05 | 133 | 60 | +0.00% | +0.40% | +5.42% | -9.84% |
| CHB-IND | 1e-06 | 133 | 52 | +0.00% | +0.90% | +9.11% | -16.70% |
| CHB-COMONO | 0.0001 | 133 | 0 | +0.00% | +0.00% | +0.00% | +0.00% |
| CHB-COMONO | 1e-05 | 133 | 37 | +0.00% | +0.17% | +0.61% | +0.00% |
| CHB-COMONO | 1e-06 | 133 | 32 | +0.00% | +0.12% | +9.72% | +0.00% |
| MEMIK-COP | 0.0001 | 133 | 53 | +0.00% | +0.00% | +0.12% | -71.51% |
| MEMIK-COP | 1e-05 | 133 | 54 | +0.00% | +0.05% | +0.98% | -69.26% |
| MEMIK-COP | 1e-06 | 133 | 46 | +0.00% | +0.00% | +0.35% | -99.88% |

## Unsafe windows (tightness < 1) over window 0 + windows 1..9, 12 kernels

| method | p | old | new |
|---|---|---|---|
| E2E-CHB | 0.0001 | 10 | 10 | (n=120)
| E2E-CHB | 1e-05 | 83 | 83 | (n=120)
| E2E-CHB | 1e-06 | 101 | 101 | (n=120)
| E2E-MEMIK | 0.0001 | 1 | 1 | (n=120)
| E2E-MEMIK | 1e-05 | 28 | 28 | (n=120)
| E2E-MEMIK | 1e-06 | 68 | 68 | (n=120)
| CHB-COP | 0.0001 | 9 | 9 | (n=120)
| CHB-COP | 1e-05 | 81 | 78 | (n=120)
| CHB-COP | 1e-06 | 97 | 96 | (n=120)
| CHB-IND | 0.0001 | 9 | 9 | (n=120)
| CHB-IND | 1e-05 | 84 | 80 | (n=120)
| CHB-IND | 1e-06 | 98 | 98 | (n=120)
| CHB-COMONO | 0.0001 | 7 | 7 | (n=120)
| CHB-COMONO | 1e-05 | 58 | 58 | (n=120)
| CHB-COMONO | 1e-06 | 76 | 76 | (n=120)
| MEMIK-COP | 0.0001 | 0 | 1 | (n=120)
| MEMIK-COP | 1e-05 | 21 | 23 | (n=120)
| MEMIK-COP | 1e-06 | 45 | 50 | (n=120)

## estimates_n1e5: old -> new

| bench | method | p=1e-4 | p=1e-5 | p=1e-6 |
|---|---|---|---|---|
| bsort100 | E2E-CHB | 1.045 | 1.022 | 0.880 |
| bsort100 | E2E-MEMIK | 1.050 | 1.021 | 0.881 |
| bsort100 | CHB-COP | 1.045 | 1.012 -> 1.022 | 0.880 |
| bsort100 | CHB-IND | 1.045 | 1.012 -> 1.022 | 0.880 |
| bsort100 | CHB-COMONO | 1.050 | 1.130 | 0.971 |
| bsort100 | MEMIK-COP | 1.056 -> 1.056 | 1.038 -> 1.038 | 3201.592 -> 5.730 |
| cnt | E2E-CHB | 1.048 | 0.985 | 0.975 |
| cnt | E2E-MEMIK | 1.096 | 1.050 | 1.061 |
| cnt | CHB-COP | 1.049 | 0.988 | 0.983 |
| cnt | CHB-IND | 1.048 | 0.985 | 0.975 |
| cnt | CHB-COMONO | 1.049 | 1.016 | 1.006 |
| cnt | MEMIK-COP | 1.101 -> 1.101 | 1.062 -> 1.060 | 1470.614 -> 2.485 |
| edn | E2E-CHB | 1.120 | 1.066 | 0.815 |
| edn | E2E-MEMIK | 1.120 | 1.087 | 0.823 |
| edn | CHB-COP | 1.120 | 1.066 | 0.820 |
| edn | CHB-IND | 1.120 | 1.066 | 0.820 |
| edn | CHB-COMONO | 1.120 | 1.066 | 0.820 |
| edn | MEMIK-COP | 1.120 | 1.087 | 0.823 |
| fir | E2E-CHB | 1.107 | 1.036 | 1.011 |
| fir | E2E-MEMIK | 1.115 | 1.035 | 1.013 |
| fir | CHB-COP | 1.108 -> 1.108 | 1.037 -> 1.036 | 1.182 -> 0.985 |
| fir | CHB-IND | 1.108 -> 1.108 | 1.037 -> 1.036 | 1.182 -> 0.985 |
| fir | CHB-COMONO | 1.114 | 1.139 | 1.166 |
| fir | MEMIK-COP | 1.120 | 1.043 | 3.112 |
| lms | E2E-CHB | 1.092 | 1.052 | 1.049 |
| lms | E2E-MEMIK | 1.109 | 1.079 | 1.092 |
| lms | CHB-COP | 1.098 -> 1.098 | 1.051 -> 1.051 | 1.050 |
| lms | CHB-IND | 1.098 -> 1.097 | 1.051 -> 1.051 | 1.049 |
| lms | CHB-COMONO | 1.149 | 1.121 | 1.155 |
| lms | MEMIK-COP | 1.104 | 1.066 | 1.118 |
| ludcmp | E2E-CHB | 1.088 | 1.022 | 1.001 |
| ludcmp | E2E-MEMIK | 1.100 | 1.051 | 1.053 |
| ludcmp | CHB-COP | 1.099 -> 1.099 | 1.055 -> 1.056 | 1.060 -> 1.066 |
| ludcmp | CHB-IND | 1.091 -> 1.091 | 1.043 | 1.054 -> 1.065 |
| ludcmp | CHB-COMONO | 1.210 | 1.267 | 1.350 |
| ludcmp | MEMIK-COP | 1.132 -> 1.132 | 1.099 -> 1.101 | 767.558 -> 767.644 |
| matmult | E2E-CHB | 1.065 | 1.007 | 0.749 |
| matmult | E2E-MEMIK | 1.084 | 1.070 | 0.767 |
| matmult | CHB-COP | 1.065 | 1.007 | 0.713 -> 0.758 |
| matmult | CHB-IND | 1.065 | 1.007 | 0.713 -> 0.758 |
| matmult | CHB-COMONO | 1.071 | 1.148 | 0.859 |
| matmult | MEMIK-COP | 1.090 | 1.074 | 5.301 |
| ndes | E2E-CHB | 1.205 | 1.100 | 0.837 |
| ndes | E2E-MEMIK | 1.200 | 1.215 | 0.833 |
| ndes | CHB-COP | 1.234 -> 1.231 | 1.194 -> 1.192 | 0.884 -> 0.889 |
| ndes | CHB-IND | 1.219 -> 1.218 | 1.128 -> 1.127 | 0.793 -> 0.865 |
| ndes | CHB-COMONO | 1.821 | 1.927 | 1.396 |
| ndes | MEMIK-COP | 1.362 -> 1.362 | 1.403 -> 1.405 | 1.516 -> 1.521 |
| prime | E2E-CHB | 1.042 | 1.036 -> 1.044 | 1.024 -> 1.029 |
| prime | E2E-MEMIK | 1.053 | 1.091 | 1.106 |
| prime | CHB-COP | 1.038 | 1.031 | 1.024 |
| prime | CHB-IND | 1.038 | 1.031 | 1.024 |
| prime | CHB-COMONO | 1.038 | 1.031 | 1.024 |
| prime | MEMIK-COP | 1.146 | 1.077 | 1.106 |
| qsort-exam | E2E-CHB | 1.069 | 1.014 | 1.005 |
| qsort-exam | E2E-MEMIK | 1.090 | 1.052 | 1.069 |
| qsort-exam | CHB-COP | 1.071 -> 1.069 | 1.125 -> 1.014 | 1.098 -> 1.005 |
| qsort-exam | CHB-IND | 1.071 -> 1.069 | 1.125 -> 1.014 | 1.098 -> 1.005 |
| qsort-exam | CHB-COMONO | 1.072 | 1.046 | 1.032 -> 1.037 |
| qsort-exam | MEMIK-COP | 1.091 | 1.055 | 2.063 |
| select | E2E-CHB | 1.072 | 1.030 | 0.896 |
| select | E2E-MEMIK | 1.072 | 1.041 | 0.896 |
| select | CHB-COP | 1.073 -> 1.073 | 1.043 | 0.897 -> 0.897 |
| select | CHB-IND | 1.073 | 1.043 | 0.896 -> 0.896 |
| select | CHB-COMONO | 1.077 | 1.152 | 1.020 |
| select | MEMIK-COP | 1.078 -> 1.079 | 1.060 -> 1.061 | 3128.504 -> 5.574 |
| st | E2E-CHB | 1.180 | 1.179 | 1.042 |
| st | E2E-MEMIK | 1.203 | 1.178 | 1.044 |
| st | CHB-COP | 1.180 | 1.179 | 1.003 |
| st | CHB-IND | 1.180 | 1.179 | 1.003 |
| st | CHB-COMONO | 1.180 | 1.179 | 1.003 |
| st | MEMIK-COP | 1.203 | 1.178 | 1.044 |

## estimates_fine: old -> new

| bench | method | p=1e-4 | p=1e-5 | p=1e-6 |
|---|---|---|---|---|
| bsort100 | E2E-CHB | 1.017 | 0.942 | 0.894 |
| bsort100 | E2E-MEMIK | 1.044 | 0.987 | 0.950 |
| bsort100 | CHB-COP | 6.650 -> 6.614 | 14.689 -> 14.528 | 23.166 -> 23.187 |
| bsort100 | CHB-IND | 6.583 -> 6.582 | 12.148 | 17.650 -> 17.650 |
| bsort100 | CHB-COMONO | 4.223 | 20.305 | 30.949 |
| bsort100 | MEMIK-COP | 11.738 -> 11.734 | 19.385 -> 19.565 | 669549.611 -> 669596.647 |

## Largest relative changes

| set | bench | window | method | p | old | new | change |
|---|---|---|---|---|---|---|---|
| estimates_multiwindow | fir | 7 | MEMIK-COP | 1e-06 | 2859.507 | 3.424 | -99.9% |
| estimates_multiwindow | matmult | 4 | MEMIK-COP | 1e-06 | 4463.802 | 5.538 | -99.9% |
| estimates_multiwindow | bsort100 | 8 | MEMIK-COP | 1e-06 | 3175.217 | 4.259 | -99.9% |
| estimates_n1e5 | cnt | 0 | MEMIK-COP | 1e-06 | 1470.614 | 2.485 | -99.8% |
| estimates_multiwindow | cnt | 1 | MEMIK-COP | 1e-06 | 1473.087 | 2.509 | -99.8% |
| estimates_multiwindow | cnt | 5 | MEMIK-COP | 1e-06 | 1472.998 | 2.513 | -99.8% |
| estimates_n1e5 | select | 0 | MEMIK-COP | 1e-06 | 3128.504 | 5.574 | -99.8% |
| estimates_n1e5 | bsort100 | 0 | MEMIK-COP | 1e-06 | 3201.592 | 5.730 | -99.8% |
| estimates_multiwindow | select | 8 | MEMIK-COP | 1e-06 | 3132.133 | 5.633 | -99.8% |
| estimates_multiwindow | qsort-exam | 2 | MEMIK-COP | 1e-06 | 1068.478 | 2.563 | -99.8% |
| estimates_multiwindow | ndes | 2 | MEMIK-COP | 0.0001 | 5.245 | 1.494 | -71.5% |
| estimates_multiwindow | ndes | 2 | MEMIK-COP | 1e-05 | 4.516 | 1.388 | -69.3% |
| estimates_multiwindow | ndes | 6 | MEMIK-COP | 0.0001 | 2.882 | 1.371 | -52.4% |
| estimates_multiwindow | ndes | 6 | MEMIK-COP | 1e-05 | 2.523 | 1.256 | -50.2% |
| estimates_multiwindow | ndes | 6 | MEMIK-COP | 1e-06 | 1.607 | 0.831 | -48.3% |
| estimates_multiwindow | select | 1 | MEMIK-COP | 0.0001 | 1.647 | 1.119 | -32.1% |
| estimates | matmult | 0 | MEMIK-COP | 0.0001 | 1.567 | 1.121 | -28.5% |
| estimates_multiwindow | select | 1 | MEMIK-COP | 1e-05 | 1.518 | 1.104 | -27.3% |
| estimates_multiwindow | select | 1 | MEMIK-COP | 1e-06 | 1.244 | 0.940 | -24.4% |
| estimates_multiwindow | ndes | 4 | MEMIK-COP | 0.0001 | 1.946 | 1.496 | -23.1% |
| estimates_multiwindow | qsort-exam | 3 | MEMIK-COP | 0.0001 | 1.400 | 1.085 | -22.5% |
| estimates | matmult | 0 | MEMIK-COP | 1e-05 | 1.415 | 1.098 | -22.4% |
| estimates_multiwindow | qsort-exam | 6 | MEMIK-COP | 0.0001 | 1.399 | 1.102 | -21.2% |
| estimates_multiwindow | ndes | 8 | MEMIK-COP | 0.0001 | 1.795 | 1.431 | -20.3% |
| estimates | fir | 0 | MEMIK-COP | 0.0001 | 1.305 | 1.043 | -20.0% |

## select windows 8 and 9 (worst non-monotone unit curves)

| window | method | p=1e-4 | p=1e-5 | p=1e-6 |
|---|---|---|---|---|
| 8 | E2E-CHB | 0.989 -> 0.989 | 0.925 -> 0.926 | 0.782 -> 0.782 |
| 8 | E2E-MEMIK | 1.003 -> 1.003 | 0.956 -> 0.956 | 0.811 -> 0.811 |
| 8 | CHB-COP | 0.992 -> 0.991 | 0.941 -> 0.939 | 0.931 -> 1.011 |
| 8 | CHB-IND | 0.992 -> 0.990 | 0.941 -> 0.938 | 0.931 -> 1.011 |
| 8 | CHB-COMONO | 1.091 -> 1.091 | 1.020 -> 1.022 | 1.189 -> 1.189 |
| 8 | MEMIK-COP | 1.013 -> 1.013 | 0.980 -> 0.986 | 3132.133 -> 5.633 |
| 9 | E2E-CHB | 1.059 -> 1.059 | 1.034 -> 1.034 | 0.868 -> 0.868 |
| 9 | E2E-MEMIK | 1.075 -> 1.075 | 1.036 -> 1.036 | 0.870 -> 0.870 |
| 9 | CHB-COP | 1.060 -> 1.060 | 1.038 -> 1.033 | 1.053 -> 1.071 |
| 9 | CHB-IND | 1.060 -> 1.060 | 1.037 -> 1.033 | 1.053 -> 1.071 |
| 9 | CHB-COMONO | 1.181 -> 1.181 | 1.144 -> 1.146 | 1.333 -> 1.333 |
| 9 | MEMIK-COP | 1.083 -> 1.083 | 1.059 -> 1.059 | 1.146 -> 1.146 |
