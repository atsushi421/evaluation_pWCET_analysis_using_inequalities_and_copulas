Autoware, window 0 (n = 1e4 nominal invocations), steady state: the first nominal invocation of every replay dropped; RESTK n_sims 1000.

```
tightness at p=0.0001 (SMI-censored reference), window 0
bench             E~CHB     E~MEMIK  E~CANTELLI   E~EVT-PoT    E~EVT-BM     EVT-COP   MEMIK-COP     CHB-IND  CHB-COMONO     CHB-COP
cb1               1.152       1.141       7.367       1.012       1.064       4.699       8.027       2.683       5.142       2.924
cb2               1.681       1.645       9.030       1.000           -       1.005       1.648       1.707       1.757       1.679
cb3               1.099       1.180       6.516       0.813           -       0.813       1.091       1.099       1.099       1.099
cb4               1.010       1.090       9.824       0.986           -      13.728       1.496       1.188       2.178       1.260
cb5               1.086       1.100       4.835       1.429           -       1.614       1.340       1.067       1.591       1.095
cb6               1.616       1.602      10.096       1.254           -       1.439       1.621       1.609       1.753       1.617
cb7               1.248       1.244       8.208       0.947           -       0.982       1.607       1.228       1.706       1.321
#unsafe               0           0           0           4           0           2           0           0           0           0
tightness at p=1e-05 (SMI-censored reference), window 0
bench             E~CHB     E~MEMIK  E~CANTELLI   E~EVT-PoT    E~EVT-BM     EVT-COP   MEMIK-COP     CHB-IND  CHB-COMONO     CHB-COP
cb1               1.118       1.114      19.433       0.984       1.168    1178.403       9.585       2.740       6.985       2.986
cb2               1.691       1.747      20.431       1.200           -       1.201       1.750       1.767       1.880       1.770
cb3               0.264       0.279       4.791       0.197           -       0.197       0.260       0.261       0.261       0.261
cb4               0.920       1.034      26.487       0.897           -   14504.308       1.394       1.100       2.432       1.186
cb5               1.180       1.176      12.894       2.709           -      92.501       4.588       1.152       2.058       1.168
cb6               0.375       0.382       6.006       0.279           -       0.279       0.384       0.380       0.419       0.383
cb7               1.332       1.326      22.076       0.922           -       1.207       1.743       1.284       2.241       1.464
#unsafe               3           2           0           5           0           2           2           2           2           2
```
