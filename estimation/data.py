"""Loading one benchmark's parsed traces for the estimation pipeline.

Uses the artifacts of ``ipoint/tools/run_campaign.py`` under
``traces/<bench>/``: the pruned timing schema, per-unit instance samples with
their run indices, the end-to-end times of every run, and the SMI censoring
list of ``smi_censor.py`` (runs hit by SMM interrupts are dropped from every
training window and from the reference quantiles; see the paper repo
notes/smi_interference.md).
"""
import json
import os
import sys
from dataclasses import dataclass

import numpy as np

_IPOINT_TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ipoint", "tools")
sys.path.insert(0, _IPOINT_TOOLS)
from ipoint_schema import Schema, Unit  # noqa: E402

WINDOW = 10_000


@dataclass
class UnitData:
    vals: np.ndarray      # ticks per instance, trace order
    runs: np.ndarray      # run index per instance
    self_vals: np.ndarray | None = None


class Bench:
    def __init__(self, traces_dir: str, bench: str):
        self.bench = bench
        self.dir = os.path.join(traces_dir, bench)
        self.schema = Schema.from_json(os.path.join(self.dir, "schema_timing.json"))
        self.by_uid = self.schema.by_uid()
        self.tick_ns = json.load(open(os.path.join(self.dir, "overhead.json")))["tick_ns"]
        parsed = os.path.join(self.dir, "parsed")
        self.e2e_all = np.load(os.path.join(parsed, "e2e_all.npy")).astype(np.float64)
        smi_path = os.path.join(parsed, "smi_runs.npy")
        self.smi_runs = np.load(smi_path) if os.path.exists(smi_path) else np.empty(0, dtype=np.uint64)
        self._clean_e2e_mask = np.ones(len(self.e2e_all), dtype=bool)
        self._clean_e2e_mask[self.smi_runs.astype(np.int64)] = False
        # unit samples exist only for the fully traced runs: the first 1e5 in the first benchmark
        # campaign, every run in traces_full/ and in the merged job-mode traces of Autoware
        meta_path = os.path.join(self.dir, "timing", "meta.json")
        if os.path.exists(meta_path):
            meta = json.load(open(meta_path))
            self.n_traced = int(min(meta["full_trace_runs"], meta["runs"]))
        else:
            self.n_traced = len(self.e2e_all)
        self.units: dict[str, UnitData] = {}
        udir = os.path.join(parsed, "units")
        for u in self.schema.units:
            path = os.path.join(udir, u.uid + ".npy")
            if not (u.instrumented and os.path.exists(path)):
                continue
            vals = np.load(path).astype(np.float64)
            runs = np.load(os.path.join(udir, u.uid + ".run.npy")).astype(np.int64)
            sp = os.path.join(udir, u.uid + ".self.npy")
            self_vals = np.load(sp).astype(np.float64) if os.path.exists(sp) else None
            self.units[u.uid] = UnitData(vals, runs, self_vals)

    # ---------------- windows and censoring

    def window_bounds(self, w: int, size: int = WINDOW, stride: int | None = None) -> tuple[int, int]:
        """Runs [lo, hi) of window w: consecutive windows by default, w * stride with a stride."""
        lo = w * (stride or size)
        hi = lo + size
        if hi > self.n_traced:
            raise ValueError(f"window {w} exceeds the {self.n_traced} fully traced runs")
        return lo, hi

    def clean_run_mask(self, runs: np.ndarray) -> np.ndarray:
        return self._clean_e2e_mask[runs]

    def unit_window(self, uid: str, lo: int, hi: int, what: str = "vals") -> np.ndarray:
        u = self.units[uid]
        m = (u.runs >= lo) & (u.runs < hi) & self.clean_run_mask(u.runs)
        return (u.vals if what == "vals" else u.self_vals)[m]

    def per_run_totals(self, uid: str, lo: int, hi: int, what: str = "vals") -> np.ndarray:
        """Sum per run over [lo, hi); censored runs are dropped by the caller's run mask."""
        u = self.units[uid]
        m = (u.runs >= lo) & (u.runs < hi)
        src = u.vals if what == "vals" else u.self_vals
        return np.bincount(u.runs[m] - lo, weights=src[m], minlength=hi - lo)

    def per_run_counts(self, uid: str, lo: int, hi: int) -> np.ndarray:
        u = self.units[uid]
        m = (u.runs >= lo) & (u.runs < hi)
        return np.bincount(u.runs[m] - lo, minlength=hi - lo)

    def window_clean_runs(self, lo: int, hi: int) -> np.ndarray:
        """Offsets in [0, hi-lo) of the non-censored runs of the window."""
        return np.flatnonzero(self._clean_e2e_mask[lo:hi])

    def e2e_window(self, lo: int, hi: int) -> np.ndarray:
        return self.e2e_all[lo:hi][self._clean_e2e_mask[lo:hi]]

    # ---------------- references

    def references(self, p_list) -> dict:
        clean = self.e2e_all[self._clean_e2e_mask]
        out = {"censored": {}, "uncensored": {}, "n_clean": int(len(clean)),
               "n_censored_runs": int(len(self.smi_runs))}
        for p in p_list:
            out["censored"][p] = float(np.quantile(clean, 1 - p, method="higher"))
            out["uncensored"][p] = float(np.quantile(self.e2e_all, 1 - p, method="higher"))
        return out

    # ---------------- schema navigation

    def effective_children(self, uid: str) -> list[Unit]:
        """Nearest instrumented descendants, not crossing another instrumented unit."""
        out = []
        for c_uid in self.by_uid[uid].children:
            c = self.by_uid[c_uid]
            if c.instrumented and c_uid in self.units:
                out.append(c)
            else:
                out.extend(self.effective_children(c_uid))
        return out

    def branch_of(self, uid: str) -> str:
        """Enclosing branch uid of an alternative (the schema parent chain)."""
        u = self.by_uid[uid]
        while u.kind != "branch":
            u = self.by_uid[u.parent]
        return u.uid

    def loop_of_body(self, uid: str) -> Unit:
        u = self.by_uid[uid]
        parent = self.by_uid[u.parent]
        if parent.kind != "loop":
            raise ValueError(f"{uid}: loop_body whose parent {parent.uid} is not a loop")
        return parent
