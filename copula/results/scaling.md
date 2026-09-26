N2: R-vine fit (pool par, BIC, independence pre-test) and Monte-Carlo composition time on one core of the Xeon Silver 4216, n = 1e4 runs; MC time per 1e6 draws (linear in N).

| coupling | m | pair copulas | non-independent | fit [s] | MC per 1e6 [s] | MC 1e8 [s] (x100) |
|---|---|---|---|---|---|---|
| sparse | 2 | 1 | 1 | 7.1 | 0.21 | 21 |
| sparse | 4 | 6 | 3 | 22.3 | 0.87 | 87 |
| sparse | 8 | 28 | 7 | 40.1 | 2.52 | 252 |
| sparse | 16 | 120 | 16 | 86.1 | 7.51 | 751 |
| sparse | 24 | 276 | 23 | 154.7 | 13.44 | 1344 |
| sparse | 32 | 496 | 35 | 345.6 | 31.35 | 3135 |
| dense | 2 | 1 | 1 | 4.8 | 0.21 | 21 |
| dense | 4 | 6 | 6 | 27.9 | 1.27 | 127 |
| dense | 8 | 28 | 28 | 142.7 | 5.66 | 566 |
| dense | 16 | 120 | 120 | 612.3 | 88.67 | 8867 |
| dense | 24 | 276 | 276 | 1378.7 | 233.91 | 23391 |
| dense | 32 | 496 | 474 | 2436.6 | 490.32 | 49032 |
