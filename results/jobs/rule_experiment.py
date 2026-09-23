"""Recompute a few stored entries under each candidate monotonization rule (tools/monotone_rules.py)
by patching copula.compose.monotone_curve; decision material of 2026-09-23.

    .venv/bin/python results/jobs/rule_experiment.py select 2 MEMIK-COP,CHB-COP,E2E-MEMIK,E2E-CHB 1e7
"""
import json, sys, time
sys.path.insert(0, '.'); sys.path.insert(0, 'tools')
import numpy as np
from copula import compose as ccompose
from estimation import tree
from estimation.data import Bench
import monotone_rules as mr
import chb_cop_from_schema as cs

bench_name, window, methods, n_mc = sys.argv[1], int(sys.argv[2]), sys.argv[3].split(','), int(float(sys.argv[4]))
bench = Bench('ipoint/traces', bench_name); refs = bench.references(tree.P_EVAL)['censored']
lo, hi = bench.window_bounds(window)
for rule in ('runmax', 'hybrid 1e-6', 'hybrid 1e-4'):
    fn = mr.RULES[rule]
    def patched(pwcet, fn=fn):
        c = fn(pwcet); a = np.array(sorted(c)); return a, np.array([c[x] for x in a])
    ccompose.monotone_curve = patched
    for m in methods:
        t0 = time.perf_counter()
        if m.startswith('E2E'):
            pw, _ = cs.run_e2e(m, bench.e2e_window(lo, hi), bench_name, window)
        else:
            pw, _ = tree.decomposed_estimate(bench, m, window, n_mc)
        print(f'{rule:12} {bench_name} w{window} {m:10} ' + '  '.join(f'p={p:g}: {pw[p]/refs[p]:.3f}' for p in tree.P_EVAL) + f'  [{time.perf_counter()-t0:.0f} s]', flush=True)
