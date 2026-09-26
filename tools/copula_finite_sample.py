#!/usr/bin/env python3
"""Finite-sample behavior of the copula stage (experiment N3 of the paper repo's answers_draft/09, R2-2).

synthetic  Parts with a known joint law: X_i = 1000 + 100 * LogNormal(0, s_i), s_i cycling over 0.25, 0.5,
    1.0, coupled by a D-vine whose first tree carries one pair-copula family (higher trees independent).
    Per replication, n = 1e4 runs are drawn and the 1e-4 and 1e-3 quantiles of the sum are estimated with
    every combination of marginals (CHB = the pipeline's tanh leaf; true = the exact quantile functions)
    and coupling (fit = the pipeline's R-vine, pool par + BIC + independence pre-test; true; indep; comono),
    by Monte-Carlo with N = 2e6 draws. The truth is the Monte-Carlo quantile of the true law with 1e8 draws.
    CHB+fit is what CHB-COP computes; true+fit isolates the error of the fitted copula; CHB+true isolates
    the margin of the unit-level bounds.
bootstrap  The whole decomposed pipeline (CHB-COP, CHB-IND, CHB-COMONO) on bootstrap resamples of the runs of
    a measured training window, against the reference of the full campaign: the spread that the fitted
    copula and the unit-level bounds get from the finite window.

    .venv/bin/python tools/copula_finite_sample.py synthetic --reps 40 --workers 14
    .venv/bin/python tools/copula_finite_sample.py bootstrap --traces ipoint/traces_full --bench ndes --reps 20
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pyvinecopulib as pv
from scipy import stats

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from copula import compose as ccompose  # noqa: E402
from estimation import chb, tree  # noqa: E402
from estimation.data import WINDOW, Bench, UnitData  # noqa: E402

F = pv.BicopFamily
PROBS = (1e-3, 1e-4)
N_TRAIN = 10_000
N_MC = 2_000_000          # 200 draws above the 1e-4 quantile; the truth uses N_TRUE
N_TRUE = 100_000_000
SIGMAS = (0.25, 0.5, 1.0)
# name: (m, family, Kendall's tau of the first tree)
MODELS = {"frank-0.05-m4": (4, F.frank, 0.05), "gauss-0.3-m4": (4, F.gaussian, 0.3),
          "gumbel-0.5-m4": (4, F.gumbel, 0.5), "gumbel-0.3-m8": (8, F.gumbel, 0.3)}
VARIANTS = ("CHB+fit", "true+fit", "CHB+true", "CHB+indep", "CHB+comono", "true+indep")


def true_vine(name):
    m, fam, tau = MODELS[name]
    pc = pv.Bicop(family=fam, parameters=pv.Bicop(family=fam).tau_to_parameters(tau))
    pcs = [[pc] * (m - 1)] + [[pv.Bicop()] * (m - 1 - t) for t in range(1, m - 1)]
    return pv.Vinecop.from_structure(structure=pv.DVineStructure(order=list(range(1, m + 1))), pair_copulas=pcs)


def true_icdfs(m):
    law = [stats.lognorm(SIGMAS[i % len(SIGMAS)]) for i in range(m)]
    return [lambda u, d=d: 1000.0 + 100.0 * d.ppf(np.clip(u, 0.0, 1.0 - 1e-16)) for d in law]


def truth(name):
    m = MODELS[name][0]
    return ccompose.compose(true_vine(name), true_icdfs(m), PROBS, n_samples=N_TRUE, seed=7).quantiles


def replication(name, rep, q_true):
    m = MODELS[name][0]
    v = true_vine(name)
    icdf_t = true_icdfs(m)
    u = v.simulate(N_TRAIN, seeds=[1000 + rep])
    x = np.column_stack([icdf_t[i](u[:, i]) for i in range(m)])
    rng = np.random.default_rng([rep, 11])
    icdf_c = [tree.Marginal(chb.chb_leaf(x[:, i], tree.P_GRID_FULL, rng, certificate=False).pwcet).icdf()
              for i in range(m)]
    fitted, info = tree._fit_model(x, "cop", seed=rep)
    models = {"fit": fitted, "true": v, "indep": "indep"}
    out = {"model": name, "rep": rep, "n_nonindep": sum(e["label"] != "indep" for e in info["edges"])}
    for var in VARIANTS:
        marg, coup = var.split("+")
        icdfs = icdf_c if marg == "CHB" else icdf_t
        if coup == "comono":
            q = {p: float(sum(f(np.array([1.0 - p]))[0] for f in icdfs)) for p in PROBS}
        else:
            q = ccompose.compose(models[coup], icdfs, PROBS, n_samples=N_MC, seed=rep).quantiles
        out[var] = {str(p): q[p] / q_true[p] for p in PROBS}
    return out


def resampled_bench(b: Bench, lo: int, hi: int, rng, tag: str) -> Bench:
    """Window [lo, hi) with its non-censored runs drawn with replacement; one run's unit instances move together."""
    runs = lo + rng.choice(b.window_clean_runs(lo, hi), size=hi - lo, replace=True)
    m = Bench.__new__(Bench)
    m.bench, m.dir, m.schema, m.by_uid, m.tick_ns = tag, b.dir, b.schema, b.by_uid, b.tick_ns
    m.e2e_all = b.e2e_all[runs]
    m.smi_runs = np.empty(0, dtype=np.uint64)
    m._clean_e2e_mask = np.ones(len(runs), dtype=bool)
    m.n_traced = len(runs)
    m.units = {}
    for uid, u in b.units.items():
        keep = (u.runs >= lo) & (u.runs < hi)
        order = np.argsort(u.runs[keep], kind="stable")
        ur = u.runs[keep][order]
        start, end = np.searchsorted(ur, runs), np.searchsorted(ur, runs, side="right")
        idx = np.concatenate([np.arange(s, e) for s, e in zip(start, end)]).astype(np.int64)
        vals = u.vals[keep][order][idx]
        selfs = u.self_vals[keep][order][idx] if u.self_vals is not None else None
        m.units[uid] = UnitData(vals, np.repeat(np.arange(len(runs)), end - start), selfs)
    return m


