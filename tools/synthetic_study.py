#!/usr/bin/env python3
"""Synthetic-data experiments with analytic ground truth.

families (E1-1): plug-in bound of each envelope family (x^k = MEMIK, arctan, tanh,
    softsign x/(x+d), Hill x^2/(x^2+d^2), 1-exp(-x/d)) under identical settings
    (13-point d grid from a 10% calibration subsample, k <= 150, RESTK n_sims as the pipeline).
grid (E1-2): the CHB leaf (tanh, pipeline settings) under changes of the d grid size,
    its range, k_max, and without the calibration split.

Every configuration sees the same samples (common random numbers): n = 1e4 per
replication, R replications per distribution. The bounds are computed on the
full p grid of the pipeline and monotonized (tree.monotone_pwcet: running
minimum from p = 1e-4 upward, running maximum from it downward) before the ratio
is taken, exactly as the end-to-end
estimators report; the raw per-p ratios are kept under "raw" (P_EVAL) and
"raw_grid" (every grid point), so other monotonization rules can be evaluated
without recomputation. Output: <out>/<mode>.json and a
Markdown summary (median tightness = estimate / true quantile, and the number of
replications below 1).

    .venv/bin/python tools/synthetic_study.py families --reps 20 --workers 4
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import optimize, stats

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from estimation import chb, tree  # noqa: E402

P_EVAL = (1e-3, 1e-4, 1e-5, 1e-6)
N = 10_000


class Mixture:
    """0.999 N(100, 3^2) + 0.001 N(130, 5^2): light tails plus a rare slow mode."""
    w, a, b = 0.001, stats.norm(100, 3), stats.norm(130, 5)

    def rvs(self, size, random_state):
        slow = random_state.uniform(size=size) < self.w
        return np.where(slow, self.b.rvs(size, random_state=random_state), self.a.rvs(size, random_state=random_state))

    def isf(self, p):
        sf = lambda x: (1 - self.w) * self.a.sf(x) + self.w * self.b.sf(x) - p  # noqa: E731
        return optimize.brentq(sf, 0, 1000)


DISTS = {
    "lognormal(s=1)": stats.lognorm(1.0),
    "lognormal(s=1.5)": stats.lognorm(1.5),
    "pareto(a=2)": stats.pareto(2.0),
    "pareto(a=3)": stats.pareto(3.0),
    "weibull(k=0.5)": stats.weibull_min(0.5),
    "normal+rare mode": Mixture(),
}
FAMILY_SET = ("memik", "atan", "tanh", "softsign", "hill2", "expsat")
GRID_CONFIGS = {
    "base (|D|=13, k<=150)": {},
    "|D|=7": {"n_d": 7}, "|D|=20": {"n_d": 20}, "|D|=40": {"n_d": 40},
    "d range x10": {"widen": 10.0},
    "k<=50": {"k_max": 50}, "k<=300": {"k_max": 300},
    "no calibration split": {"no_split": True},
}


def sample(dist: str, rep: int) -> np.ndarray:
    rs = np.random.default_rng([rep, sum(map(ord, dist))])
    return np.asarray(DISTS[dist].rvs(size=N, random_state=rs), dtype=float)


def task(mode, cfg, dist, rep):
    x = sample(dist, rep)
    shift = min(0.0, x.min() - 1.0)            # the estimators need positive samples
    x = x - shift
    rng = np.random.default_rng([rep, 7])
    grid = tree.P_GRID_FULL
    if mode == "families":
        fam = chb.FAMILIES[cfg]
        calib, main = x[:N // 10], x[N // 10:]
        env = chb.family_pwcet(main, cfg, grid, rng, d_list=fam.d_grid(calib))
        raw = {p: env[p][0] for p in grid}
    else:
        o = GRID_CONFIGS[cfg]
        calib, main = (x, x) if o.get("no_split") else (x[:N // 10], x[N // 10:])
        k_max = o.get("k_max", chb.K_MAX)
        raw = {p: np.inf for p in grid}
        for name in chb.CHB_FAMILIES:
            d_list = chb.FAMILIES[name].d_grid(calib, o.get("n_d", 13), o.get("widen", 1.0))
            env = chb.family_pwcet(main, name, grid, rng, d_list=d_list, k_max=k_max)
            raw = {p: min(raw[p], env[p][0]) for p in grid}
    est = tree.monotone_pwcet(raw)         # monotonized exactly as the pipeline reports
    truth = {p: float(DISTS[dist].isf(p)) for p in grid}
    out = {str(p): (est[p] + shift) / truth[p] for p in P_EVAL}
    out["raw"] = {str(p): (raw[p] + shift) / truth[p] for p in P_EVAL}
    out["raw_grid"] = {str(p): (raw[p] + shift) / truth[p] for p in grid}   # any monotonization rule can be applied post hoc
    return cfg, dist, rep, out


def summarize(mode, res, reps):
    configs = FAMILY_SET if mode == "families" else tuple(GRID_CONFIGS)
    lines = [f"Median tightness (estimate / true quantile) over {reps} replications of n = 1e4; "
             "in brackets the number of replications below 1 (unsafe).\n"]
    for dist in DISTS:
        lines.append(f"\n{dist}\n\n| config | " + " | ".join(f"p={p:g}" for p in P_EVAL) + " |\n|---|"
                     + "---|" * len(P_EVAL))
        for cfg in configs:
            cells = []
            for p in P_EVAL:
                v = np.array([r[str(p)] for r in res[cfg][dist]])
                cells.append(f"{np.median(v[np.isfinite(v)]) if np.isfinite(v).any() else np.inf:.3f} [{int((v < 1).sum())}]")
            lines.append(f"| {cfg} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("families", "grid"))
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="results/synthetic")
    ap.add_argument("--shard", default=None, help="i/k: run every k-th task from i, write <mode>.shard<i>.json")
    ap.add_argument("--merge", type=int, default=0, help="merge k shard files instead of running")
    ap.add_argument("--rerule", action="store_true",
                    help="recompute the reported ratios of <out>/<mode>.json from raw_grid with the current "
                         "tree.monotone_pwcet and rewrite the JSON and the Markdown summary")
    a = ap.parse_args()
    if a.rerule:
        path = os.path.join(a.out, f"{a.mode}.json")
        d = json.load(open(path))
        for cfg, per_dist in d["results"].items():
            for dist, reps in per_dist.items():
                truth = {float(k): float(DISTS[dist].isf(float(k))) for k in reps[0]["raw_grid"]}
                for r in reps:
                    mono = tree.monotone_pwcet({float(k): x * truth[float(k)] for k, x in r["raw_grid"].items()})
                    r.update({str(p): mono[p] / truth[p] for p in P_EVAL})
        with open(path, "w") as f:
            json.dump(d, f, indent=1, default=float)
        text = summarize(a.mode, d["results"], d["reps"])
        with open(os.path.join(a.out, f"{a.mode}.md"), "w") as f:
            f.write(text)
        print(text)
        return
    configs = FAMILY_SET if a.mode == "families" else tuple(GRID_CONFIGS)
    tasks = [(a.mode, c, d, r) for c in configs for d in DISTS for r in range(a.reps)]
    res = {c: {d: [None] * a.reps for d in DISTS} for c in configs}
    os.makedirs(a.out, exist_ok=True)
    if a.merge:
        for i in range(a.merge):
            part = json.load(open(os.path.join(a.out, f"{a.mode}.shard{i}.json")))
            for c, d, r, t in part:
                res[c][d][r] = t
    else:
        if a.shard:
            i, k = map(int, a.shard.split("/"))
            tasks = tasks[i::k]
        done = []
        with ProcessPoolExecutor(a.workers) as ex:
            for j, (c, d, r, t) in enumerate(ex.map(task, *zip(*tasks), chunksize=1)):
                res[c][d][r] = t
                done.append((c, d, r, t))
                if (j + 1) % 50 == 0:
                    print(f"{j + 1}/{len(tasks)}", flush=True)
        if a.shard:
            with open(os.path.join(a.out, f"{a.mode}.shard{i}.json"), "w") as f:
                json.dump(done, f, default=float)
            return
    with open(os.path.join(a.out, f"{a.mode}.json"), "w") as f:
        json.dump({"n": N, "reps": a.reps, "p": P_EVAL, "results": res}, f, indent=1, default=float)
    text = summarize(a.mode, res, a.reps)
    with open(os.path.join(a.out, f"{a.mode}.md"), "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
