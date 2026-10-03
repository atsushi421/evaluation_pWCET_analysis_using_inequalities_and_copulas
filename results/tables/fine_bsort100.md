Fine-granularity bsort100 (100 ns floor), second campaign (2e6 runs, all traced), window 0; @max = per-run slowest-iteration loop rule.

```
tightness at p=0.0001 (SMI-censored reference), window 0
bench             E~CHB     E~MEMIK   E~EVT-PoT     EVT-COP   MEMIK-COP     CHB-IND  CHB-COMONO     CHB-COP CHB-IND@max CHB-COP@max
bsort100          1.021       1.025       0.990       1.131       1.165       1.164       1.165       1.164      27.926      27.926
#unsafe               0           0           1           0           0           0           0           0           0           0
tightness at p=1e-05 (SMI-censored reference), window 0
bench             E~CHB     E~MEMIK   E~EVT-PoT     EVT-COP   MEMIK-COP     CHB-IND  CHB-COMONO     CHB-COP CHB-IND@max CHB-COP@max
bsort100          0.964       0.986       0.927       1.047       1.090       1.091       1.091       1.091      25.844      25.844
#unsafe               1           1           1           0           0           0           0           0           0           0
tightness at p=1e-06 (SMI-censored reference), window 0
bench             E~CHB     E~MEMIK   E~EVT-PoT     EVT-COP   MEMIK-COP     CHB-IND  CHB-COMONO     CHB-COP CHB-IND@max CHB-COP@max
bsort100          0.904       0.949       0.859       0.970       1.025       1.022       1.022       1.022      23.958      23.958
#unsafe               1           1           1           1           0           0           0           0           0           0
```
