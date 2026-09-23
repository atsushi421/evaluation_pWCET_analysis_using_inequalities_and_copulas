"""How many CHB leaf curves of the stored decomposed results are non-monotone in p near the tail
(v(p) > v(p') for some p' < p, p <= 1e-4)? Recomputes the leaves only (window 0..9 of the 12 kernels,
n=1e5 window, the fine bsort100 and the E2-14 qsort-exam windows)."""
import sys; sys.path.insert(0, '.')
import numpy as np
from estimation.data import Bench
from estimation import tree, chb
def scan(traces, bench, windows, wsize):
    b = Bench(traces, bench)
    for w in windows:
        lo, hi = b.window_bounds(w, wsize)
        for uid, u in b.units.items():
            for what in (('vals',) if u.self_vals is None else ('vals', 'self')):
                s = b.unit_window(uid, lo, hi, what)
                if len(s) == 0: continue
                r = chb.chb_leaf(s, tree.P_GRID_FULL, tree._seed(bench, w, uid + ('' if what == 'vals' else '.self'), 'CHB'), certificate=False)
                ps = sorted(r.pwcet); vals = [r.pwcet[p] for p in ps]     # ps ascending: 1e-10 .. 0.5
                bad = [(p, r.pwcet[p], min(r.pwcet[q] for q in ps if q < p)) for p in ps if p <= 1e-4 and any(np.isfinite(r.pwcet[q]) and r.pwcet[q] < r.pwcet[p] for q in ps if q < p)]
                if bad:
                    worst = max(bad, key=lambda t: (t[1] - t[2]) / t[2] if np.isfinite(t[1]) else 0)
                    print(f"{traces}/{bench} w{w} {uid}.{what}: non-monotone at {[f'{p:g}' for p,_,_ in bad]} worst p={worst[0]:g} v={worst[1]:.0f} min_below={worst[2]:.0f} ({(worst[1]-worst[2])/worst[2]*100:.1f}%)", flush=True)
        print(f"{bench} w{w} done", flush=True)
for b in ["bsort100", "fir", "matmult", "edn", "ndes", "st", "lms", "prime", "cnt", "ludcmp", "select", "qsort-exam"]:
    scan('ipoint/traces', b, range(10), 10000)
    scan('ipoint/traces', b, [0], 100000)
scan('ipoint/traces_fine', 'bsort100', [0], 10000)
scan('results/e214/rand', 'qsort-exam', [0], 10000)
print("SCAN DONE")
