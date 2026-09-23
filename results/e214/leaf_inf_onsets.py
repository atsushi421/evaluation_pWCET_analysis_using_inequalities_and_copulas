"""Where does the CHB bound of each timed unit of the E2-14 rand window 0 become +inf?"""
import sys; sys.path.insert(0, '.')
import numpy as np
from estimation.data import Bench
from estimation import tree, chb
b = Bench('results/e214/rand', 'qsort-exam'); lo, hi = b.window_bounds(0)
leaf = tree.make_leaf('CHB-IND', 'qsort-exam', 0)
for uid, u in b.units.items():
    for what in (('vals',) if u.self_vals is None else ('vals', 'self')):
        s = b.unit_window(uid, lo, hi, what)
        if len(s) == 0: print(f'{uid} {what}: no instance'); continue
        m = leaf(s, uid + ('' if what == 'vals' else '.self'))
        inf_ps = [p for p, v in m.pwcet.items() if not np.isfinite(v)]
        print(f'{uid:<40} {what:<5} n={len(s):>8} med={np.median(s):8.0f} max={s.max():8.0f} inf from p={max(inf_ps) if inf_ps else None}', flush=True)
