#!/usr/bin/env python3
"""Values of the revised paper that the other tables do not hold, from the stored estimates and traces.

    .venv/bin/python tools/paper_tables.py [--out results/tables]

paper_extra.md  one section per value group: the 400 windows of the copula-based methods, paired comparisons,
                the dependence effect, the cb7 marker loop, E2-14 iteration times, X2 per-window exceedance,
                the loop rules of fine bsort100, repeated calls, the SMI exclusion, Autoware tails and analysis time
tau.md          Kendall's tau between the parts of every composed node (CHB-COP meta)
tailid_bm.md    TailID scenarios of E2E-EVT-PoT and of the EVT-COP leaves, E2E-EVT-BM block sizes

Only the five loop leaves of the cb7 and E2-14 sections are recomputed (Algorithm 1 on the per-run average
iteration, production code and seeds, about 10 s each); everything else is read from results/ and the traces.
Run from the repository root.
"""
import argparse
import json
import math
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from estimation import tree  # noqa: E402
from estimation.data import Bench  # noqa: E402
from ipoint_schema import Schema  # noqa: E402  (on sys.path through estimation.data)
from multiwindow_table import BENCHES, cp, load, pair_row, tight  # noqa: E402
from tables import METHODS, QP, md, tail_stats  # noqa: E402
import x2_summary  # noqa: E402

EST, AW_EST, FINE_EST = "results/estimates", "results/estimates_autoware_warm1", "results/estimates_fine"
TRACES, AW_TRACES = "ipoint/traces_full", "ipoint/autoware/traces/autoware/bench_warm1"
X2_TRACES, X2_JSON = "ipoint/autoware/traces/x2_queuefull/bench_warm1", "results/x2/x2_cb1.json"
E214 = {"qsort-exam": ("results/e214/rand", "results/e214/killer", "sort.L1.body"),
        "select": ("results/e214/select_rand", "results/e214/select_killer", "select.L1.body")}
REPEATED = (("cb4", AW_TRACES, "Controller::publishProcessingTime"), ("st", TRACES, "Calc_Var_Stddev"))
CB7_LOOP = "NDTScanMatcher::publish_marker.L1"
CBS = [f"cb{i}" for i in range(1, 8)]
P4, P5, P6 = "0.0001", "1e-05", "1e-06"
COPULA = ("CHB-COP", "MEMIK-COP", "EVT-COP")
TMAX = "training max"            # pseudo-method: the largest SMI-censored run of the training window
PAIR_HEAD = ("| A vs B | windows | A only | B only | McNemar p | median A/B | Wilcoxon p |\n"
             "|---|---|---|---|---|---|---|\n")


def vals(dataset, m, p):
    """Tightness of m at p over every window of {bench: {window: entry}} that has an estimate."""
    return np.array([t for wins in dataset.values() for e in wins.values() if (t := tight(e, m, p)) is not None])


def ratios(wins, a, b, p=P4):
    """{window: tightness of a / tightness of b} over the windows where both have an estimate."""
    return {w: ta / tb for w, e in wins.items()
            if (ta := tight(e, a, p)) is not None and (tb := tight(e, b, p)) is not None}


def section(title, desc, body):
    return f"## {title}\n\n{desc}\n\n{body}\n"


def fmt(v, d=3):
    return "-" if v is None else f"{v:.{d}f}"


# ------------------------------------------------------------ benchmarks: windows, pairs, dependence

def add_training_max(data):
    """Store the training-window maximum as a pseudo-method: the largest run of the window after the SMI
    exclusion of the reference (Bench.e2e_window, the estimators' own input) over the stored reference."""
    for b, wins in data.items():
        bench = Bench(TRACES, b)
        ref = json.load(open(os.path.join(EST, f"{b}.json")))["references"]["censored"]
        assert ref == {str(p): v for p, v in bench.references(tree.P_EVAL)["censored"].items()}, b
        for e in wins.values():
            x = bench.e2e_window(*e["runs"])
            assert len(x) == e["n_train"], b
            e[TMAX] = {"tightness": {p: float(x.max()) / r for p, r in ref.items()}}


def root_parts(b, wins):
    """Parts of the root of the CHB-COP composition tree (1 for a program of one unit)."""
    entry = Schema.from_json(os.path.join(TRACES, b, "schema_timing.json")).entry_function
    meta = wins["0"]["CHB-COP"]["meta"]
    return len(meta[entry]["parts"]) if "parts" in meta.get(entry, {}) else 1


