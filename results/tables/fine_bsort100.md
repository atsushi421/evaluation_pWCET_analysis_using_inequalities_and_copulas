Fine-granularity bsort100 (100 ns floor), second campaign (2e6 runs, all traced), window 0; @inst = per-instance loop rule.

```
tightness at p=0.0001 (SMI-censored reference), window 0
bench             E~CHB     E~MEMIK   E~EVT-PoT     EVT-COP   MEMIK-COP     CHB-IND  CHB-COMONO     CHB-COP CHB-IND@inst CHB-COP@inst
bsort100          1.021       1.025       0.990       1.103       1.285       1.202       1.292       1.175        7.151        7.191
#unsafe               0           0           1           0           0           0           0           0            0            0
tightness at p=1e-05 (SMI-censored reference), window 0
bench             E~CHB     E~MEMIK   E~EVT-PoT     EVT-COP   MEMIK-COP     CHB-IND  CHB-COMONO     CHB-COP CHB-IND@inst CHB-COP@inst
bsort100          0.964       0.986       0.927       1.025       1.218       1.141       1.239       1.105       16.265       16.458
#unsafe               1           1           1           0           0           0           0           0            0            0
tightness at p=1e-06 (SMI-censored reference), window 0
bench             E~CHB     E~MEMIK   E~EVT-PoT     EVT-COP   MEMIK-COP     CHB-IND  CHB-COMONO     CHB-COP CHB-IND@inst CHB-COP@inst
bsort100          0.904       0.949       0.859       0.967       1.154       1.079       1.184       1.043       22.424       29.826
#unsafe               1           1           1           1           0           0           0           0            0            0
```
