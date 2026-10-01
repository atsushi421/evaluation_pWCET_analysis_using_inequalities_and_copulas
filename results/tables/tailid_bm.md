# TailID scenarios and block maxima

TailID scenario of every PoT fit (meta `tailid_scenario`: 1 keeps the EQMAE threshold, 2 moves it to the first ID-sensitive point, 3 falls back to the ECDF). '< 10 exceedances': scenario 1 or 2 whose threshold leaves fewer than 10 exceedances, which also falls back to the ECDF (meta `fallback`, estimation/evt.py). ECDF %: both fallbacks. Sources: results/estimates/*.json, results/estimates_autoware_warm1/*.json.

## E2E-EVT-PoT (benchmarks, 50 windows each; Autoware, all windows)

| program | fits | scenario 1 | scenario 2 | scenario 3 | < 10 exceedances | scenario 3 % | ECDF % | median xi (GPD windows) |
|---|---|---|---|---|---|---|---|---|
| bsort100 | 50 | 0 | 0 | 50 | 0 | 100.0 | 100.0 | - |
| fir | 50 | 0 | 50 | 0 | 0 | 0.0 | 0.0 | -0.77 |
| matmult | 50 | 0 | 50 | 0 | 0 | 0.0 | 0.0 | 1.93 |
| edn | 50 | 0 | 0 | 50 | 0 | 100.0 | 100.0 | - |
| ndes | 50 | 0 | 0 | 50 | 0 | 100.0 | 100.0 | - |
| st | 50 | 0 | 50 | 0 | 0 | 0.0 | 0.0 | 3.55 |
| lms | 50 | 0 | 50 | 0 | 0 | 0.0 | 0.0 | -0.05 |
| prime | 50 | 39 | 5 | 6 | 0 | 12.0 | 12.0 | -0.70 |
| cnt | 50 | 0 | 50 | 0 | 0 | 0.0 | 0.0 | -0.10 |
| ludcmp | 50 | 0 | 50 | 0 | 0 | 0.0 | 0.0 | -0.80 |
| select | 50 | 12 | 0 | 38 | 0 | 76.0 | 76.0 | -0.17 |
| qsort-exam | 50 | 0 | 2 | 48 | 0 | 96.0 | 96.0 | 0.13 |
| cb1 | 53 | 0 | 0 | 53 | 0 | 100.0 | 100.0 | - |
| cb2 | 53 | 0 | 0 | 53 | 0 | 100.0 | 100.0 | - |
| cb3 | 53 | 0 | 53 | 0 | 0 | 0.0 | 0.0 | -0.19 |
| cb4 | 33 | 9 | 0 | 24 | 0 | 72.7 | 72.7 | -0.29 |
| cb5 | 12 | 12 | 0 | 0 | 0 | 0.0 | 0.0 | 0.44 |
| cb6 | 9 | 0 | 0 | 9 | 0 | 100.0 | 100.0 | - |
| cb7 | 10 | 3 | 7 | 0 | 0 | 0.0 | 0.0 | -0.12 |
| Autoware | 223 | 24 | 60 | 139 | 0 | 62.3 | 62.3 | -0.16 |

## EVT-COP leaves (benchmarks: windows 0-49, or 0-9 for the R-vine kernels; Autoware: window 0)

| program | fits | scenario 1 | scenario 2 | scenario 3 | < 10 exceedances | scenario 3 % | ECDF % |
|---|---|---|---|---|---|---|---|
| bsort100 | 100 | 0 | 50 | 50 | 0 | 50.0 | 50.0 |
| fir | 100 | 0 | 100 | 0 | 0 | 0.0 | 0.0 |
| matmult | 100 | 0 | 100 | 0 | 2 | 0.0 | 2.0 |
| edn | 40 | 0 | 20 | 20 | 1 | 50.0 | 52.5 |
| ndes | 40 | 0 | 27 | 13 | 10 | 32.5 | 57.5 |
| st | 60 | 0 | 60 | 0 | 1 | 0.0 | 1.7 |
| lms | 30 | 2 | 24 | 4 | 0 | 13.3 | 13.3 |
| prime | 50 | 39 | 5 | 6 | 0 | 12.0 | 12.0 |
| cnt | 100 | 0 | 100 | 0 | 0 | 0.0 | 0.0 |
| ludcmp | 50 | 0 | 40 | 10 | 10 | 20.0 | 40.0 |
| select | 100 | 11 | 50 | 39 | 0 | 39.0 | 39.0 |
| qsort-exam | 100 | 0 | 45 | 55 | 0 | 55.0 | 55.0 |
| benchmarks | 870 | 52 | 621 | 197 | 24 | 22.6 | 25.4 |
| cb1 (w0) | 24 | 1 | 12 | 11 | 6 | 45.8 | 70.8 |
| cb2 (w0) | 3 | 0 | 1 | 2 | 1 | 66.7 | 100.0 |
| cb3 (w0) | 1 | 0 | 1 | 0 | 0 | 0.0 | 0.0 |
| cb4 (w0) | 74 | 7 | 46 | 21 | 29 | 28.4 | 67.6 |
| cb5 (w0) | 8 | 4 | 4 | 0 | 3 | 0.0 | 37.5 |
| cb6 (w0) | 31 | 1 | 22 | 8 | 20 | 25.8 | 90.3 |
| cb7 (w0) | 18 | 5 | 11 | 2 | 4 | 11.1 | 33.3 |
| Autoware w0 | 159 | 18 | 97 | 44 | 63 | 27.7 | 67.3 |

## E2E-EVT-BM (benchmarks, 50 windows each; Autoware, all windows)

A window has an estimate when at least one block size B passes Q-Q R^2 >= 0.99 (the estimate is the median over the accepted B); per B, the windows in which it was accepted.

| program | windows with an estimate | B=10 accepted | B=20 | B=50 | B=100 |
|---|---|---|---|---|---|
| bsort100 | 22/50 | 5 | 15 | 11 | 7 |
| fir | 0/50 | 0 | 0 | 0 | 0 |
| matmult | 0/50 | 0 | 0 | 0 | 0 |
| edn | 0/50 | 0 | 0 | 0 | 0 |
| ndes | 0/50 | 0 | 0 | 0 | 0 |
| st | 0/50 | 0 | 0 | 0 | 0 |
| lms | 6/50 | 0 | 0 | 2 | 6 |
| prime | 12/50 | 0 | 0 | 2 | 10 |
| cnt | 2/50 | 0 | 0 | 0 | 2 |
| ludcmp | 0/50 | 0 | 0 | 0 | 0 |
| select | 25/50 | 17 | 11 | 15 | 14 |
| qsort-exam | 31/50 | 26 | 6 | 24 | 21 |
| all | 98/600 | 48 | 32 | 54 | 60 |
| cb1 | 46/53 | 0 | 40 | 35 | 19 |
| cb2 | 8/53 | 1 | 7 | 3 | 2 |
| cb3 | 0/53 | 0 | 0 | 0 | 0 |
| cb4 | 0/33 | 0 | 0 | 0 | 0 |
| cb5 | 0/12 | 0 | 0 | 0 | 0 |
| cb6 | 0/9 | 0 | 0 | 0 | 0 |
| cb7 | 0/10 | 0 | 0 | 0 | 0 |
| Autoware | 54/223 | 1 | 47 | 38 | 21 |
