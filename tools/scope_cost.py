#!/usr/bin/env python3
"""E2-10 per-scope cost of CHB-COP on window 0: Algorithm 1 per unit, the pair-copula selection and the
synthesis (Monte-Carlo, or exact integration for two parts) per scope, timed with the production code.
The production functions are wrapped in this process only, so the estimate equals the stored one.

    .venv/bin/python tools/scope_cost.py --traces ipoint/traces_full --bench st --n-mc 1e8
    .venv/bin/python tools/scope_cost.py --table > results/tables/cost_scope.md
"""
import argparse
import glob
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from copula import compose as ccompose  # noqa: E402
from estimation import tree  # noqa: E402
from estimation.data import Bench  # noqa: E402


def measure(traces: str, bench_name: str, n_mc: int) -> dict:
    stack, scopes, leaves, cur = [], [], [], {}

    def timed(key, fn):
        def wrapper(*args, **kw):
            t0 = time.perf_counter()
            try:
                return fn(*args, **kw)
            finally:
                cur[key] = cur.get(key, 0.0) + time.perf_counter() - t0
        return wrapper

    node_marginal, compose_parts, make_leaf = tree.node_marginal, tree.compose_parts, tree.make_leaf

    def node_marginal_w(bench, uid, *args, **kw):
        stack.append(uid)
        try:
            return node_marginal(bench, uid, *args, **kw)
        finally:
            stack.pop()

    def compose_parts_w(parts, X, mode, probs, n, seed):
        cur.clear()
        t0 = time.perf_counter()
        out = compose_parts(parts, X, mode, probs, n, seed)
        scopes.append({"uid": stack[-1], "parts": len(parts), "total_s": time.perf_counter() - t0,
                       **{f"{k}_s": v for k, v in cur.items()}})
        return out

    def make_leaf_w(method, bench, window):
        leaf = make_leaf(method, bench, window)

        def leaf_w(samples, uid):
            t0 = time.perf_counter()
            m = leaf(samples, uid)
            leaves.append({"uid": uid, "n": int(len(samples)), "s": time.perf_counter() - t0})
            return m
        return leaf_w

    tree.node_marginal, tree.compose_parts, tree.make_leaf = node_marginal_w, compose_parts_w, make_leaf_w
    tree._fit_model = timed("selection", tree._fit_model)
    ccompose.compose = timed("mc", ccompose.compose)
    ccompose.exact_sum_quantiles = timed("exact", ccompose.exact_sum_quantiles)

    bench = Bench(traces, bench_name)
    t0 = time.perf_counter()
    pwcet, meta = tree.decomposed_estimate(bench, "CHB-COP", 0, n_mc=n_mc)
    total = time.perf_counter() - t0
    for s in scopes:
        m = meta.get(s["uid"], {})
        s["model"], s["composition"] = m.get("model"), m.get("composition")
        s["dependent_pairs"] = (sum(not e["independent_by_test"] for e in m["edges"]) if "edges" in m
                                else int(m.get("model") not in ("indep", None)))
    return {"bench": bench_name, "traces": traces, "n_mc": n_mc, "total_s": total,
            "estimate_ticks": {str(p): pwcet[p] for p in tree.P_EVAL}, "leaves": leaves, "scopes": scopes}


def table(out_dir: str) -> str:
    L = ["CHB-COP on window 0, one core of the Xeon Silver 4216 (several such processes in parallel). Algorithm 1: "
         "time per unit (median, max). Per scope: parts, dependent pairs after the independence test, pair-copula "
         "selection, and synthesis (exact integration for two parts, Monte-Carlo with N draws for the tail plus "
         f"{tree.N_MC_BODY:.0e} for the body otherwise). Seconds.", "",
         "| program | units | Alg. 1 median, max | scope | parts | dependent pairs | selection | synthesis | synthesis s | total |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for f in sorted(glob.glob(os.path.join(out_dir, "*.json"))):
        d = json.load(open(f))
        ls = np.array([x["s"] for x in d["leaves"]])
        mc = f"MC N={d['n_mc']:.0e}"
        rows = [f"{s['uid']} | {s['parts']} | {s['dependent_pairs']} | {s.get('selection_s', 0):.1f} | "
                f"{'exact' if s.get('exact_s') else mc} | {s.get('exact_s', 0) + s.get('mc_s', 0):.1f}"
                for s in d["scopes"]] or ["– | 1 | – | – | – | –"]
        for i, r in enumerate(rows):
            lead = f"{d['bench']} | {len(ls)} | {np.median(ls):.1f}, {ls.max():.1f}" if i == 0 else " | | "
            L.append(f"| {lead} | {r} | {d['total_s']:.0f} |" if i == 0 else f"| {lead} | {r} | |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--traces")
    ap.add_argument("--bench")
    ap.add_argument("--n-mc", type=float, default=1e8)
    ap.add_argument("--out", default="results/cost_scope")
    ap.add_argument("--table", action="store_true", help="print the markdown table of every stored result")
    a = ap.parse_args()
    if a.table:
        sys.stdout.write(table(a.out))
        return
    r = measure(a.traces, a.bench, int(a.n_mc))
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, f"{a.bench}.json"), "w") as f:
        json.dump(r, f, indent=1, default=float)
    print(f"{a.bench}: {r['total_s']:.0f} s, " + ", ".join(
        f"{s['uid']} {s['parts']} parts {s.get('selection_s', 0):.0f}+{s.get('exact_s', 0) + s.get('mc_s', 0):.0f} s"
        for s in r["scopes"]), flush=True)


if __name__ == "__main__":
    main()
