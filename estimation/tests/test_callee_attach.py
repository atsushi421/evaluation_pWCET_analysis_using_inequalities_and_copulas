"""A timed function called from the entry function is composed below it: the entry's self time is
its interval minus the callee's, and the composed parts add up to the end-to-end time of every run."""
import json

import numpy as np

from estimation.data import Bench
from ipoint_schema import Schema, Unit

RUNS = 1000


def test_callee_of_the_entry_is_composed(tmp_path):
    d = tmp_path / "syn"
    u = d / "parsed" / "units"
    u.mkdir(parents=True)
    units = [Unit("main", "function", None, 0, instrumented=True, calls=["f", "f"]),
             Unit("f", "function", None, 0, instrumented=True)]
    Schema("syn.c", "", [], {}, "main", 0, units).to_json(str(d / "schema_timing.json"))
    json.dump({"tick_ns": 1.0}, open(d / "overhead.json", "w"))
    rng = np.random.default_rng(0)
    f_runs = np.repeat(np.arange(RUNS), 2)                       # f is called twice per run
    f_vals = rng.integers(100, 200, size=2 * RUNS)
    main_vals = rng.integers(10, 20, size=RUNS) + np.bincount(f_runs, weights=f_vals).astype(np.int64)
    np.save(d / "parsed" / "e2e_all.npy", main_vals)
    np.save(u / "main.npy", main_vals)
    np.save(u / "main.run.npy", np.arange(RUNS))
    np.save(u / "f.npy", f_vals)
    np.save(u / "f.run.npy", f_runs)
    np.save(u / "f.caller.npy", np.zeros(2 * RUNS, dtype=np.uint16))
    json.dump(["main"], open(u / "f.callers.json", "w"))

    b = Bench(str(tmp_path), "syn")
    assert b.attached_callees == ["f"] and [c.uid for c in b.effective_children("main")] == ["f"]
    composed = b.per_run_totals("main", 0, RUNS, "self") + b.per_run_totals("f", 0, RUNS)
    assert np.array_equal(composed, b.e2e_all) and b.units["main"].self_vals.min() >= 10
