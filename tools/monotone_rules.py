#!/usr/bin/env python3
"""Candidate monotonization rules for a plug-in bound curve {p: bound} (decision material of 2026-09-23;
the pipeline adopted "hybrid 1e-4", copula.compose.monotone_curve, on the user's decision).

    raw       the per-p values of Algorithm 1 (not monotone: the k ceiling is extrapolated per p)
    runmax    running maximum from the largest p (copula.compose.monotone_curve; conservative,
              but a loose body bound, e.g. Markov's k = 1 at p >= 1e-3, is carried into the tail)
    hybrid    inside [p_top, 1] the running minimum from p_top upward (a bound at a smaller p also
              bounds the quantile at a larger p), below p_top the running maximum from p_top downward
              (extrapolated ceilings never tighten a validated value); p_top = smallest p validated by
              the RESTK bootstrap (1e-6) or the largest one (1e-4)

    .venv/bin/python tools/monotone_rules.py results/synthetic_mono/families.json   # E1-1 table per rule
"""
import json
import sys

import numpy as np

P_EVAL = (1e-3, 1e-4, 1e-5, 1e-6)


def _arrays(pwcet):
    alphas = np.array(sorted(float(a) for a in pwcet), dtype=float)
    return alphas, np.array([pwcet[a] if a in pwcet else pwcet[str(a)] for a in alphas], dtype=float)


def runmax(pwcet):
    alphas, v = _arrays(pwcet)
    return dict(zip(alphas, np.maximum.accumulate(v[::-1])[::-1]))


def hybrid(pwcet, p_top=1e-6):
    alphas, v = _arrays(pwcet)
    out = v.copy()
    body = np.where(alphas >= p_top * (1 - 1e-9))[0]        # ascending p from p_top
    tail = np.where(alphas < p_top * (1 - 1e-9))[0]
    out[body] = np.minimum.accumulate(v[body])
    if len(tail):
        seed = v[body[0]] if len(body) else -np.inf
        out[tail] = np.maximum.accumulate(np.concatenate([[seed], v[tail][::-1]]))[1:][::-1]
    return dict(zip(alphas, out))


RULES = {"raw": lambda c: dict(zip(*_arrays(c))),
         "runmax": runmax,
         "hybrid 1e-6": lambda c: hybrid(c, 1e-6),
         "hybrid 1e-4": lambda c: hybrid(c, 1e-4)}


def main():
    sys.path.insert(0, "tools")
    from synthetic_study import DISTS      # raw_grid holds ratios; the rules act on the bound values
    d = json.load(open(sys.argv[1]))
    res = d["results"]
    truth = {}
    for rule, fn in RULES.items():
        print(f"\n### {rule}: median tightness over {d['reps']} replications [unsafe count]\n")
        for dist in next(iter(res.values())):
            print(f"\n{dist}\n\n| config | " + " | ".join(f"p={p:g}" for p in P_EVAL) + " |\n|---|" + "---|" * len(P_EVAL))
            for cfg in res:
                cells = []
                curves = []
                for r in res[cfg][dist]:
                    for k in r["raw_grid"]:
                        truth.setdefault((dist, float(k)), float(DISTS[dist].isf(float(k))))
                    values = fn({float(k): x * truth[(dist, float(k))] for k, x in r["raw_grid"].items()})
                    curves.append({q: v / truth[(dist, q)] for q, v in values.items()})
                for p in P_EVAL:
                    v = np.array([c[p] for c in curves])
                    fin = v[np.isfinite(v)]
                    cells.append(f"{np.median(fin) if len(fin) else np.inf:.3f} [{int((v < 1).sum())}]")
                print(f"| {cfg} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