def common_windows(data, com):
    rows = []
    for m in METHODS + [TMAX]:
        v4, v5 = vals(com, m, P4), vals(com, m, P5)
        rows.append([m, f"{int((v4 < 1).sum())}/{len(v4)}", f"{np.median(v4):.3f}", f"{np.quantile(v4, 0.1):.3f}",
                     f"{np.quantile(v4, 0.9):.3f}", f"{int((v5 < 1).sum())}/{len(v5)}", f"{np.median(v5):.3f}"])
    t1 = md(["method", "unsafe 1e-4", "median 1e-4", "10 % point 1e-4", "90 % point 1e-4", "unsafe 1e-5",
             "median 1e-5"], rows)
    rows = []
    n_train = [e["n_train"] for wins in data.values() for e in wins.values()]
    for p in (P4, P5, P6):
        v = vals(data, TMAX, p)
        k = int((v < 1).sum())
        ci = cp(k, len(v))
        rows.append([p, f"{k}/{len(v)}", f"{100 * k / len(v):.1f} [{100 * ci.low:.1f}, {100 * ci.high:.1f}]",
                     f"{100 * np.mean([(1 - float(p)) ** n for n in n_train]):.1f}", f"{np.median(v):.3f}"])
    t2 = md(["p", "unsafe windows", "unsafe % [95 % Clopper-Pearson]", "IID expectation (1-p)^n %",
             "median tightness"], rows)
    rows = []
    for m in METHODS:
        v = vals(data, m, P4)
        rows.append([m, len(v), f"{np.quantile(v, 0.1):.3f}", f"{np.quantile(v, 0.9):.3f}"])
    t3 = md(["method", "windows", "10 % point 1e-4", "90 % point 1e-4"], rows)
    return section(
        "Common windows of the copula-based methods (02 §2)",
        f"The {sum(map(len, com.values()))} windows where CHB-COP, MEMIK-COP and EVT-COP have an estimate (windows "
        "0-49 of seven kernels, 0-9 of the five R-vine kernels). Per method: unsafe windows (tightness < 1) / "
        "windows with an estimate (E2E-EVT-BM counts only the windows where a block size was accepted), median, "
        "and 10 % and 90 % points (numpy linear) of the tightness. 'training max' is the largest run of the "
        "training window after the SMI exclusion of the reference, over the reference. Sources: "
        f"{EST}/*.json, {TRACES}/*/parsed.",
        t1 + "\nCHB-COP vs E2E-MEMIK on these windows at p = 1e-4:\n\n" + PAIR_HEAD
        + pair_row(com, "CHB-COP", "E2E-MEMIK", P4) + "\n\nTraining-window maximum over all 600 windows (the "
        "IID expectation is the probability that none of the n training runs reaches the reference quantile, "
        "averaged over the windows):\n\n" + t2 + "\n10 % and 90 % points over all windows of each method (600, "
        "400 for the copula-based methods):\n\n" + t3)


def one_only(dataset, a, b, p=P4):
    rows = [[bench, w, f"{ta:.4f}", f"{tb:.4f}", f"{ta / tb:.3f}"]
            for bench, wins in dataset.items() for w, e in wins.items()
            if (ta := tight(e, a, p)) is not None and (tb := tight(e, b, p)) is not None and (ta < 1) != (tb < 1)]
    return md(["bench", "window", a, b, f"{a}/{b}"], rows)


def pairs(com, parts):
    small = {b: com[b] for b in BENCHES if parts[b] <= 2}
    large = {b: com[b] for b in BENCHES if parts[b] > 2}
    t1 = PAIR_HEAD + "\n".join([
        pair_row(com, "CHB-COMONO", "CHB-COP", P4),
        pair_row(large, "CHB-COP", "E2E-CHB", P4).replace("|", f"| > 2 parts ({len(large)} kernels):", 1),
        pair_row(small, "CHB-COP", "E2E-CHB", P4).replace("|", f"| <= 2 parts ({len(small)} kernels):", 1)]) + "\n"
    rows = []
    for b in BENCHES:
        r = np.array(list(ratios(com[b], "CHB-COP", "E2E-CHB").values()))
        rows.append([b, parts[b], len(r), f"{np.median(r):.3f}", f"{r.min():.3f}", f"{r.max():.3f}"])
    r = np.array([x for b in small for x in ratios(com[b], "CHB-COP", "E2E-CHB").values()])
    rows.append([f"pooled <= 2 parts ({', '.join(small)})", "", len(r), f"{np.median(r):.3f}", f"{r.min():.3f}",
                 f"{r.max():.3f}"])
    t2 = md(["bench", "root parts", "windows", "median", "min", "max"], rows)
    return section(
        "Paired comparisons (02 §2)",
        "Windows unsafe for one method only, exact McNemar test, median tightness ratio and Wilcoxon test (as in "
        "multiwindow.md) at p = 1e-4 on the common windows; the kernels are grouped by the number of parts of the "
        f"root of their composition tree (CHB-COP meta). Sources: {EST}/*.json.",
        t1 + "\nWindows unsafe for one method only:\n\n" + one_only(com, "CHB-COMONO", "CHB-COP")
        + "\n" + one_only(com, "CHB-COP", "E2E-CHB") + "\nCHB-COP / E2E-CHB per window at p = 1e-4:\n\n" + t2)


