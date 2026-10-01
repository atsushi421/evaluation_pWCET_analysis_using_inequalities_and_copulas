#!/usr/bin/env python3
"""Unsafe-window probability at p = 1e-5 versus the mixing rate rho (X3 sweep), qsort-exam and select.

The values are those of results/tables/x3_mixing_<kernel>.md, computed by tools/x3_summary.py, namely the share
of the training windows (n = 1e4 runs, K ~ Binom(n, rho) of them adversarial) whose estimate lies below the
quantile of the mixture, among the windows with an estimate, at the eight rates of the table. rho = 0 sits at its
own tick left of the log axis and is not joined to the line. E2E-EVT-BM is drawn where at least 1 % of the
windows have an estimate, that is every rate except 1e-3. E2E-CANTELLI, CHB-IND and CHB-IND@max are 0 at every
rate, so their lines overlap on the zero line. The dashed grey curve is (1 - rho)^n, the probability that a window
holds no adversarial run.

    .venv/bin/python tools/fig_mixing.py [--out results/figs/mixing.pdf]
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import x3_summary as xs  # noqa: E402
from fig_tightness import AQUA, GRID, INK, MUTED, STYLE, marker_kw, rc  # noqa: E402

KERNELS = ("qsort-exam", "select")
P = "1e-05"
METHODS = ("E2E-EVT-BM", "E2E-EVT-PoT", "E2E-CANTELLI", "E2E-MEMIK", "E2E-CHB", "CHB-IND", "CHB-IND@max")
LABEL = {"CHB-IND": "CHB-IND (average rule)", "CHB-IND@max": "CHB-IND@max (maximum rule)"}
X0 = 10 ** -6.5          # position of rho = 0
MIN_HAVE = 0.01          # smallest share of windows with an E2E-EVT-BM estimate that is drawn


def style(m):
    """Line and marker style; see-through markers for E2E-CANTELLI and CHB-IND@max keep the three lines at 0 visible."""
    if m == "CHB-IND@max":
        return dict(color=AQUA, ls=(0, (3, 1.5)), lw=1.0, marker="v", ms=6, mfc="none", mec=AQUA, mew=0.8, zorder=2)
    kw = dict(color=STYLE[m][0], lw=1.0, **marker_kw(m))
    if m == "E2E-CANTELLI":
        kw.update(mfc="none", ms=4.2, zorder=4)
    return kw


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="results/figs/mixing.pdf")
    a = ap.parse_args()
    rc()
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.2), sharey=True)
    rhos = np.array(xs.RHOS)
    xpos = np.where(rhos > 0, rhos, X0)
    grid = np.logspace(-6, -3, 200)
    for tag, b, ax in zip("ab", KERNELS, axes):
        r, k, est = xs.load(b, [f"results/x3/x3_{b}.json"])
        refs = [xs.mixture_ref(r, k, rho, float(P)) for rho in rhos]
        ax.plot(grid, (1 - grid) ** xs.N, color=MUTED, lw=1.0, ls=(0, (4, 2)), zorder=1,
                label=r"$(1-\rho)^{n}$, no adversarial run in the window")
        rows = []
        for m in METHODS:
            res = [xs.unsafe_prob(est[m], ref, rho, P) for ref, rho in zip(refs, rhos)]
            y = np.array([np.nan if u is None or (m == "E2E-EVT-BM" and 1 - miss < MIN_HAVE) else u
                          for u, _, miss in res])
            kw = style(m)
            ax.plot(xpos[1:], y[1:], label=LABEL.get(m, m), **kw)
            ax.plot(xpos[:1], y[:1], **{**kw, "ls": "none"})
            rows.append(f"  {m:12s}" + " ".join(f"{v:5.2f}" for v in y))
        print(f"{b} p={P} unsafe probability at rho = {', '.join(f'{x:g}' for x in rhos)}\n" + "\n".join(rows))
        ax.set_xscale("log")
        ax.set_xlim(X0 / 1.6, 1.6e-3)
        ax.set_xticks([X0, 1e-6, 1e-5, 1e-4, 1e-3], ["0", r"$10^{-6}$", r"$10^{-5}$", r"$10^{-4}$", r"$10^{-3}$"])
        ax.set_xticks([f * 10.0 ** e for e in (-6, -5, -4) for f in range(2, 10)], minor=True)
        for x in (10 ** -6.25 / 1.07, 10 ** -6.25 * 1.07):      # axis break between 0 and 1e-6
            ax.plot([x / 1.05, x * 1.05], [-0.025, 0.025], transform=ax.get_xaxis_transform(), color=INK,
                    lw=0.6, clip_on=False)
        ax.set_ylim(-0.04, 1.04)
        ax.grid(True, which="major", lw=0.3, color=GRID)
        ax.set_xlabel(r"Mixing rate $\rho$")
        ax.text(0.98, 0.5, f"({tag}) {b}", transform=ax.transAxes, ha="right", va="center", fontsize=7.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel("Unsafe-window probability")
    h, lab = axes[0].get_legend_handles_labels()
    order = [1, 2, 3, 4, 5, 6, 7, 0]
    fig.legend([h[i] for i in order], [lab[i] for i in order], loc="upper center", ncol=4, frameon=False,
               fontsize=7, handlelength=2.6, columnspacing=1.4)
    fig.tight_layout(pad=0.3, rect=(0, 0, 1, 0.8))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    fig.savefig(a.out)
    fig.savefig(a.out.replace(".pdf", ".png"), dpi=150)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