def bootstrap_one(traces, bench, window, rep, methods, n_mc):
    b = Bench(traces, bench)
    lo, hi = b.window_bounds(window)
    refs = b.references(tree.P_EVAL)["censored"]
    bb = resampled_bench(b, lo, hi, np.random.default_rng([rep, 13]), f"{bench}-boot{rep}")
    out = {"bench": bench, "rep": rep}
    for meth in methods:
        pw, _ = tree.decomposed_estimate(bb, meth, 0, n_mc=n_mc, window_size=hi - lo)
        out[meth] = {str(p): pw[p] / refs[p] for p in tree.P_EVAL}
    return out


def summarize_synthetic(res):
    lines = ["N3 synthetic: estimate / true quantile of the sum over replications of n = 1e4 runs: median "
             "[min, max] and the number of replications below 1. CHB+fit is CHB-COP; true+fit isolates the fitted "
             "copula; CHB+true isolates the unit-level bounds.\n"]
    for name in MODELS:
        rs = [r for r in res if r["model"] == name]
        if not rs:
            continue
        m, fam, tau = MODELS[name]
        nn = [r["n_nonindep"] for r in rs]
        lines += [f"\n{name}: m = {m}, first tree {fam.name} tau {tau}, {len(rs)} replications; "
                  f"non-independent pair copulas fitted: median {np.median(nn):.0f} of {m * (m - 1) // 2}\n",
                  "| variant | " + " | ".join(f"p={p:g}" for p in PROBS) + " |", "|---|" + "---|" * len(PROBS)]
        for var in VARIANTS:
            cells = []
            for p in PROBS:
                v = np.array([r[var][str(p)] for r in rs])
                cells.append(f"{np.median(v):.3f} [{v.min():.3f}, {v.max():.3f}] {int((v < 1).sum())}/{len(v)}")
            lines.append(f"| {var} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def summarize_bootstrap(res):
    lines = ["N3 bootstrap: tightness of the decomposed estimators on bootstrap resamples of training window 0 "
             "(reference of the full campaign): median [min, max] and resamples below 1.\n",
             "| bench | method | reps | " + " | ".join(f"p={p:g}" for p in tree.P_EVAL) + " |",
             "|---|---|---|" + "---|" * len(tree.P_EVAL)]
    for bench in dict.fromkeys(r["bench"] for r in res):
        rs = [r for r in res if r["bench"] == bench]
        for meth in (k for k in rs[0] if k not in ("bench", "rep")):
            cells = []
            for p in tree.P_EVAL:
                v = np.array([r[meth][str(p)] for r in rs])
                cells.append(f"{np.median(v):.3f} [{v.min():.3f}, {v.max():.3f}] {int((v < 1).sum())}")
            lines.append(f"| {bench} | {meth} | {len(rs)} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("synthetic", "bootstrap"))
    ap.add_argument("--reps", type=int, default=40)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--traces", default="ipoint/traces_full")
    ap.add_argument("--bench", default="ndes", help="bootstrap: comma separated")
    ap.add_argument("--window", type=int, default=0)
    ap.add_argument("--methods", default="CHB-COP,CHB-IND,CHB-COMONO")
    ap.add_argument("--n-mc", type=float, default=1e7)
    ap.add_argument("--out", default="results/copula_finite_sample")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    with ProcessPoolExecutor(a.workers) as ex:
        if a.mode == "synthetic":
            names = a.models.split(",")
            q = dict(zip(names, ex.map(truth, names)))
            jobs = [(n, r, q[n]) for n in names for r in range(a.reps)]
            res = list(ex.map(replication, *zip(*jobs)))
            json.dump({"truth": {n: {str(p): v for p, v in q[n].items()} for n in names}, "results": res},
                      open(os.path.join(a.out, "synthetic.json"), "w"), indent=1)
            text = summarize_synthetic(res)
        else:
            jobs = [(a.traces, b, a.window, r, a.methods.split(","), int(a.n_mc))
                    for b in a.bench.split(",") for r in range(a.reps)]
            res = list(ex.map(bootstrap_one, *zip(*jobs)))
            tag = "_".join(a.bench.split(","))
            json.dump(res, open(os.path.join(a.out, f"bootstrap_{tag}.json"), "w"), indent=1)
            text = summarize_bootstrap(res)
    open(os.path.join(a.out, f"{a.mode}{'' if a.mode == 'synthetic' else '_' + tag}.md"), "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