def dependence(data, com, parts):
    rows, pooled2, cop_ind = [], {}, {}
    for b in BENCHES:
        r = ratios(com[b], "CHB-COMONO", "CHB-COP")
        d = ratios(com[b], "CHB-COP", "CHB-IND")
        cop_ind |= {(b, w): v for w, v in d.items()}
        if parts[b] == 2:
            pooled2 |= {(b, w): v for w, v in r.items()}
        wr, wd = max(r, key=r.get), max(d, key=d.get)
        rows.append([b, parts[b], len(r), f"{np.median(list(r.values())):.2f}", f"{min(r.values()):.2f}",
                     f"{r[wr]:.2f} (w{wr})", f"{100 * (d['0'] - 1):+.1f}", f"{100 * (min(d.values()) - 1):+.1f}",
                     f"{100 * (d[wd] - 1):+.1f} (w{wd})"])
    k2, kd = max(pooled2, key=pooled2.get), (min(cop_ind, key=cop_ind.get), max(cop_ind, key=cop_ind.get))
    rows.append(["pooled", "", "", "", "", "", "", f"{100 * (cop_ind[kd[0]] - 1):+.1f} ({kd[0][0]} w{kd[0][1]})",
                 f"{100 * (cop_ind[kd[1]] - 1):+.1f} ({kd[1][0]} w{kd[1][1]})"])
    t1 = md(["bench", "root parts", "windows", "COMONO/COP median", "min", "max", "COP/IND-1 % w0", "min", "max"], rows)
    v2 = np.array(list(pooled2.values()))
    nd, nd50 = com["ndes"], data["ndes"]
    rn = np.array(list(ratios(nd, "CHB-COMONO", "CHB-COP").values()))
    lines = [f"Two-part kernels pooled ({len(v2)} windows): CHB-COMONO/CHB-COP median {np.median(v2):.3f}, "
             f"max {pooled2[k2]:.3f} ({k2[0]} w{k2[1]}).",
             f"ndes windows 0-9: mean tightness CHB-COMONO {vals({'ndes': nd}, 'CHB-COMONO', P4).mean():.3f}, CHB-COP "
             f"{vals({'ndes': nd}, 'CHB-COP', P4).mean():.3f}; ratio per window {rn.min():.2f}-{rn.max():.2f} (median "
             f"{np.median(rn):.2f}); CHB-COMONO mean over all {len(nd50)} windows "
             f"{vals({'ndes': nd50}, 'CHB-COMONO', P4).mean():.3f}."]
    st, st10 = data["st"], com["st"]
    rows = []
    for p in (P5, P6):
        ind = {w: tight(e, "CHB-IND", p) for w, e in st.items()}
        bad = [w for w, t in ind.items() if t < 1]
        rows.append([p, f"{len(bad)}/{len(ind)}", f"{min(ind.values()):.3f}",
                     ", ".join(w for w in bad if int(w) < 10) or "none", f"{ind['4']:.3f}",
                     f"{tight(st['4'], 'CHB-COP', p):.3f}", f"{int((vals({'st': st10}, 'CHB-COP', p) < 1).sum())}/{len(st10)}",
                     f"{int((vals({'st': st}, 'CHB-COMONO', p) < 1).sum())}/{len(st)}"])
    t2 = md(["p", "CHB-IND unsafe", "CHB-IND min", "CHB-IND unsafe in w0-9", "CHB-IND w4", "CHB-COP w4",
             "CHB-COP unsafe (w0-9)", "CHB-COMONO unsafe"], rows)
    return section(
        "Dependence effect (02 §2)",
        "Per kernel over the common windows at p = 1e-4: CHB-COMONO/CHB-COP (the window of the maximum in "
        "brackets) and the relative difference CHB-COP/CHB-IND - 1 in % (window 0, minimum and maximum; the pooled "
        f"row is over all {len(cop_ind)} windows). Sources: {EST}/*.json.",
        t1 + "\n" + "\n\n".join(lines) + "\n\nst in the extrapolation region (CHB-IND over its 50 windows):\n\n" + t2)


