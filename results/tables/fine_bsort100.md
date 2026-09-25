Fine-granularity bsort100 (100 ns floor), window 0; @inst = per-instance loop rule.

```
tightness at p=0.0001 (SMI-censored reference), window 0
bench             E~CHB     E~MEMIK   E~EVT-PoT     EVT-COP   MEMIK-COP     CHB-IND  CHB-COMONO     CHB-COPCHB-IND@instCHB-COP@inst
bsort100          1.030       1.044       0.999       1.111       1.325       1.190       1.331       1.177       6.582       6.619
#unsafe               0           0           1           0           0           0           0           0           0           0
tightness at p=1e-05 (SMI-censored reference), window 0
bench             E~CHB     E~MEMIK   E~EVT-PoT     EVT-COP   MEMIK-COP     CHB-IND  CHB-COMONO     CHB-COPCHB-IND@instCHB-COP@inst
bsort100          0.958       0.987       0.925       1.037       1.240       1.124       1.258       1.088      12.249      14.539
#unsafe               1           1           1           0           0           0           0           0           0           0
tightness at p=1e-06 (SMI-censored reference), window 0
bench             E~CHB     E~MEMIK   E~EVT-PoT     EVT-COP   MEMIK-COP     CHB-IND  CHB-COMONO     CHB-COPCHB-IND@instCHB-COP@inst
bsort100          0.894       0.950       0.855       0.979       1.175       1.081       1.195       1.014      17.165      24.037
#unsafe               1           1           1           1           0           0           0           0           0           0
```
