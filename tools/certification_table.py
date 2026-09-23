#!/usr/bin/env python3
"""E2-12 table: certified and plug-in envelopes relative to the empirical quantile.

    .venv/bin/python tools/certification_table.py [--dir results/certification] [--out results/tables/certification.md]
"""
import argparse
import glob
import json
import os

import numpy as np

PS = (1e-2, 1e-3, 1e-4, 1e-5, 10 ** -5.75, 1e-6)   # 10^-5.75 = 1.78e-6 is the last grid point above the n = 9e6 floor
ORDER = ["bsort100", "fir", "matmult", "edn", "ndes", "st", "lms", "prime", "cnt", "ludcmp", "select", "qsort-exam"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default="results/certification")
    ap.add_argument("--out", default="results/tables/certification.md")
    a = ap.parse_args()
    rows = {}
    for path in glob.glob(os.path.join(a.dir, "*.json")):
        c = json.load(open(path))
        p = np.array(c["p"])
        idx = {q: int(np.argmin(np.abs(np.log10(p / q)))) for q in PS}
        emp = np.array(c["empirical_all"])
        rows[c["bench"]] = (c, idx, emp)
    hdr = " | ".join(f"p={q:.3g}" for q in PS)
    lines = []
    for key, title in (("all", "all SMI-censored runs (calibration 10%, moments on the rest)"),
                       ("window0", "training window 0 (1e4 runs)")):
        any_c = next(iter(rows.values()))[0][key]
        lines += [f"\nEnvelope / empirical quantile of all runs, fitted on {title}: n = {any_c['n_main']}, "
                  f"grid {any_c['grid_size']}, alpha {next(iter(rows.values()))[0]['alpha']}, "
                  f"floor 1 - e^-tau = {any_c['floor']:.3g}. Cells: certified (plug-in); inf = below the floor.\n",
                  f"| bench | {hdr} |", "|---|" + "---|" * len(PS)]
        for b in [x for x in ORDER if x in rows]:
            c, idx, emp = rows[b]
            cells = [f"{c[key]['certified'][i] / emp[i]:.3f} ({c[key]['plugin'][i] / emp[i]:.3f})" for i in idx.values()]
            lines.append(f"| {b} | " + " | ".join(cells) + " |")
    text = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