# ------------------------------------------------------------ Kendall's tau (tau.md)

def tau_pairs(meta):
    """(node, part, part, tau, independence rejected) of the first-tree edges of every R-vine node and of every
    two-part node of a CHB-COP meta; the pre-test rejects independence at p-value < 0.05 (copula/select.py)."""
    out = []
    for uid, m in meta.items():
        if "edges" in m:
            out += [(uid, *sorted(m["parts"][i - 1] for i in e["conditioned"]), e["tau"], not e["independent_by_test"])
                    for e in m["edges"] if e["tree"] == 1]
        elif "tau" in m:
            out.append((uid, *sorted(m["parts"]), m["tau"], m["indep_pvalue"] < 0.05))
    return out


def pair_name(key):
    node, a, b = key
    return f"{node}: {a} / {b}"


def tau_table(data, aw):
    rows, strong = [], []
    for b, wins in data.items():
        per_w = {w: tau_pairs(e["CHB-COP"]["meta"]) for w, e in wins.items() if "CHB-COP" in e}
        flat = [(w, x) for w, xs in per_w.items() for x in xs]
        if not flat:
            rows.append([b, len(per_w), 0] + ["-"] * 5 + ["single unit, no composition"])
            continue
        by_pair = {}
        for w, x in flat:
            by_pair.setdefault(x[:3], {})[w] = x[3]
        absmax = {k: max(map(abs, v.values())) for k, v in by_pair.items()}
        top = max(absmax, key=absmax.get)
        wmax, xmax = max(flat, key=lambda wx: abs(wx[1][3]))
        counts = sorted({len(xs) for xs in per_w.values()})
        rows.append([b, len(per_w), "-".join(map(str, (counts[0], counts[-1]) if len(counts) > 1 else counts)),
                     f"{np.median([abs(x[3]) for _, x in flat]):.3f}", f"{abs(xmax[3]):.3f} (w{wmax})",
                     f"{max(abs(x[3]) for x in per_w['0']):.3f}",
                     f"{pair_name(top)} ({'+' if max(by_pair[top].values(), key=abs) > 0 else '-'})",
                     f"{min(by_pair[top].values()):+.2f} to {max(by_pair[top].values()):+.2f}",
                     f"{100 * np.mean([x[4] for _, x in flat]):.0f} %"])
        strong += [[b, pair_name(k), len(by_pair[k]), f"{min(by_pair[k].values()):+.3f}",
                    f"{max(by_pair[k].values()):+.3f}"] for k in sorted(absmax, key=absmax.get, reverse=True)
                   if absmax[k] >= 0.1]
    t1 = md(["kernel", "windows", "pairs per window", "median abs tau", "max abs tau (window)", "max abs tau w0",
             "strongest pair (sign)", "its tau over windows", "independence rejected"], rows)
    t2 = md(["kernel", "pair", "windows", "min tau", "max tau"], strong)
    rows = []
    for cb in CBS:
        xs = tau_pairs(aw[cb]["CHB-COP"]["meta"])
        if not xs:
            rows.append([cb, 0, "-", "-", "single unit, no composition"])
            continue
        top = max(xs, key=lambda x: abs(x[3]))
        rows.append([cb, len(xs), f"{np.median([abs(x[3]) for x in xs]):.3f}", f"{top[3]:+.3f}", pair_name(top[:3])])
    t3 = md(["callback", "pairs", "median abs tau", "tau of the strongest pair", "strongest pair"], rows)
    return ("# Dependence between units: Kendall's tau\n\n"
            "Kendall's tau of the pairs that the CHB-COP composition couples directly, i.e. the first-tree edges of "
            "every R-vine node and every two-part node, as stored in the CHB-COP meta of the estimate JSONs (pairs of "
            "deeper trees are conditional and left out). Independence rejected: share of these pairs whose Kendall-tau "
            f"independence pre-test rejected at 0.05. Sources: {EST}/*.json (all windows with CHB-COP: 0-49, or 0-9 "
            f"for the R-vine kernels), {AW_EST}/*.json (window 0).\n\n## Benchmarks\n\n" + t1
            + "\nPairs whose abs tau reaches 0.1 in some window (signed range over the windows where the pair is "
            "coupled directly):\n\n" + t2 + "\n## Autoware, window 0\n\n" + t3)


# ------------------------------------------------------------ TailID and block maxima (tailid_bm.md)

