"""Recompute window-0 decomposed estimates with the current code and compare with results/estimates."""
import json, sys, time
sys.path.insert(0, '.')
from estimation.data import Bench
from estimation import tree
benches = sys.argv[1].split(','); methods = sys.argv[2].split(',')
worst = 0.0
for b in benches:
    bench = Bench('ipoint/traces', b); refs = bench.references(tree.P_EVAL)
    stored = json.load(open(f'results/estimates/{b}.json'))['windows']['0']
    for m in methods:
        t0 = time.perf_counter(); pw, _ = tree.decomposed_estimate(bench, m, 0, int(1e8))
        for p in tree.P_EVAL:
            new = pw[p] / refs['censored'][p]; old = stored[m]['tightness'][str(p)]
            rel = abs(new - old) / old; worst = max(worst, rel)
            flag = '' if rel == 0 else f'  REL {rel:.2e}'
            print(f'{b:<10} {m:<10} p={p:g} new {new:.6f} old {old:.6f}{flag}', flush=True)
        print(f'  [{time.perf_counter()-t0:.0f} s]', flush=True)
print('WORST relative deviation', worst)
