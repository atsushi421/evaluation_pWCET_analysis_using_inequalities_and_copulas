#!/usr/bin/env python3
"""Compare copula candidate pools and family-selection criteria (experiment E2-5 / CC-D).

Two modes:

``synthetic``  Bivariate data of size n are simulated from copulas with known
    upper-tail behavior (and two mixtures that no candidate family matches).
    Every candidate of the largest pool is fitted once per data set and the
    winner under each criterion and each pool is recorded, together with its
    upper-tail dependence, out-of-sample log-likelihood and the quantiles of
    X + Y (lognormal marginals) obtained by Monte-Carlo composition, compared
    with the truth from the true copula. This isolates the effect of the
    family choice on the program-level estimate.

``traces``  The same comparison on measured unit traces
    (``parsed/units/<uid>.npy`` and ``<uid>.run.npy`` of the ipoint toolkit):
    the copula is fitted on the first ``--train`` runs, the marginals are the
    empirical quantile functions of all runs, and the composed sum is compared
    with the empirical sum over all runs.

Run from the repository root, e.g.
    .venv/bin/python -m copula.study_selection synthetic --reps 20 --workers 12
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pyvinecopulib as pv
from scipy.special import ndtr, ndtri

from copula import compose as cp
from copula import families as fam
from copula import select as sel

F = pv.BicopFamily
POOLS = ("vc15", "par", "all")
CRITERIA = sel.CRITERIA
PROBS = (1e-3, 1e-4, 1e-5, 1e-6)
MARGINAL_SIGMAS = (1.0, 0.7)


def _bicop(family, rotation=0, params=()):
    b = pv.Bicop(family=family, rotation=rotation)
    if params:
        b = pv.Bicop(family=family, rotation=rotation, parameters=np.array(params, dtype=float).reshape(-1, 1))
    return b


def _tau_to_param(family, tau):
    return float(pv.Bicop(family=family).tau_to_parameters(tau).ravel()[0])


class Mixture:
    """Finite mixture of bivariate copulas (still a copula); has simulate/pdf like a Bicop."""

    def __init__(self, components, weights):
        self.components = components
        self.weights = np.asarray(weights, dtype=float)

    def simulate(self, n, seeds=()):
        seed = int(seeds[0]) if seeds else 0
        rng = np.random.default_rng(seed)
        which = rng.choice(len(self.components), size=n, p=self.weights)
        out = np.empty((n, 2))
        for k, c in enumerate(self.components):
            m = int(np.sum(which == k))
            if m:
                out[which == k] = c.simulate(m, seeds=[(seed * 7 + k + 1) % 2_147_483_647])
        return out

    def pdf(self, u):
        return sum(w * c.pdf(u) for w, c in zip(self.weights, self.components))

    def hfunc1(self, u):
        # P(V <= v | U = u) of a mixture of copulas is the mixture of the conditional CDFs
        return sum(w * c.hfunc1(u) for w, c in zip(self.weights, self.components))

    def loglik(self, u):
        return float(np.sum(np.log(self.pdf(u))))

    def lambda_u(self):
        return float(sum(w * fam.tail_dependence_of(c)[1] for w, c in zip(self.weights, self.components)))


def scenario_specs():
    rho05 = math.sin(math.pi * 0.5 / 2)
    return {
        "indep": ("bicop", F.indep, 0, ()),
        "gauss_t0.5": ("bicop", F.gaussian, 0, (rho05,)),
        "gauss_t-0.4": ("bicop", F.gaussian, 0, (math.sin(math.pi * -0.4 / 2),)),
        "t3_t0.5": ("bicop", F.student, 0, (rho05, 3.0)),
        "gumbel_t0.5": ("bicop", F.gumbel, 0, (2.0,)),
        "gumbel_t0.2": ("bicop", F.gumbel, 0, (1.25,)),
        "clayton180_t0.5": ("bicop", F.clayton, 180, (2.0,)),
        "clayton_t0.5": ("bicop", F.clayton, 0, (2.0,)),
        "joe_t0.5": ("bicop", F.joe, 0, (_tau_to_param(F.joe, 0.5),)),
        "frank_t0.5": ("bicop", F.frank, 0, (_tau_to_param(F.frank, 0.5),)),
        "bb1": ("bicop", F.bb1, 0, (0.5, 1.5)),
        "tawn": ("bicop", F.tawn, 0, (0.9, 0.5, 3.0)),
        "mix_gauss_indep": ("mix", [(F.gaussian, 0, (0.8,)), (F.indep, 0, ())], (0.5, 0.5)),
        "mix_gauss_clayton180": ("mix", [(F.gaussian, 0, (0.5,)), (F.clayton, 180, (4.0,))], (0.7, 0.3)),
    }


def build_model(spec):
    if spec[0] == "bicop":
        return _bicop(spec[1], spec[2], spec[3])
    comps = [_bicop(f, r, p) for f, r, p in spec[1]]
    return Mixture(comps, spec[2])


def true_lambda_u(model):
    return model.lambda_u() if isinstance(model, Mixture) else fam.tail_dependence_of(model)[1]


def true_label(spec):
    return fam.label(spec[1], spec[2]) if spec[0] == "bicop" else "mixture"


def marginal_icdfs(sigmas=MARGINAL_SIGMAS):
    return [(lambda u, s=s: np.exp(s * ndtri(np.asarray(u, dtype=float)))) for s in sigmas]


def marginal_cdfs(sigmas=MARGINAL_SIGMAS):
    return [(lambda x, s=s: ndtr(np.log(np.maximum(np.asarray(x, dtype=float), 1e-300)) / s)) for s in sigmas]


def sum_quantiles(model, u_grid=None):
    """Exact quantiles of X + Y for the study marginals (lognormal, no Monte-Carlo)."""
    (F1, F2), (Q1, Q2) = marginal_cdfs(), marginal_icdfs()
    return cp.exact_sum_quantiles(model, F1, Q1, F2, Q2, PROBS, u_grid=u_grid)


def compute_truth(name, spec, n_truth, chunk):
    model = build_model(spec)
    t0 = time.perf_counter()
    q = sum_quantiles(model)
    return name, {"quantiles": {str(p): v for p, v in q.items()}, "lambda_u": true_lambda_u(model),
                  "label": true_label(spec), "seconds": time.perf_counter() - t0, "method": "exact"}


def _model_key(bicop):
    return (bicop.family.name, bicop.rotation, tuple(np.round(np.asarray(bicop.parameters).ravel(), 6).tolist()))


def evaluate_dataset(name, spec, rep, n, n_mc, chunk, cv_folds, indep_alpha, truth):
    """One synthetic data set: fit all candidates once, select under every pool x criterion, compose exactly."""
    model = build_model(spec)
    seed = 1000 * (zlib.crc32(name.encode()) % 1000) + rep  # deterministic across processes and runs
    x = model.simulate(n, seeds=[seed])
    u = sel.pseudo_obs(x)
    test = model.simulate(100_000, seeds=[seed + 500_000])
    ll_true_test = model.loglik(test) / len(test)
    t0 = time.perf_counter()
    cands = sel.fit_candidates(u, pool="all", preselect=True)
    t_fit = time.perf_counter() - t0
    t0 = time.perf_counter()
    sel.evaluate_extra(u, cands, CRITERIA, cv_folds=cv_folds, seed=rep)
    t_extra = time.perf_counter() - t0
    tau, _, pval = sel.independence_test(u)
    u_grid = cp.default_u_grid()
    composed = {}
    rows = []
    for pool in POOLS:
        sub = sel.subset(cands, pool)
        for crit in CRITERIA:
            winner = sel.rank(sub, crit)[0]
            for pretest in (False, True):
                if pretest and pval < indep_alpha:
                    chosen = winner
                elif pretest:
                    chosen = None  # independence by test
                else:
                    chosen = winner
                bicop = chosen.bicop if chosen is not None else pv.Bicop()
                key = _model_key(bicop)
                if key not in composed:
                    t1 = time.perf_counter()
                    q_exact = sum_quantiles(bicop, u_grid)
                    composed[key] = (q_exact, time.perf_counter() - t1, float(bicop.loglik(test)) / len(test))
                q, t_mc, ll_test = composed[key]
                lam_u = fam.tail_dependence_of(bicop)[1]
                if math.isnan(lam_u):
                    lam_u = fam.tail_concentration(bicop, 1 - 1e-4)[1]
                row = {"scenario": name, "true_label": truth["label"], "rep": rep, "n": n, "pool": pool,
                       "pretest": int(pretest), "criterion": crit,
                       "label": fam.label(bicop.family, bicop.rotation), "npars": float(bicop.npars),
                       "tau": tau, "indep_pvalue": pval, "lambda_u": lam_u, "lambda_u_true": truth["lambda_u"],
                       "oos_loglik_gap": ll_true_test - ll_test, "fit_seconds": t_fit, "extra_seconds": t_extra,
                       "mc_seconds": t_mc}
                for p in PROBS:
                    tq = truth["quantiles"][str(p)]
                    row[f"q_{p:g}"] = q[p]
                    row[f"relerr_{p:g}"] = q[p] / tq - 1.0
                rows.append(row)
    return rows


def run_synthetic(args):
    specs = scenario_specs()
    if args.scenarios:
        specs = {k: specs[k] for k in args.scenarios}
    os.makedirs(args.out, exist_ok=True)
    truth_path = os.path.join(args.out, "synthetic_truth.json")
    truth = {}
    if os.path.exists(truth_path) and not args.recompute_truth:
        truth = json.load(open(truth_path))
    todo = [k for k in specs if k not in truth]
    if todo:
        print(f"computing exact truth for {len(todo)} scenarios ...", flush=True)
        with ProcessPoolExecutor(args.workers) as ex:
            futs = [ex.submit(compute_truth, k, specs[k], args.n_truth, args.chunk) for k in todo]
            for f in as_completed(futs):
                k, v = f.result()
                truth[k] = v
                print(f"  truth {k}: {v['quantiles']} ({v['seconds']:.0f}s)", flush=True)
        json.dump(truth, open(truth_path, "w"), indent=1)
    rows = []
    tasks = [(k, specs[k], r) for k in specs for r in range(args.reps)]
    print(f"evaluating {len(tasks)} data sets (n={args.n}, exact composition) on {args.workers} workers ...", flush=True)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(args.workers) as ex:
        futs = {ex.submit(evaluate_dataset, k, s, r, args.n, args.n_mc, args.chunk, args.cv_folds,
                          args.indep_alpha, truth[k]): (k, r) for k, s, r in tasks}
        done = 0
        for f in as_completed(futs):
            rows.extend(f.result())
            done += 1
            if done % 10 == 0 or done == len(tasks):
                print(f"  {done}/{len(tasks)} data sets ({time.perf_counter() - t0:.0f}s)", flush=True)
    path = os.path.join(args.out, "synthetic_rows.csv")
    write_rows(rows, path)
    print(f"wrote {path} ({len(rows)} rows)")
    mc_path = os.path.join(args.out, "synthetic_truth_mc1e8.json")
    truth_mc = json.load(open(mc_path)) if os.path.exists(mc_path) else None
    summarize(rows, os.path.join(args.out, "synthetic_summary.md"), truth, truth_mc)


def write_rows(rows, path):
    keys = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def _fmt(x, nd=3):
    return "nan" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def summarize(rows, path, truth, truth_mc=None):
    import pandas as pd
    df = pd.DataFrame(rows)
    lines = ["# Copula pool x selection criterion study (synthetic)", ""]
    lines.append(f"scenarios: {sorted(df.scenario.unique())}; replicates per scenario: {df.rep.nunique()}; n = {df.n.iloc[0]}")
    lines.append("")
    lines.append("Composed quantiles are computed exactly by numerical integration of P(X+Y > t) over the copula")
    lines.append("(trapezoidal rule on a 47k-point grid refined toward both ends, bisection in t); no Monte-Carlo noise.")
    if truth_mc:
        lines.append("")
        lines.append("Validation of the integration against a 1e8-sample Monte-Carlo truth (relative difference exact/MC - 1):")
        lines.append("")
        lines.append("| scenario | p=1e-3 | p=1e-4 | p=1e-5 | p=1e-6 (MC has ~100 exceedances) |")
        lines.append("|---|---|---|---|---|")
        for scen in sorted(truth):
            if scen in truth_mc:
                cells = [f"{truth[scen]['quantiles'][k] / truth_mc[scen]['quantiles'][k] - 1:+.4f}" for k in ("0.001", "0.0001", "1e-05", "1e-06")]
                lines.append(f"| {scen} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("Metrics per (pool, pretest, criterion), averaged over scenarios and replicates:")
    lines.append("`recover` = share of data sets whose winner has the true family and rotation (scenarios whose truth is in the pool);")
    lines.append("`|dlamU|` = mean absolute error of the upper-tail dependence coefficient; `oos_gap` = mean per-observation")
    lines.append("out-of-sample log-likelihood deficit against the true copula; `mre_p` = mean relative error of the")
    lines.append("composed quantile at exceedance probability p; `min_p` = worst relative error (negative = underestimation);")
    lines.append("`unsafe_p` = share of data sets with relative error below -5%.")
    lines.append("")
    hdr = "| pool | pretest | criterion | recover | \\|dlamU\\| | oos_gap | mre_1e-4 | min_1e-4 | unsafe_1e-4 | mre_1e-5 | min_1e-5 | unsafe_1e-5 | mre_1e-6 | min_1e-6 |"
    lines.append(hdr)
    lines.append("|" + "---|" * (hdr.count("|") - 1))
    pool_has = {}
    for pool in POOLS:
        labels = {fam.label(f, r) for f, r in fam.candidates(pool)}
        pool_has[pool] = labels
    for (pool, pretest, crit), g in df.groupby(["pool", "pretest", "criterion"], sort=False):
        rec_mask = g.true_label.isin(pool_has[pool]) | ((g.true_label == "indep") & (pretest == 1))
        recover = float(np.mean(g.label[rec_mask] == g.true_label[rec_mask])) if rec_mask.any() else float("nan")
        cells = [pool, str(pretest), crit, _fmt(recover, 2), _fmt(float(np.mean(np.abs(g.lambda_u - g.lambda_u_true)))),
                 _fmt(float(g.oos_loglik_gap.mean()), 4)]
        for p in ("0.0001", "1e-05"):
            col = g[f"relerr_{p}"]
            cells += [_fmt(float(col.mean())), _fmt(float(col.min())), _fmt(float(np.mean(col < -0.05)), 2)]
        col = g["relerr_1e-06"]
        cells += [_fmt(float(col.mean())), _fmt(float(col.min()))]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Per scenario, pool `par`, no pretest: winner shares and relative error at p = 1e-5")
    lines.append("")
    sub = df[(df.pool == "par") & (df.pretest == 0)]
    for scen, g in sub.groupby("scenario", sort=False):
        lines.append(f"### {scen} (true {g.true_label.iloc[0]}, lambda_U = {g.lambda_u_true.iloc[0]:.3f}, "
                     f"true q(1e-5) = {truth[scen]['quantiles']['1e-05']:.2f})")
        lines.append("")
        lines.append("| criterion | winners (share) | mean lambda_U | mean relerr 1e-4 | mean relerr 1e-5 | min relerr 1e-5 |")
        lines.append("|---|---|---|---|---|---|")
        for crit, gg in g.groupby("criterion", sort=False):
            shares = gg.label.value_counts(normalize=True)
            win = ", ".join(f"{k} ({v:.0%})" for k, v in shares.items())
            lines.append(f"| {crit} | {win} | {gg.lambda_u.mean():.3f} | {gg['relerr_0.0001'].mean():+.3f} | "
                         f"{gg['relerr_1e-05'].mean():+.3f} | {gg['relerr_1e-05'].min():+.3f} |")
        lines.append("")
    lines.append("## Cost")
    lines.append("")
    lines.append(f"mean seconds per data set: fit all candidates of pool `all` {df.fit_seconds.mean():.2f}, "
                 f"cross-validation + tail statistics {df.extra_seconds.mean():.2f}, "
                 f"one exact composition {df.mc_seconds.mean():.2f}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {path}")


# ---------------------------------------------------------------- traces mode

def load_unit_matrix(parsed_dir, units, max_runs=None):
    """Per-run totals of the given units, aligned by run index (inner join)."""
    per_run = []
    for uid in units:
        s = np.load(os.path.join(parsed_dir, "units", f"{uid}.npy")).astype(float)
        r = np.load(os.path.join(parsed_dir, "units", f"{uid}.run.npy")).astype(np.int64)
        tot = {}
        for run, val in zip(r, s):
            tot[run] = tot.get(run, 0.0) + val
        per_run.append(tot)
    runs = sorted(set.intersection(*[set(t) for t in per_run]))
    if max_runs:
        runs = runs[:max_runs]
    X = np.array([[t[run] for t in per_run] for run in runs], dtype=float)
    return np.array(runs), X


def run_traces(args):
    runs, X = load_unit_matrix(args.parsed_dir, args.units, args.max_runs)
    n_train = min(args.train, len(X))
    Xtr = X[:n_train]
    u = sel.pseudo_obs(Xtr, ties_method=args.ties)
    ref = cp.empirical_quantiles(X.sum(axis=1), PROBS)
    icdfs = [cp.icdf_from_samples(X[:, i]) for i in range(X.shape[1])]
    cdfs = [cp.cdf_from_samples(X[:, i]) for i in range(X.shape[1])]
    rows = []
    if X.shape[1] == 2:
        def composed_quantiles(model):
            if isinstance(model, str):
                return cp.compose(model, icdfs, PROBS, n_samples=args.n_mc, chunk=args.chunk).quantiles
            return cp.exact_sum_quantiles(model, cdfs[0], icdfs[0], cdfs[1], icdfs[1], PROBS)
        cands = sel.fit_candidates(u, pool="all")
        sel.evaluate_extra(u, cands, CRITERIA, cv_folds=args.cv_folds)
        tau, _, pval = sel.independence_test(u)
        composed = {}
        for pool in POOLS:
            sub = sel.subset(cands, pool)
            for crit in CRITERIA:
                w = sel.rank(sub, crit)[0]
                key = _model_key(w.bicop)
                if key not in composed:
                    composed[key] = composed_quantiles(w.bicop)
                q = composed[key]
                row = {"units": "+".join(args.units), "pool": pool, "criterion": crit, "label": w.label, "tau": tau,
                       "indep_pvalue": pval, "lambda_u": w.lambda_u, "bic": w.bic, "aic": w.aic, "cv": w.cv_loglik,
                       "tcf": w.tcf}
                for p in PROBS:
                    row[f"q_{p:g}"] = q[p]
                    row[f"ref_{p:g}"] = ref[p]
                    row[f"tightness_{p:g}"] = q[p] / ref[p]
                rows.append(row)
        for name in ("indep", "comono"):
            q = composed_quantiles(name)
            row = {"units": "+".join(args.units), "pool": name, "criterion": "-", "label": name, "tau": tau,
                   "indep_pvalue": pval, "lambda_u": float("nan"), "bic": float("nan"), "aic": float("nan"),
                   "cv": float("nan"), "tcf": float("nan")}
            for p in PROBS:
                row[f"q_{p:g}"] = q[p]
                row[f"ref_{p:g}"] = ref[p]
                row[f"tightness_{p:g}"] = q[p] / ref[p]
            rows.append(row)
    else:
        from copula import vine as vn
        for pool in POOLS:
            for crit in CRITERIA:
                fit = vn.fit_vine(u, pool=pool, criterion=crit, indep_alpha=args.indep_alpha, cv_folds=args.cv_folds)
                q = cp.compose(fit.vinecop, icdfs, PROBS, n_samples=args.n_mc, chunk=args.chunk).quantiles
                row = {"units": "+".join(args.units), "pool": pool, "criterion": crit,
                       "label": ";".join(e["label"] for e in fit.edges()), "tau": float("nan"),
                       "indep_pvalue": float("nan"), "lambda_u": float("nan"), "bic": float("nan"),
                       "aic": float("nan"), "cv": float("nan"), "tcf": float("nan")}
                for p in PROBS:
                    row[f"q_{p:g}"] = q[p]
                    row[f"ref_{p:g}"] = ref[p]
                    row[f"tightness_{p:g}"] = q[p] / ref[p]
                rows.append(row)
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, f"traces_{'_'.join(args.units)}.csv")
    write_rows(rows, path)
    print(f"wrote {path} ({len(rows)} rows); runs used: {len(X)}, train: {n_train}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="mode", required=True)
    a = sp.add_parser("synthetic")
    a.add_argument("--n", type=int, default=10_000, help="training sample size")
    a.add_argument("--reps", type=int, default=20)
    a.add_argument("--n-mc", type=float, default=1e7, help="unused for synthetic (exact composition); kept for compatibility")
    a.add_argument("--n-truth", type=float, default=1e8, help="unused (exact truth); kept for compatibility")
    a.add_argument("--chunk", type=int, default=2_000_000)
    a.add_argument("--cv-folds", type=int, default=5)
    a.add_argument("--indep-alpha", type=float, default=0.05)
    a.add_argument("--workers", type=int, default=max(1, os.cpu_count() - 2))
    a.add_argument("--scenarios", nargs="*", default=None)
    a.add_argument("--recompute-truth", action="store_true")
    a.add_argument("--out", default="copula/results")
    b = sp.add_parser("traces")
    b.add_argument("--parsed-dir", required=True)
    b.add_argument("--units", nargs="+", required=True)
    b.add_argument("--train", type=int, default=10_000)
    b.add_argument("--max-runs", type=int, default=None)
    b.add_argument("--ties", default="average", choices=["average", "random", "min", "max", "first", "dense"])
    b.add_argument("--n-mc", type=float, default=1e7)
    b.add_argument("--chunk", type=int, default=2_000_000)
    b.add_argument("--cv-folds", type=int, default=5)
    b.add_argument("--indep-alpha", type=float, default=0.05)
    b.add_argument("--out", default="copula/results")
    args = ap.parse_args(argv)
    args.n_mc = int(args.n_mc)
    if args.mode == "synthetic":
        args.n_truth = int(args.n_truth)
        run_synthetic(args)
    else:
        run_traces(args)


if __name__ == "__main__":
    main()