def leaf_fits(meta):
    """EVT leaves of a decomposed-method meta (every pot_fit records its TailID scenario)."""
    return [m for m in meta.values() if "tailid_scenario" in m]


def tailid_counts(metas):
    sc = Counter(m["tailid_scenario"] for m in metas)
    few = sum("fallback" in m for m in metas)
    n = len(metas)
    return [n, sc[1], sc[2], sc[3], few, f"{100 * sc[3] / n:.1f}", f"{100 * (sc[3] + few) / n:.1f}"]


def tailid_bm(data, aw, awall):
    head = ["fits", "scenario 1", "scenario 2", "scenario 3", "< 10 exceedances", "scenario 3 %", "ECDF %"]
    rows, alle = [], []
    for b, wins in list(data.items()) + list(awall.items()):
        ms = [e["E2E-EVT-PoT"]["meta"] for e in wins.values()]
        xi = [m["xi"] for m in ms if "xi" in m]
        rows.append([b] + tailid_counts(ms) + [f"{np.median(xi):.2f}" if xi else "-"])
        if b in awall:
            alle += ms
    xi = [m["xi"] for m in alle if "xi" in m]
    rows.append(["Autoware"] + tailid_counts(alle) + [f"{np.median(xi):.2f}"])
    t1 = md(["program"] + head + ["median xi (GPD windows)"], rows)
    rows, allb, alla = [], [], []
    for b, wins in data.items():
        ms = [m for e in wins.values() if "EVT-COP" in e for m in leaf_fits(e["EVT-COP"]["meta"])]
        allb += ms
        rows.append([b] + tailid_counts(ms))
    rows.append(["benchmarks"] + tailid_counts(allb))
    for cb in CBS:
        ms = leaf_fits(aw[cb]["EVT-COP"]["meta"])
        alla += ms
        rows.append([f"{cb} (w0)"] + tailid_counts(ms))
    rows.append(["Autoware w0"] + tailid_counts(alla))
    t2 = md(["program"] + head, rows)
    rows = []
    for group in (data, awall):
        tot = Counter()
        for b, wins in group.items():
            es = [e for e in wins.values() if "E2E-EVT-BM" in e]
            fitted = sum(tight(e, "E2E-EVT-BM", P4) is not None for e in es)
            acc = Counter(B for e in es for B, v in e["E2E-EVT-BM"]["meta"]["blocks"].items() if v["accepted"])
            tot.update(acc)
            tot.update(fitted=fitted, windows=len(es))
            rows.append([b, f"{fitted}/{len(es)}"] + [acc[B] for B in ("10", "20", "50", "100")])
        rows.append(["all" if group is data else "Autoware", f"{tot['fitted']}/{tot['windows']}"]
                    + [tot[B] for B in ("10", "20", "50", "100")])
    t3 = md(["program", "windows with an estimate", "B=10 accepted", "B=20", "B=50", "B=100"], rows)
    return ("# TailID scenarios and block maxima\n\n"
            "TailID scenario of every PoT fit (meta `tailid_scenario`: 1 keeps the EQMAE threshold, 2 moves it to the "
            "first ID-sensitive point, 3 falls back to the ECDF). '< 10 exceedances': scenario 1 or 2 whose "
            "threshold leaves fewer than 10 exceedances, which also falls back to the ECDF (meta `fallback`, "
            "estimation/evt.py). ECDF %: both fallbacks. Sources: "
            f"{EST}/*.json, {AW_EST}/*.json.\n\n## E2E-EVT-PoT (benchmarks, 50 windows each; Autoware, all windows)\n\n"
            + t1
            + "\n## EVT-COP leaves (benchmarks: windows 0-49, or 0-9 for the R-vine kernels; Autoware: window 0)\n\n"
            + t2 + "\n## E2E-EVT-BM (benchmarks, 50 windows each; Autoware, all windows)\n\nA window has an estimate when at least one block "
            "size B passes Q-Q R^2 >= 0.99 (the estimate is the median over the accepted B); per B, the windows in "
            "which it was accepted.\n\n" + t3)


# ------------------------------------------------------------ loops: cb7, E2-14, fine bsort100

def unit_bound(bench, body, w, name):
    """Algorithm 1 bound at 1e-4 on the per-run average iteration of window w and the loop part (bound x it),
    through tree.loop_marginal with the production leaf and seed; returns (part, per-run column, leaf meta)."""
    lo, hi = bench.window_bounds(w)
    sink = {}
    part, col = tree.loop_marginal(bench, body, bench.loop_of_body(body).bound, lo, hi,
                                   tree.make_leaf("CHB-COP", name, w), sink, "avg")
    return part, col, sink[f"{body}.avg"]


