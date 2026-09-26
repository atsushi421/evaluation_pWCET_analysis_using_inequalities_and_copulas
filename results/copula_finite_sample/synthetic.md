N3 synthetic: estimate / true quantile of the sum over replications of n = 1e4 runs: median [min, max] and the number of replications below 1. CHB+fit is CHB-COP; true+fit isolates the fitted copula; CHB+true isolates the unit-level bounds.


frank-0.05-m4: m = 4, first tree frank tau 0.05, 40 replications; non-independent pair copulas fitted: median 3 of 6

| variant | p=0.001 | p=0.0001 |
|---|---|---|
| CHB+fit | 1.348 [1.115, 1.800] 0/40 | 1.173 [0.966, 1.802] 2/40 |
| true+fit | 1.000 [0.995, 1.006] 19/40 | 0.998 [0.972, 1.022] 24/40 |
| CHB+true | 1.348 [1.115, 1.800] 0/40 | 1.174 [0.966, 1.802] 2/40 |
| CHB+indep | 1.346 [1.112, 1.779] 0/40 | 1.170 [0.964, 1.793] 3/40 |
| CHB+comono | 1.439 [1.209, 1.870] 0/40 | 1.252 [1.053, 1.891] 0/40 |
| true+indep | 0.998 [0.993, 1.004] 30/40 | 0.999 [0.984, 1.011] 22/40 |

gauss-0.3-m4: m = 4, first tree gaussian tau 0.3, 40 replications; non-independent pair copulas fitted: median 3 of 6

| variant | p=0.001 | p=0.0001 |
|---|---|---|
| CHB+fit | 1.364 [1.135, 1.692] 0/40 | 1.179 [0.939, 1.880] 2/40 |
| true+fit | 1.000 [0.996, 1.006] 20/40 | 0.999 [0.981, 1.018] 24/40 |
| CHB+true | 1.365 [1.135, 1.692] 0/40 | 1.179 [0.939, 1.883] 2/40 |
| CHB+indep | 1.326 [1.104, 1.662] 0/40 | 1.162 [0.908, 1.905] 3/40 |
| CHB+comono | 1.413 [1.196, 1.733] 0/40 | 1.220 [0.999, 1.941] 1/40 |
| true+indep | 0.973 [0.969, 0.979] 40/40 | 0.977 [0.961, 0.988] 40/40 |

gumbel-0.5-m4: m = 4, first tree gumbel tau 0.5, 40 replications; non-independent pair copulas fitted: median 3 of 6

| variant | p=0.001 | p=0.0001 |
|---|---|---|
| CHB+fit | 1.316 [1.097, 1.722] 0/40 | 1.183 [0.891, 1.731] 2/40 |
| true+fit | 1.001 [0.996, 1.004] 19/40 | 0.999 [0.969, 1.022] 23/40 |
| CHB+true | 1.316 [1.097, 1.722] 0/40 | 1.184 [0.891, 1.733] 2/40 |
| CHB+indep | 1.245 [1.063, 1.650] 0/40 | 1.120 [0.846, 1.647] 6/40 |
| CHB+comono | 1.324 [1.100, 1.727] 0/40 | 1.186 [0.895, 1.733] 2/40 |
| true+indep | 0.928 [0.923, 0.933] 40/40 | 0.920 [0.906, 0.930] 40/40 |

gumbel-0.3-m8: m = 8, first tree gumbel tau 0.3, 40 replications; non-independent pair copulas fitted: median 7 of 28

| variant | p=0.001 | p=0.0001 |
|---|---|---|
| CHB+fit | 1.350 [1.164, 1.578] 0/40 | 1.260 [1.078, 1.474] 0/40 |
| true+fit | 1.001 [0.994, 1.008] 16/40 | 1.001 [0.987, 1.027] 16/40 |
| CHB+true | 1.354 [1.167, 1.562] 0/40 | 1.261 [1.079, 1.474] 0/40 |
| CHB+indep | 1.185 [1.054, 1.388] 0/40 | 1.053 [0.900, 1.218] 12/40 |
| CHB+comono | 1.519 [1.319, 1.772] 0/40 | 1.360 [1.165, 1.672] 0/40 |
| true+indep | 0.903 [0.899, 0.906] 40/40 | 0.846 [0.835, 0.853] 40/40 |
