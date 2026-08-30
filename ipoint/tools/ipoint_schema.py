#!/usr/bin/env python3
"""Data model of an IPoint timing schema (schema.json) shared by
ipoint_instrument.py and ipoint_parse.py.

A schema is a tree of units:
  function     one per instrumented function definition
  loop         a for/while/do statement (entry/exit around the statement)
  loop_body    the body of a loop (entry/exit inside the body; one pair per
               iteration)
  branch       an if statement; a container without IPoints of its own
  alternative  one path of a branch (then/else); an absent or empty else is a
               single marker IPoint with entry == exit and empty == True

IPoint ids are assigned on the full tree, independently of which units are
instrumented, so schemas produced for the same source under different policies
share their ids.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

TOOL_VERSION = "ipoint_instrument 0.2"
KINDS = ("function", "loop", "loop_body", "branch", "alternative")


@dataclass
class Unit:
    uid: str
    kind: str
    parent: Optional[str]
    depth: int
    line: int = 0
    stmt: str = ""
    entry: Optional[int] = None
    exit: Optional[int] = None
    instrumented: bool = False
    empty: bool = False
    children: List[str] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)
    bound: Optional[int] = None
    bound_source: Optional[str] = None
    loop_var: Optional[str] = None
    job: bool = False           # function whose entry/exit probes delimit a run (IPOINT_JOB_BEGIN/END)
    qualified: Optional[str] = None  # fully qualified C++ name (uid drops the namespaces)

    @property
    def has_ipoints(self) -> bool:
        return self.entry is not None


@dataclass
class Schema:
    source: str
    source_sha256: str
    cflags: List[str]
    policy: Dict
    entry_function: Optional[str]
    max_id: int
    units: List[Unit]
    tool: str = TOOL_VERSION
    lang: str = "c"
    id_base: int = 0            # ids are id_base+1 .. max_id (several schemas can share one process)

    def by_uid(self) -> Dict[str, Unit]:
        return {u.uid: u for u in self.units}

    def functions(self) -> List[Unit]:
        return [u for u in self.units if u.kind == "function"]

    def instrumented_units(self) -> List[Unit]:
        return [u for u in self.units if u.instrumented and u.has_ipoints]

    def entry_unit(self) -> Optional[Unit]:
        if self.entry_function is None:
            return None
        return self.by_uid().get(self.entry_function)

    def id_to_unit(self) -> Dict[int, tuple]:
        """Map ipoint id -> (unit, 'entry'|'exit'|'marker')."""
        m: Dict[int, tuple] = {}
        for u in self.units:
            if u.entry is None:
                continue
            if u.empty or u.entry == u.exit:
                m[u.entry] = (u, "marker")
            else:
                m[u.entry] = (u, "entry")
                m[u.exit] = (u, "exit")
        return m

    def to_json(self, path: str) -> None:
        d = asdict(self)
        with open(path, "w") as f:
            json.dump(d, f, indent=1)
            f.write("\n")

    @staticmethod
    def from_json(path: str) -> "Schema":
        with open(path) as f:
            d = json.load(f)
        units = [Unit(**u) for u in d.pop("units")]
        return Schema(units=units, **d)

    def validate(self) -> List[str]:
        errors: List[str] = []
        by = self.by_uid()
        if len(by) != len(self.units):
            errors.append("duplicate uid")
        ids: Dict[int, str] = {}
        for u in self.units:
            if u.kind not in KINDS:
                errors.append(f"{u.uid}: unknown kind {u.kind}")
            if u.parent is not None and u.parent not in by:
                errors.append(f"{u.uid}: unknown parent {u.parent}")
            if u.parent is not None and u.uid not in by[u.parent].children:
                errors.append(f"{u.uid}: not listed in parent's children")
            for c in u.children:
                if c not in by or by[c].parent != u.uid:
                    errors.append(f"{u.uid}: bad child link {c}")
            if u.kind == "branch":
                if u.entry is not None:
                    errors.append(f"{u.uid}: branch must not carry ipoints")
            elif u.entry is None or u.exit is None:
                errors.append(f"{u.uid}: missing ipoint ids")
            else:
                for i in {u.entry, u.exit}:
                    if i in ids:
                        errors.append(f"{u.uid}: ipoint id {i} also used by {ids[i]}")
                    ids[i] = u.uid
                    if i > self.max_id or i <= self.id_base:
                        errors.append(f"{u.uid}: id {i} outside ({self.id_base}, {self.max_id}]")
            if u.instrumented and u.parent is not None and not (by[u.parent].instrumented or by[u.parent].kind == "branch" and by[by[u.parent].parent].instrumented):
                errors.append(f"{u.uid}: instrumented but ancestor is not")
        if self.entry_function is not None and self.entry_function not in by:
            errors.append(f"entry function {self.entry_function} not in schema")
        return errors

    def print_tree(self, out=None) -> None:
        by = self.by_uid()

        def rec(u: Unit, indent: int) -> None:
            flag = "*" if u.instrumented else " "
            ids = "" if u.entry is None else (f" [{u.entry}]" if u.entry == u.exit else f" [{u.entry}-{u.exit}]")
            extra = ""
            if u.bound is not None:
                extra += f" bound={u.bound}({u.bound_source})"
            if u.calls:
                extra += " calls=" + ",".join(u.calls)
            if u.empty:
                extra += " empty"
            if u.job:
                extra += " job"
            print(f"{flag}{'  ' * indent}{u.uid} <{u.kind}{('/' + u.stmt) if u.stmt else ''}> d={u.depth} L{u.line}{ids}{extra}", file=out)
            for c in u.children:
                rec(by[c], indent + 1)

        for f in self.functions():
            rec(f, 0)