def cb7_marker():
    b = Bench(AW_TRACES, "cb7")
    body = CB7_LOOP + ".body"
    bound, n, us = b.loop_of_body(body).bound, len(b.e2e_all), b.tick_ns / 1e3
    assert b.per_run_counts(CB7_LOOP, 0, n).max() == 1           # one loop entry per invocation
    u = b.units[body]
    assert (np.diff(u.runs) >= 0).all()
    it = np.arange(len(u.runs)) - np.searchsorted(u.runs, u.runs)    # iteration number in its run, from 0
    cnt = b.per_run_counts(body, 0, n)
    loop_t, body_t = b.per_run_totals(CB7_LOOP, 0, n), b.per_run_totals(body, 0, n)
    part, col, leaf = unit_bound(b, body, 0, "cb7")
    stored = json.load(open(os.path.join(AW_EST, "cb7.json")))["windows"]["0"]["CHB-COP"]["meta"][f"{body}.avg"]
    assert leaf["choice"][1e-4] == stored["choice"][P4] and stored["bound"] == bound
    rule = part.pwcet[1e-4]
    ref = b.references([1e-4])["censored"][1e-4]
    q_loop, q_body = (np.quantile(t, 1 - 1e-4, method="higher") for t in (loop_t, body_t))
    r_max = int(b.window_clean_runs(*b.window_bounds(0))[np.argmax(col)])
    big = u.vals * b.tick_ns > 100e3
    rows = [["median iteration time, iterations 1-8 (us)",
             ", ".join(f"{np.median(u.vals[it == i]) * us:.2f}" for i in range(8))],
            ["iterations per invocation (all invocations), static bound", f"{cnt.min()}-{cnt.max()} ({n} "
             f"invocations), bound {bound}"],
            ["Algorithm 1 bound on the per-run average at 1e-4, window 0 (d, k)",
             f"{rule / bound * us:.1f} us (d = {leaf['choice'][1e-4]['d']:.0f}, k = {leaf['choice'][1e-4]['k']})"],
            ["window-0 maximum of the per-run average; bound / maximum",
             f"{col.max() * us:.1f} us; {rule / bound / col.max():.2f}"],
            ["run of that maximum: iterations, first iteration", f"run {r_max}: {cnt[r_max]}, "
             f"{u.vals[(u.runs == r_max) & (it == 0)][0] * us:.1f} us"],
            ["loop rule value (bound x Algorithm 1 bound)", f"{rule * us / 1e3:.2f} ms"],
            ["1e-4 quantile of the loop time over all invocations; rule / quantile (iterations only)",
             f"{q_loop * us / 1e3:.3f} ms; {rule / q_loop:.1f} ({q_body * us / 1e3:.3f} ms; {rule / q_body:.1f})"],
            ["callback reference at 1e-4; rule / reference", f"{ref * us / 1e3:.2f} ms; {100 * rule / ref:.1f} %"],
            ["iterations above 100 us (of them the first or second)", f"{big.sum()} ({(big & (it < 2)).sum()})"],
            ["loop time / callback time, median over invocations (iterations only)",
             f"{100 * np.median(loop_t / b.e2e_all):.3f} % ({100 * np.median(body_t / b.e2e_all):.3f} %)"]]
    return section(
        "cb7 marker loop (02 §3.1)",
        f"Loop `{CB7_LOOP}` of cb7 (steady state, every invocation, window 0 for the bound). Loop time: the "
        "interval of the loop unit (iterations and loop control); 'iterations only' sums the iteration bodies, "
        "which is what the rule bounds. The bound is recomputed with tree.loop_marginal and the production seed, "
        f"and its (d, k) equals the stored CHB-COP meta. Sources: {AW_TRACES}/cb7, {AW_EST}/cb7.json.",
        md(["value", "cb7"], rows))


def per_run_avg(b, body, lo, hi):
    """Per-run average iteration time (ticks) and iteration count over the non-censored runs of [lo, hi) that
    iterate (the sample of the loop leaf, tree.loop_marginal)."""
    clean = b.window_clean_runs(lo, hi)
    c, t = b.per_run_counts(body, lo, hi)[clean], b.per_run_totals(body, lo, hi)[clean]
    return t[c > 0] / c[c > 0], c[c > 0]


