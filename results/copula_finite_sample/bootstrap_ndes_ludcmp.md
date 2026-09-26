N3 bootstrap: tightness of the decomposed estimators on bootstrap resamples of training window 0 (reference of the full campaign): median [min, max] and resamples below 1.

| bench | method | reps | p=0.0001 | p=1e-05 | p=1e-06 |
|---|---|---|---|---|---|
| ndes | CHB-COP | 20 | 1.231 [1.058, 1.482] 0 | 1.073 [0.978, 1.289] 3 | 0.801 [0.743, 0.962] 20 |
| ndes | CHB-IND | 20 | 1.230 [1.056, 1.483] 0 | 1.071 [0.973, 1.304] 3 | 0.805 [0.742, 0.982] 20 |
| ndes | CHB-COMONO | 20 | 1.515 [1.337, 1.629] 0 | 1.393 [1.192, 1.479] 0 | 1.075 [0.896, 1.145] 2 |
| ludcmp | CHB-COP | 20 | 1.040 [1.024, 1.084] 0 | 0.973 [0.952, 1.010] 19 | 0.975 [0.945, 1.003] 19 |
| ludcmp | CHB-IND | 20 | 1.043 [1.028, 1.085] 0 | 0.975 [0.955, 1.009] 19 | 0.970 [0.944, 0.999] 20 |
| ludcmp | CHB-COMONO | 20 | 1.128 [1.064, 1.149] 0 | 1.072 [0.998, 1.090] 1 | 1.083 [0.995, 1.099] 2 |
