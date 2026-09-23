"""Why is the E2-14 CHB-IND root +inf at 1e-6? Print, per composed node, the +inf onset of every part
and of the result, the cap, and the numerical tail at a huge t."""
import sys; sys.path.insert(0, '.')
import numpy as np
from estimation.data import Bench
from estimation import tree
from copula import compose as cc

def onset(pw):
    ps = [p for p, v in pw.items() if not np.isfinite(v)]
    return max(ps) if ps else None

_cp = tree.compose_parts
def cp(parts, X, mode, probs, n_mc, seed):
    one = np.array([1.0])
    for i, m in enumerate(parts):
        print(f"  part{i} {str(m.meta.get('uid') or m.meta.get('branch') or m.meta)[:50]:<50} onset={onset(m.pwcet)} icdf(1)={float(m.icdf()(one)[0]):.4g} cdf(1e15)={float(m.cdf()(np.array([1e15]))[0]):.10f}", flush=True)
    if len(parts) == 2 and mode != 'comono':
        cdf1, icdf1, cdf2, icdf2 = parts[0].cdf(), parts[0].icdf(), parts[1].cdf(), parts[1].icdf()
        import pyvinecopulib as pv
        for t in (1e9, 1e12, 1e15):
            print(f"  tail_indep(t={t:g}) = {cc.exact_sum_tail(pv.Bicop(), cdf1, icdf1, cdf2, t):.4e}", flush=True)
    q, info = _cp(parts, X, mode, probs, n_mc, seed)
    print(f"  => onset={onset(q)} q(1e-6)={q.get(1e-6)} q(2e-6)={q.get(2e-6)} {info.get('composition')}", flush=True)
    return q, info
tree.compose_parts = cp
_nm = tree.node_marginal
def nm(bench, uid, *a, **k):
    print(f"node {uid}", flush=True); return _nm(bench, uid, *a, **k)
tree.node_marginal = nm
b = Bench('results/e214/rand', 'qsort-exam')
pw, meta = tree.decomposed_estimate(b, 'CHB-IND', 0, n_mc=int(1e7))
print("ROOT", {p: pw[p] for p in tree.P_EVAL})