def e214(p=1e-4):
    rows, crows = [], []
    for name, (rdir, kdir, body) in E214.items():
        rb, kb = Bench(rdir, name), Bench(kdir, name)
        ns = rb.tick_ns
        ka, kc = per_run_avg(kb, body, 0, len(kb.e2e_all))
        kmed = float(np.median(kb.e2e_all[kb._clean_e2e_mask]))
        rmed = float(np.median(rb.e2e_all[rb._clean_e2e_mask]))
        rows.append([name, "killer", len(ka), f"{np.median(ka) * ns:.1f} ({ka.max() * ns:.1f})",
                     f"{np.median(kc):.0f} ({kc.min()}-{kc.max()})", "", "", f"{kmed / rmed:.2f}"])
        for w in (0, 1):
            ra, rc = per_run_avg(rb, body, *rb.window_bounds(w))
            part, _, _ = unit_bound(rb, body, w, name)
            ub = part.pwcet[1e-4] / rb.loop_of_body(body).bound
            rows.append([name, f"random w{w}", len(ra), f"{np.median(ra) * ns:.1f} ({ra.max() * ns:.1f})",
                         f"{np.median(rc):.0f} ({rc.min()}-{rc.max()})", f"{ub * ns:.1f}",
                         f"{ub / np.median(ka):.2f}", ""])
            x = rb.e2e_window(*rb.window_bounds(w))
            crows.append([name, w, f"{kmed / x.mean():.3f}", f"{1 + x.std(ddof=1) / x.mean() * math.sqrt((1 - p) / p):.3f}"])
    return section(
        "E2-14: iteration times of the killer and random inputs (02 §4.1)",
        "Per-run average iteration time in ns, median (max), and iterations per run, median (min-max), over the "
        "SMI-censored runs (killer: all runs; random: training windows 0 and 1). Unit bound: Algorithm 1 at 1e-4 on "
        "the per-run average of the window (tree.loop_marginal, production seed); 'bound / killer' divides it by the "
        "killer's median per-run average. Killer/random E2E: medians of all SMI-censored runs. Sources: "
        "results/e214/{rand,killer,select_rand,select_killer}.",
        md(["kernel", "input", "runs", "per-run average ns", "iterations per run", "unit bound 1e-4 ns",
            "bound / killer", "killer / random E2E median"], rows)
        + "\nCantelli break check at p = 1e-4: the killer median exceeds the Cantelli plug-in bound (mean + SD "
        "sqrt((1-p)/p) of the training window) iff killer median / mean > 1 + CV sqrt((1-p)/p):\n\n"
        + md(["kernel", "window", "killer median / window mean", "1 + CV sqrt((1-p)/p)"], crows))


def fine():
    wins = load(FINE_EST, FINE_EST, ["bsort100"])["bsort100"]
    rows = []
    for p in (P4, P5, P6):
        r = np.array(list(ratios(wins, "CHB-COP@max", "CHB-COP", p).values()))
        rows.append([p, len(r), f"{np.median(r):.1f}", f"{r.min():.1f}-{r.max():.1f}"])
    return section(
        "Fine bsort100: loop rules (02 §5)",
        f"CHB-COP@max / CHB-COP (per-run slowest iteration vs per-run average rule) per window. Source: {FINE_EST}/bsort100.json.",
        md(["p", "windows", "median", "min-max"], rows))


# ------------------------------------------------------------ X2, repeated calls, Autoware

def x2():
    qb = Bench(X2_TRACES, "cb1")
    d = json.load(open(X2_JSON))
    n = len(qb.e2e_all)
    full = np.sort(qb.e2e_all[(qb.per_run_counts(x2_summary.POSE, 0, n) == 5) & qb._clean_e2e_mask])
    kmed = float(np.median(full))
    methods = sorted({k.split("/", 1)[1] for k in d if k.startswith("w")}, key=lambda m: (not m.startswith("E2E"), m))
    wins = sorted({k.split("/")[0] for k in d if k.startswith("w")})
    rows = []
    for m in methods:
        cells = []
        for p in (P4, P5):
            exc = np.array([1 - np.searchsorted(full, d[f"{w}/{m}"]["vs_full_median"][p] * kmed, side="right")
                            / len(full) for w in wins if f"{w}/{m}" in d])
            cells.append(f"{exc.min():.2%}, {np.median(exc):.2%}, {exc.max():.2%}")
        rows.append([m] + cells)
    return section(
        "X2: per-window exceedance of the queue-full invocations (02 §4.2)",
        f"Share of the {len(full)} queue-full cb1 invocations (pose loop at its bound 5) above the estimate of each "
        f"training window ({len(wins)} windows), minimum, median and maximum over the windows, as in "
        f"tools/x2_summary.py (resolution {100 / len(full):.3f} %). Sources: {X2_JSON}, {X2_TRACES}.",
        md(["method", "p = 1e-4", "p = 1e-5"], rows))


