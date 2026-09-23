#!/usr/bin/env python3
"""E2-11: Figure 1 with numerical axes, from the bsort100 end-to-end traces.

Empirical CCDF of the 1e4 training runs (window 0) and of all 1e7 runs, the
plug-in saturating-Chebyshev bound fitted on the training runs, and its
certified version (finite above the floor 1 - e^{-tau} only). The pWCET at
p = 1e-4 (the main evaluation point) is marked. Needs results/certification/<bench>.json.

    .venv/bin/python tools/fig_pwcet_concept.py [--bench bsort100] [--out results/figs/pwcet_concept.pdf]
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from estimation.data import Bench  # noqa: E402

BLUE, ORANGE, AQUA, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#1a1a19", "#8a8980"
P_MARK = 1e-4


def ccdf(x):
    xs = np.sort(x)
    return xs, 1.0 - np.arange(len(xs)) / len(xs)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--traces", default="ipoint/traces")
    ap.add_argument("--bench", default="bsort100")
    ap.add_argument("--cert", default="results/certification")
    ap.add_argument("--out", default="results/figs/pwcet_concept.pdf")
    a = ap.parse_args()
    bench = Bench(a.traces, a.bench)
    us = bench.tick_ns / 1e3
    train = bench.e2e_window(*bench.window_bounds(0)) * us
    allruns = bench.e2e_all[bench._clean_e2e_mask] * us
    c = json.load(open(os.path.join(a.cert, f"{a.bench}.json")))
    p = np.array(c["p"])
    plug = np.array(c["window0"]["plugin"]) * us
    cert = np.array(c["window0"]["certified"]) * us

    plt.rcParams.update({"font.size": 8, "font.family": "serif", "axes.linewidth": 0.6})
    fig, ax = plt.subplots(figsize=(3.45, 2.75))
    xa, ya = ccdf(allruns)
    xt, yt = ccdf(train)
    ax.step(xa, ya, where="post", color=MUTED, lw=1.0, label=r"all $10^7$ runs (empirical)")
    ax.step(xt, yt, where="post", color=BLUE, lw=1.4, label=r"$10^4$ training runs (empirical)")
    shown = p >= 1e-6          # below the RESTK test points the k ceiling is extrapolated
    ax.plot(plug[shown], p[shown], color=ORANGE, lw=1.4, ls="--", label="plug-in bound (training runs)")
    fin = np.isfinite(cert)
    ax.plot(cert[fin], p[fin], color=AQUA, lw=1.4, ls=":", label=r"certified bound ($1-\alpha=0.95$)")
    floor = c["window0"]["floor"]
    ax.axhline(floor, color=AQUA, lw=0.6, ls=(0, (1, 2)))
    ax.text(train.min(), floor * 1.3, f"certification floor {floor:.2g}",
            color=INK, fontsize=6.5, va="bottom")
    i = int(np.argmin(np.abs(np.log10(p / P_MARK))))
    ax.axhline(P_MARK, color=INK, lw=0.5, ls="-", alpha=0.4)
    ax.plot([plug[i]], [P_MARK], "o", ms=4, color=ORANGE, mec="white", mew=0.8, zorder=5)
    ax.annotate(rf"pWCET$(10^{{{int(np.log10(P_MARK))}}})$ = {plug[i]:.1f} $\mu$s", (plug[i], P_MARK), xytext=(6, 6),
                textcoords="offset points", fontsize=6.5, color=INK)
    ax.set_yscale("log")
    ax.set_ylim(1e-7, 1.5)
    ax.set_xlim(train.min() * 0.97, xa.max() * 1.03)
    ax.set_xlabel(r"execution time $x$ [$\mu$s]")
    ax.set_ylabel(r"$P(X \geq x)$")
    ax.grid(True, which="major", lw=0.3, color="#d9d8d1")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.42, -0.2), ncol=2, fontsize=5.8, frameon=False,
              handlelength=2.2, columnspacing=1.0)
    fig.tight_layout(pad=0.3)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    fig.savefig(a.out)
    fig.savefig(a.out.replace(".pdf", ".png"), dpi=200)
    print(f"wrote {a.out}; pWCET({P_MARK:g}) = {plug[i]:.2f} us at p={p[i]:.2g}, floor {floor:.3g}")


if __name__ == "__main__":
    main()
