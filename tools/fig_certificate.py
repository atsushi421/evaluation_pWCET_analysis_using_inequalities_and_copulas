#!/usr/bin/env python3
"""Certified and plug-in bounds relative to the empirical quantile of all runs, per kernel (appendix figure, E2-12).

One panel per kernel, with the numbers of results/tables/certification.md (results/certification/<bench>.json)
at the 25 probabilities of the grid from 1e-1 to 1e-7. The lines are the certified bound fitted on all
SMI-censored runs (n about 9e6, floor 1.17e-6), the certified bound fitted on training window 0 (n = 9000, floor
1.17e-3), and the plug-in bound E2E-CHB fitted on all runs (thin). Below its floor a certificate is +inf and is not
drawn; the dashed vertical lines mark the two floors.

    .venv/bin/python tools/fig_certificate.py [--dir results/certification] [--out results/figs/certificate.pdf]
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fig_tightness import AQUA, BLUE, GRID, INK, MUTED, ORANGE, rc  # noqa: E402
from multiwindow_table import BENCHES  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default="results/certification")
    ap.add_argument("--out", default="results/figs/certificate.pdf")
    a = ap.parse_args()
    rc()
    fig, axes = plt.subplots(3, 4, figsize=(7.16, 3.9), sharex=True, sharey=True)
    for b, ax in zip(BENCHES, axes.flat):
        c = json.load(open(os.path.join(a.dir, f"{b}.json")))
        p, emp = np.array(c["p"]), np.array(c["empirical_all"])
        ratio = lambda key, f: np.array(c[key][f], dtype=float) / emp  # noqa: E731  (inf stays inf, not drawn)
        n_all = c["all"]["n_main"]
        ax.plot(p, ratio("all", "plugin"), color=ORANGE, lw=0.7, label="plug-in bound E2E-CHB, all runs")
        ax.plot(p, ratio("window0", "certified"), color=BLUE, lw=1.1,
                label=f"certified bound, training window 0 (n = {c['window0']['n_main']})")
        ax.plot(p, ratio("all", "certified"), color=AQUA, lw=1.4,
                label=rf"certified bound, all runs (n = {n_all / 1e6:.1f}$\times10^{{6}}$)")
        for key in ("window0", "all"):
            ax.axvline(c[key]["floor"], color=MUTED, lw=0.7, ls=(0, (3, 2)), label="certification floor")
        ax.axhline(1.0, color=INK, lw=0.5, zorder=0)
        ax.text(0.97, 0.94, b, transform=ax.transAxes, ha="right", va="top", fontsize=7.5,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.6))
        ax.grid(True, which="major", lw=0.3, color=GRID)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    ax = axes[0, 0]
    ax.set_xscale("log")
    ax.set_xlim(0.15, 7e-8)                        # tail to the right
    ax.set_xticks([1e-1, 1e-3, 1e-5, 1e-7])
    ax.set_yscale("log")
    ax.set_ylim(0.85, 9)
    ax.set_yticks([1, 1.5, 2, 3, 5], ["1", "1.5", "2", "3", "5"])
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    fig.supxlabel(r"Exceedance probability $p$", fontsize=7, y=0.01)
    fig.supylabel("Bound relative to the empirical quantile", fontsize=7, x=0.005)
    h, lab = ax.get_legend_handles_labels()
    order = [2, 0, 1, 3]                           # filled column by column, so the certificates form the first row
    fig.legend([h[i] for i in order], [lab[i] for i in order], loc="upper center", ncol=2, frameon=False,
               fontsize=7, handlelength=2.4, columnspacing=1.4)
    fig.tight_layout(pad=0.3, rect=(0.01, 0.02, 1, 0.9), h_pad=0.4, w_pad=0.6)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    fig.savefig(a.out)
    fig.savefig(a.out.replace(".pdf", ".png"), dpi=150)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
