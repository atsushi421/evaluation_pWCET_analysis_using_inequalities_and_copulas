#!/usr/bin/env python3
"""Tightness at p = 1e-4 of the ten methods over the training windows, per benchmark kernel and per Autoware callback.

The marker is the median over the windows with an estimate and the bar spans the minimum to the maximum, over the
same windows as results/tables/multiwindow.md and autoware_multiwindow.md. The benchmarks have 50 windows per
kernel, except EVT-COP, MEMIK-COP and CHB-COP on the five kernels with a vine (edn, ndes, st, lms, ludcmp; windows
0-9) and E2E-EVT-BM, which has an estimate only where a block size passes its test (98 of 600 windows, none on six
kernels). On the Autoware callbacks (steady state), the end-to-end methods use every window (223 in total;
E2E-EVT-BM only 46 on cb1 and 8 on cb2), CHB-IND and CHB-COMONO windows 0-9 (cb6 has 9), and the copula methods
window 0 only (marker, no bar). The +inf estimate of CHB-IND and CHB-COMONO on cb5 window 9 is safe but left out of
the median and range, as in the table. Values above 20 are cut at the top edge, where an arrow ends the bar; the
number beside it is the maximum, with the median in parentheses when the median is above 20 as well.

    .venv/bin/python tools/fig_tightness.py [--outdir results/figs]
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.transforms import offset_copy  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiwindow_table import BENCHES, load, tight  # noqa: E402

BLUE, ORANGE, AQUA, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#1a1a19", "#8a8980"
VIOLET, GRID = "#4a3aa7", "#d9d8d1"
P = "0.0001"
TOP = 20.0
CBS = [f"cb{i}" for i in range(1, 8)]
# colour by unit estimator, marker shape within it; end-to-end methods hollow, decomposed methods filled
STYLE = {"E2E-EVT-BM": (ORANGE, "s"), "E2E-EVT-PoT": (ORANGE, "o"), "E2E-CANTELLI": (INK, "D"),
         "E2E-MEMIK": (VIOLET, "o"), "E2E-CHB": (BLUE, "o"),
         "EVT-COP": (ORANGE, "o"), "MEMIK-COP": (VIOLET, "o"), "CHB-IND": (AQUA, "v"),
         "CHB-COMONO": (AQUA, "^"), "CHB-COP": (BLUE, "o")}
METHODS = list(STYLE)


def rc():
    plt.rcParams.update({"font.size": 7, "font.family": "serif", "mathtext.fontset": "dejavuserif",
                         "axes.linewidth": 0.6, "pdf.fonttype": 42,
                         "xtick.major.width": 0.6, "ytick.major.width": 0.6, "ytick.minor.width": 0.4})


def marker_kw(m, ms=3.6):
    c, mk = STYLE[m]
    hollow = m.startswith("E2E")
    return dict(marker=mk, ms=ms * (0.85 if mk in "sD" else 1), mfc="white" if hollow else c,
                mec=c if hollow else "white", mew=0.8 if hollow else 0.3)


def big(v):
    if v < 100:
        return f"{v:.0f}"
    e = int(np.floor(np.log10(v)))
    return rf"${v / 10 ** e:.1f}{{\times}}10^{{{e}}}$"


def panel(ax, data, groups, bottom):
    slot, gap = 0.08, 0.06
    clipped = []
    for g, b in enumerate(groups):
        for i, m in enumerate(METHODS):
            v = np.array([t for w in data[b].values() if (t := tight(w, m, P)) is not None])
            v = v[np.isfinite(v)]
            if not len(v):
                continue
            x = g + (i - 4.5) * slot + (gap if i >= 5 else -gap) / 2
            med, lo, hi = np.median(v), v.min(), v.max()
            c = STYLE[m][0]
            if hi > lo:
                ax.vlines(x, lo, min(hi, TOP), color=c, lw=0.8, zorder=2)
            if med <= TOP:
                ax.plot([x], [med], ls="none", zorder=3, **marker_kw(m))
            if hi > TOP:
                ax.annotate("", xy=(x, TOP), xytext=(0, -7), textcoords="offset points", annotation_clip=False,
                            arrowprops=dict(arrowstyle="-|>", color=c, lw=0.8, mutation_scale=5,
                                            shrinkA=0, shrinkB=0))
                txt = big(hi) + (f" ({big(med)})" if med > TOP else "")
                ax.text(x, TOP, txt, rotation=90, ha="left", va="top", fontsize=5.5, color=INK,
                        transform=offset_copy(ax.transData, ax.figure, x=1.5, y=-1, units="points"))
                clipped.append(f"{b} {m} median {med:.4g} max {hi:.4g}")
    ax.set_yscale("log")
    ax.set_ylim(bottom, TOP)
    ticks = [t for t in (0.6, 0.8, 1, 1.5, 2, 3, 5, 10, 20) if t >= bottom]
    ax.set_yticks(ticks, [f"{t:g}" for t in ticks])
    ax.axhline(1.0, color=INK, lw=0.6, ls=(0, (4, 2)), zorder=1)
    ax.set_xlim(-0.5, len(groups) - 0.5)
    ax.set_xticks(range(len(groups)), groups)
    ax.tick_params(axis="x", length=0)
    for g in range(1, len(groups)):
        ax.axvline(g - 0.5, color=GRID, lw=0.5, zorder=0)
    ax.grid(True, axis="y", which="major", lw=0.3, color=GRID, zorder=0)
    ax.set_ylabel("Tightness (estimate / reference)")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    return clipped


def legend(fig):
    h = [Line2D([], [], ls="none", label=m, **marker_kw(m, ms=4.2)) for m in METHODS]
    h = [x for pair in zip(h[:5], h[5:]) for x in pair]     # columns fill first, so end-to-end is the top row
    fig.legend(handles=h, loc="upper center", ncol=5, frameon=False, fontsize=7, handletextpad=0.3,
               columnspacing=1.6, borderaxespad=0.2)


def draw(data, groups, bottom, size, top_frac, out):
    rc()
    fig, ax = plt.subplots(figsize=size)
    clipped = panel(ax, data, groups, bottom)
    legend(fig)
    fig.tight_layout(pad=0.3, rect=(0, 0, 1, top_frac))
    fig.savefig(out)
    fig.savefig(out.replace(".pdf", ".png"), dpi=150)
    print(f"wrote {out}" + "".join(f"\n  cut at {TOP:g}: {c}" for c in clipped))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bench", default="results/estimates")
    ap.add_argument("--autoware", default="results/estimates_autoware_warm1")
    ap.add_argument("--outdir", default="results/figs")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    draw(load(a.bench, a.bench, BENCHES), BENCHES, 0.8, (7.16, 2.6), 0.86,
         os.path.join(a.outdir, "benchmarks_tightness.pdf"))
    draw(load(a.autoware, a.autoware, CBS), CBS, 0.6, (7.16, 2.4), 0.85,
         os.path.join(a.outdir, "autoware_tightness.pdf"))


if __name__ == "__main__":
    main()