def repeated_calls(p=1e-3):
    rows = []
    for name, traces, uid in REPEATED:
        b = Bench(traces, name)
        n, us = len(b.e2e_all), b.tick_ns / 1e3
        u = b.units[uid]
        cnt = b.per_run_counts(uid, 0, n)
        sel = b._clean_e2e_mask & (cnt > 0)
        c = int(cnt[sel].max())
        q1 = np.quantile(u.vals[b.clean_run_mask(u.runs)], 1 - p, method="higher")
        qt = np.quantile(b.per_run_totals(uid, 0, n)[sel], 1 - p, method="higher")
        rows.append([name, f"`{uid}`", int(sel.sum()), f"{cnt[sel].min()}-{c}", f"{q1 * us:.3f}",
                     f"{c * q1 * us:.3f}", f"{qt * us:.3f}", f"{c * q1 / qt:.2f}"])
    return section(
        "Repeated calls (02 §1)",
        f"c times the (1-p)-quantile of one call against the (1-p)-quantile of the per-run total of the c calls, "
        f"p = {p:g}, empirical quantiles (method 'higher', as the references) over all runs that call the function "
        f"(benchmarks SMI-censored), in us. Sources: {AW_TRACES}/cb4, {TRACES}/st.",
        md(["program", "function", "runs", "calls per run", "one call", "c x one call", "per-run total",
            "ratio"], rows))


def smi_references():
    rows = []
    for b in BENCHES:
        r = json.load(open(os.path.join(EST, f"{b}.json")))["references"]
        rows.append([b] + [fmt(float(r["uncensored"][p]) / float(r["censored"][p])) for p in (P4, P5, P6)])
    return section(
        "SMI exclusion and the references (02 §1)",
        "Reference without the SMI exclusion over the reference with it (empirical quantile of all 1e7 runs). "
        f"Source: {EST}/*.json (field `references`).",
        md(["kernel", "p=1e-4", "p=1e-5", "p=1e-6"], rows))


def aw_tails():
    rows = []
    for cb in CBS:
        b = Bench(AW_TRACES, cb)
        q, kurt, xi, n = tail_stats(b.e2e_all[b._clean_e2e_mask])
        rows.append([cb, "E2E (steady state)", n] + [fmt(q[p]) for p in QP] + [fmt(kurt, 1), fmt(xi, 2)])
    return section(
        "Autoware tails (02 §9)",
        "Same columns and definitions as tails.md (tools/tables.py tail_stats): quantile at 1-p over the median "
        "(when p*n >= 9), excess kurtosis, GPD shape above the 0.99 quantile; all steady-state invocations, no SMI "
        f"censoring for Autoware. Source: {AW_TRACES}.",
        md(["callback", "series", "n", "q1e-3/med", "q1e-4/med", "q1e-5/med", "q1e-6/med", "ex. kurtosis",
            "xi(0.99)"], rows))


def aw_cost(aw):
    rows = [[cb, f"{aw[cb]['CHB-COP']['seconds']:.0f}"] for cb in CBS]
    return section(
        "Autoware analysis time of CHB-COP (02 §9)",
        f"Field `seconds` of the CHB-COP entry, window 0, one core. Source: {AW_EST}/*.json.",
        md(["callback", "CHB-COP seconds"], rows))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="results/tables")
    a = ap.parse_args()
    data = load(EST, EST, BENCHES)
    add_training_max(data)
    com = {b: {w: e for w, e in wins.items() if all(tight(e, m, P4) is not None for m in COPULA)}
           for b, wins in data.items()}
    assert sum(map(len, com.values())) == 400
    parts = {b: root_parts(b, wins) for b, wins in data.items()}
    awall = load(AW_EST, AW_EST, CBS)
    aw = {cb: wins["0"] for cb, wins in awall.items()}
    out = {"paper_extra.md": "# Values of the paper without another table\n\n" + "\n".join([
               common_windows(data, com), pairs(com, parts), dependence(data, com, parts), cb7_marker(),
               e214(), x2(), fine(), repeated_calls(), smi_references(), aw_tails(), aw_cost(aw)]),
           "tau.md": tau_table(data, aw),
           "tailid_bm.md": tailid_bm(data, aw, awall)}
    os.makedirs(a.out, exist_ok=True)
    for name, text in out.items():
        with open(os.path.join(a.out, name), "w") as f:
            f.write(text)
        print(f"== {name}\n{text}")


if __name__ == "__main__":
    main()
