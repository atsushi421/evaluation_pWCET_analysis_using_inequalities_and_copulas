#!/usr/bin/env python3
"""Extract the scope tree (functions, branches, loops) of a C source file with
libclang, insert IPOINT(id) probes at unit boundaries and emit schema.json.

    ipoint_instrument.py SRC.c --out SRC.ipoint.c --schema schema.json \
        [--cflags "-std=gnu11 -fno-builtin"] [--entry FUNC] \
        [--max-depth N | --all | --functions-only] \
        [--exclude-function F]... [--exclude-unit UID]... [--include-unit UID]... \
        [--bounds bounds.json] [--keep-main] [--noinline-units] [--dry-run] [--print-tree]

Insertion rules (all edits are textual, source order preserved):
  function     IPOINT(e) after the opening brace; IPOINT(x) before every
               `return` (the return value is evaluated into a temporary first
               when it is not a trivial expression) and before the closing brace.
  loop         IPOINT(e) before the statement, IPOINT(x) after it.
  loop_body    IPOINT(e)/IPOINT(x) inside the body (braces are added to a
               single-statement body).
  alternative  IPOINT(e)/IPOINT(x) inside each branch of an if; a missing or
               empty else becomes `else { IPOINT(m); }` with a single marker.
  jumps        before every `return`, `break` and `continue` the exit IPoints of
               all instrumented units the jump leaves are emitted, innermost
               first, so every unit entry is matched by exactly one exit.
The policy (--max-depth etc.) selects which units receive probes; ids are
assigned on the full tree so they do not depend on the policy.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ipoint_schema import Schema, Unit  # noqa: E402

try:
    from clang import cindex
    from clang.cindex import CursorKind
except ImportError:  # pragma: no cover
    sys.exit("libclang python bindings not found: pip install libclang")

LOOP_KINDS = {CursorKind.FOR_STMT: "for", CursorKind.WHILE_STMT: "while", CursorKind.DO_STMT: "do"}
SIMPLE_EXPR_KINDS = {
    CursorKind.DECL_REF_EXPR,
    CursorKind.INTEGER_LITERAL,
    CursorKind.FLOATING_LITERAL,
    CursorKind.CHARACTER_LITERAL,
    CursorKind.STRING_LITERAL,
}
WRAPPER_KINDS = {CursorKind.PAREN_EXPR, CursorKind.UNEXPOSED_EXPR, CursorKind.CSTYLE_CAST_EXPR}


class Edit:
    """A replacement of src[start:end] by text. Insertions have start == end.

    Edits at the same offset are ordered: closes first, deeper closes before
    shallower ones; then opens, shallower opens before deeper ones.
    """

    def __init__(self, start: int, end: int, text: str, level: int, is_close: bool, is_brace: bool = False):
        self.start, self.end, self.text, self.level, self.is_close = start, end, text, level, is_close
        self.is_brace = is_brace

    def key(self):
        return (self.start, 0 if self.is_close else 1, -self.level if self.is_close else self.level)


def safe_int_eval(expr: str) -> Optional[int]:
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return None

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, int):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Div, ast.Mod, ast.LShift, ast.RShift)):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, (ast.Div, ast.FloorDiv)):
                return int(a / b)
            if isinstance(n.op, ast.Mod):
                return a % b
            if isinstance(n.op, ast.LShift):
                return a << b
            return a >> b
        raise ValueError

    try:
        return ev(tree)
    except (ValueError, ZeroDivisionError, TypeError):
        return None



def gcc_include_flags() -> List[str]:
    """The pip `libclang` wheel has no resource directory, so <stddef.h> and
    friends are only found through the host compiler's include directory."""
    try:
        d = subprocess.run(["gcc", "-print-file-name=include"], capture_output=True, text=True, check=True).stdout.strip()
        return ["-I" + d] if d and os.path.isdir(d) else []
    except (OSError, subprocess.CalledProcessError):
        return []


class Instrumenter:
    def __init__(self, src_path: str, cflags: List[str], policy: Dict, bounds: Dict[str, Dict]):
        self.src_path = src_path
        self.cflags = cflags
        self.policy = policy
        self.bounds = bounds
        with open(src_path, "rb") as f:
            self.src = f.read()
        self.sha256 = hashlib.sha256(self.src).hexdigest()
        idx = cindex.Index.create()
        self.tu = idx.parse(src_path, args=cflags + gcc_include_flags(),
                            options=cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
        fatal = [d for d in self.tu.diagnostics if d.severity >= cindex.Diagnostic.Error]
        for d in self.tu.diagnostics:
            print(f"clang: {d}", file=sys.stderr)
        if fatal:
            sys.exit("parse errors; aborting")
        self.macros = self._collect_macros()
        self.units: List[Unit] = []
        self.meta: Dict[str, dict] = {}  # uid -> {"cursor", "body", ...}
        self.edits: List[Edit] = []
        self.next_id = 1
        self.warnings: List[str] = []
        self.returns: List[Tuple[str, "cindex.Cursor", List[str]]] = []
        self.jumps: List[Tuple[List[str], "cindex.Cursor"]] = []
        self.counters: Dict[str, Dict[str, int]] = {}

    # ---- helpers --------------------------------------------------------
    def _in_main_file(self, c) -> bool:
        return c.location.file is not None and os.path.samefile(c.location.file.name, self.src_path)

    def _collect_macros(self) -> Dict[str, str]:
        macros = {}
        for c in self.tu.cursor.get_children():
            if c.kind == CursorKind.MACRO_DEFINITION and self._in_main_file(c):
                toks = [t.spelling for t in c.get_tokens()]
                if len(toks) >= 2 and toks[1] != "(":
                    macros[toks[0]] = " ".join(toks[1:])
        return macros

    def const_eval(self, text: str) -> Optional[int]:
        s = text
        for _ in range(32):
            replaced = re.sub(r"\b[A-Za-z_]\w*\b", lambda m: f"({self.macros[m.group(0)]})" if m.group(0) in self.macros else m.group(0), s)
            if replaced == s:
                break
            s = replaced
        if re.search(r"[A-Za-z_]", s):
            return None
        return safe_int_eval(s)

    def text(self, c) -> str:
        return self.src[c.extent.start.offset:c.extent.end.offset].decode("utf-8", "replace")

    def term_end(self, c) -> int:
        """Offset just past the statement including its terminating ';'."""
        e = c.extent.end.offset
        if e > 0 and self.src[e - 1:e] in (b"}", b";"):
            return e
        i = e
        n = len(self.src)
        while i < n:
            ch = self.src[i:i + 1]
            if ch in b" \t\r\n":
                i += 1
            elif self.src[i:i + 2] == b"//":
                j = self.src.find(b"\n", i)
                i = n if j < 0 else j + 1
            elif self.src[i:i + 2] == b"/*":
                j = self.src.find(b"*/", i)
                i = n if j < 0 else j + 2
            elif ch == b";":
                return i + 1
            else:
                break
        self.warnings.append(f"no terminating ';' found for statement at line {c.location.line}")
        return e

    def new_id(self) -> int:
        i = self.next_id
        self.next_id += 1
        return i

    def add_unit(self, uid: str, kind: str, parent: Optional[Unit], depth: int, line: int, stmt: str = "", **kw) -> Unit:
        u = Unit(uid=uid, kind=kind, parent=parent.uid if parent else None, depth=depth, line=line, stmt=stmt, **kw)
        if parent:
            parent.children.append(uid)
        self.units.append(u)
        self.meta[uid] = {}
        return u

    def counter(self, parent_uid: str, key: str) -> int:
        d = self.counters.setdefault(parent_uid, {})
        d[key] = d.get(key, 0) + 1
        return d[key]

    # ---- tree construction -------------------------------------------------
    def build(self) -> None:
        for c in self.tu.cursor.get_children():
            if c.kind == CursorKind.FUNCTION_DECL and c.is_definition() and self._in_main_file(c):
                if c.spelling in self.policy["exclude_functions"]:
                    continue
                self.visit_function(c)

    def visit_function(self, c) -> None:
        body = next((k for k in c.get_children() if k.kind == CursorKind.COMPOUND_STMT), None)
        if body is None:
            return
        u = self.add_unit(c.spelling, "function", None, 0, c.location.line)
        u.entry, u.exit = self.new_id(), self.new_id()
        self.meta[u.uid] = {"cursor": c, "body": body, "result_type": c.result_type.spelling, "is_void": c.result_type.kind == cindex.TypeKind.VOID}
        for k in body.get_children():
            self.walk(k, u, 0, u.uid, None, 1, [u])

    def walk(self, c, unit: Unit, depth: int, func: str, loop_body: Optional[Unit], level: int, chain: List[Unit]) -> None:
        """chain: open units from the function down to the innermost one."""
        kind = c.kind
        if kind == CursorKind.IF_STMT:
            self.visit_if(c, unit, depth + 1, func, loop_body, level, chain)
        elif kind in LOOP_KINDS:
            self.visit_loop(c, unit, depth + 1, func, level, chain)
        elif kind == CursorKind.RETURN_STMT:
            self.returns.append((func, c, [x.uid for x in reversed(chain) if x.kind != "function"]))
            for k in c.get_children():
                self.walk(k, unit, depth, func, loop_body, level + 1, chain)
        elif kind in (CursorKind.BREAK_STMT, CursorKind.CONTINUE_STMT):
            closes: List[str] = []
            if loop_body is not None and loop_body in chain:
                closes = [x.uid for x in reversed(chain[chain.index(loop_body):])]
            self.jumps.append((closes, c))
        elif kind == CursorKind.SWITCH_STMT:
            self.warnings.append(f"switch at line {c.location.line} is not decomposed (treated as part of {unit.uid})")
            for k in c.get_children():
                self.walk(k, unit, depth, func, None, level + 1, chain)
        elif kind == CursorKind.CALL_EXPR:
            unit.calls.append(c.spelling)
            for k in c.get_children():
                self.walk(k, unit, depth, func, loop_body, level + 1, chain)
        else:
            for k in c.get_children():
                self.walk(k, unit, depth, func, loop_body, level + 1, chain)

    def visit_if(self, c, parent: Unit, depth: int, func: str, loop_body: Optional[Unit], level: int, chain: List[Unit]) -> None:
        kids = list(c.get_children())
        if len(kids) < 2:
            return
        cond, then = kids[0], kids[1]
        els = kids[2] if len(kids) >= 3 else None
        n = self.counter(parent.uid, "if")
        b = self.add_unit(f"{parent.uid}.if{n}", "branch", parent, depth, c.location.line, "if")
        self.meta[b.uid] = {"cursor": c, "then": then, "else": els, "level": level}
        self.walk(cond, parent, depth - 1, func, loop_body, level + 1, chain)
        for name, stmt in (("then", then), ("else", els)):
            a = self.add_unit(f"{b.uid}.{name}", "alternative", b, depth, stmt.location.line if stmt is not None else c.location.line, name)
            a.entry = self.new_id()
            empty = stmt is None or (stmt.kind == CursorKind.COMPOUND_STMT and not list(stmt.get_children()))
            a.exit = a.entry if empty else self.new_id()
            a.empty = empty
            self.meta[a.uid] = {"cursor": stmt, "level": level + 1, "branch": b.uid}
            if stmt is not None:
                if stmt.kind == CursorKind.COMPOUND_STMT:
                    for k in stmt.get_children():
                        self.walk(k, a, depth, func, loop_body, level + 2, chain + [a])
                else:
                    self.walk(stmt, a, depth, func, loop_body, level + 2, chain + [a])

    def visit_loop(self, c, parent: Unit, depth: int, func: str, level: int, chain: List[Unit]) -> None:
        kids = list(c.get_children())
        stmt_kind = LOOP_KINDS[c.kind]
        if c.kind == CursorKind.DO_STMT:
            body = kids[0]
            others = kids[1:]
        else:
            body = kids[-1]
            others = kids[:-1]
        n = self.counter(parent.uid, "L")
        lp = self.add_unit(f"{parent.uid}.L{n}", "loop", parent, depth, c.location.line, stmt_kind)
        lp.entry, lp.exit = self.new_id(), self.new_id()
        self.meta[lp.uid] = {"cursor": c, "level": level}
        bd = self.add_unit(f"{lp.uid}.body", "loop_body", lp, depth, body.location.line, stmt_kind)
        bd.entry, bd.exit = self.new_id(), self.new_id()
        self.meta[bd.uid] = {"cursor": body, "level": level + 1, "loop": lp.uid}
        self.derive_bound(c, body, lp)
        for k in others:
            self.walk(k, parent, depth - 1, func, None, level + 1, chain)
        if body.kind == CursorKind.COMPOUND_STMT:
            for k in body.get_children():
                self.walk(k, bd, depth, func, bd, level + 2, chain + [lp, bd])
        else:
            self.walk(body, bd, depth, func, bd, level + 2, chain + [lp, bd])

    def derive_bound(self, c, body, lp: Unit) -> None:
        manual = self.bounds.get(lp.uid)
        if manual is not None:
            lp.bound = int(manual["bound"]) if isinstance(manual, dict) else int(manual)
            lp.bound_source = (manual.get("source", "manual") if isinstance(manual, dict) else "manual")
            return
        if c.kind != CursorKind.FOR_STMT:
            lp.bound_source = "unknown"
            return
        header = self.src[c.extent.start.offset:body.extent.start.offset].decode("utf-8", "replace")
        lpar, rpar = header.find("("), header.rfind(")")
        if lpar < 0 or rpar < 0:
            lp.bound_source = "unknown"
            return
        parts, depth_p, cur = [], 0, ""
        for ch in header[lpar + 1:rpar]:
            if ch == "(":
                depth_p += 1
            elif ch == ")":
                depth_p -= 1
            if ch == ";" and depth_p == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        parts.append(cur)
        if len(parts) != 3:
            lp.bound_source = "unknown"
            return
        init, cond, _inc = parts
        m_init = re.match(r"^\s*(?:[A-Za-z_]\w*\s+)*\**\s*([A-Za-z_]\w*)\s*=\s*(.+?)\s*$", init.replace("\n", " "))
        m_cond = re.match(r"^\s*([A-Za-z_]\w*)\s*(<=|<)\s*(.+?)\s*$", cond.replace("\n", " "))
        if not m_init or not m_cond or m_init.group(1) != m_cond.group(1):
            lp.bound_source = "unknown"
            return
        lp.loop_var = m_cond.group(1)
        lo, hi = self.const_eval(m_init.group(2)), self.const_eval(m_cond.group(3))
        if lo is None or hi is None:
            lp.bound_source = "unknown"
            return
        lp.bound = max(0, hi - lo + (1 if m_cond.group(2) == "<=" else 0))
        lp.bound_source = "macro" if re.search(r"[A-Za-z_]", m_init.group(2) + m_cond.group(3)) else "literal"

    # ---- policy -------------------------------------------------------------
    def apply_policy(self) -> None:
        by = {u.uid: u for u in self.units}
        maxd = self.policy["max_depth"]
        inc, exc = set(self.policy["include_units"]), set(self.policy["exclude_units"])
        for u in self.units:
            if u.kind == "branch":
                continue
            on = u.depth <= maxd
            if u.uid in inc:
                on = True
            if u.uid in exc:
                on = False
            u.instrumented = on
        # an instrumented unit needs all its ancestors instrumented
        changed = True
        while changed:
            changed = False
            for u in self.units:
                if not u.instrumented or u.parent is None:
                    continue
                p = by[u.parent]
                while p.kind == "branch":
                    p = by[p.parent]
                if not p.instrumented:
                    u.instrumented = False
                    changed = True
        unknown = [u.uid for u in self.units if u.uid in inc | exc and u.uid not in by]
        for x in unknown:
            self.warnings.append(f"unknown unit in include/exclude list: {x}")

    # ---- edits --------------------------------------------------------------
    def ins(self, off: int, text: str, level: int, close: bool) -> None:
        self.edits.append(Edit(off, off, text, level, close))

    def probe(self, uid_id: int) -> str:
        return f"IPOINT({uid_id});"

    def is_simple_expr(self, c) -> bool:
        if c.kind in SIMPLE_EXPR_KINDS:
            return True
        kids = list(c.get_children())
        if c.kind in WRAPPER_KINDS and len(kids) == 1:
            return self.is_simple_expr(kids[0])
        if c.kind == CursorKind.UNARY_OPERATOR and len(kids) == 1:
            toks = [t.spelling for t in c.get_tokens()]
            if "++" in toks or "--" in toks:
                return False
            return self.is_simple_expr(kids[0])
        return False

    @staticmethod
    def ends_with_jump(stmt) -> bool:
        """True when control never reaches the end of stmt (its last statement is a jump)."""
        jumps = (CursorKind.RETURN_STMT, CursorKind.BREAK_STMT, CursorKind.CONTINUE_STMT)
        if stmt.kind == CursorKind.COMPOUND_STMT:
            kids = list(stmt.get_children())
            return bool(kids) and kids[-1].kind in jumps
        return stmt.kind in jumps

    def instrument_stmt_body(self, stmt, entry: int, exit_: int, level: int, is_empty: bool) -> None:
        """Insert entry/exit probes inside a compound statement or wrap a single statement.
        The exit probe is omitted when the body ends with a jump; the jump carries it."""
        skip_exit = self.ends_with_jump(stmt)
        if stmt.kind == CursorKind.COMPOUND_STMT:
            s, e = stmt.extent.start.offset + 1, stmt.extent.end.offset - 1
            if is_empty:
                self.ins(s, f" {self.probe(entry)} ", level, False)
            else:
                self.ins(s, f" {self.probe(entry)}", level, False)
                if not skip_exit:
                    self.ins(e, f"{self.probe(exit_)} ", level, True)
        else:
            s, e = stmt.extent.start.offset, self.term_end(stmt)
            self.ins(s, f"{{ {self.probe(entry)} ", level, False)
            self.ins(e, (" }" if skip_exit else f" {self.probe(exit_)} }}"), level, True)

    def brace_single_statements(self) -> None:
        """Wrap every uninstrumented single-statement body or alternative in
        braces when an edit falls inside it, so that inserted probes cannot
        change what the if/loop guards."""
        for u in self.units:
            if u.kind not in ("alternative", "loop_body") or u.instrumented:
                continue
            stmt = self.meta[u.uid]["cursor"]
            if stmt is None or stmt.kind == CursorKind.COMPOUND_STMT:
                continue
            s, e = stmt.extent.start.offset, self.term_end(stmt)
            if any(s <= ed.start <= e for ed in self.edits if not ed.is_brace):
                lv = self.meta[u.uid]["level"]
                self.edits.append(Edit(s, s, "{ ", lv, False, True))
                self.edits.append(Edit(e, e, " }", lv, True, True))

    def generate_edits(self) -> None:
        by = {u.uid: u for u in self.units}
        noinline = self.policy.get("noinline_units", False)
        for u in self.units:
            m = self.meta[u.uid]
            if u.kind == "function":
                if not u.instrumented:
                    continue
                c, body = m["cursor"], m["body"]
                if noinline:
                    self.ins(c.extent.start.offset, "__attribute__((noinline)) ", 0, False)
                self.ins(body.extent.start.offset + 1, f" {self.probe(u.entry)}", 0, False)
                kids = list(body.get_children())
                if not kids or kids[-1].kind != CursorKind.RETURN_STMT:
                    self.ins(body.extent.end.offset - 1, f"{self.probe(u.exit)} ", 0, True)
            elif u.kind == "loop":
                lv = m["level"]
                c = m["cursor"]
                if u.instrumented:
                    self.ins(c.extent.start.offset, f"{self.probe(u.entry)} ", lv, False)
                    self.ins(self.term_end(c), f" {self.probe(u.exit)}", lv, True)
            elif u.kind == "loop_body":
                lv = m["level"]
                stmt = m["cursor"]
                if u.instrumented:
                    self.instrument_stmt_body(stmt, u.entry, u.exit, lv, False)
            elif u.kind == "alternative":
                lv = m["level"]
                stmt = m["cursor"]
                b = by[m["branch"]]
                bm = self.meta[b.uid]
                if u.instrumented:
                    if stmt is None:
                        then_end = self.term_end(bm["then"])
                        self.ins(then_end, f" else {{ {self.probe(u.entry)} }}", bm["level"], True)
                    else:
                        self.instrument_stmt_body(stmt, u.entry, u.exit, lv, u.empty)
        def closes(uids: List[str]) -> str:
            return "".join(f"{self.probe(by[x].exit)} " for x in uids
                           if by[x].kind != "branch" and by[x].instrumented and not by[x].empty)

        # returns: close every enclosing unit, then the function
        for func, r, chain_uids in self.returns:
            fu = by.get(func)
            if fu is None or not fu.instrumented:
                continue
            probes = closes(chain_uids) + f"{self.probe(fu.exit)} "
            kids = list(r.get_children())
            start = r.extent.start.offset
            if not kids or self.is_simple_expr(kids[0]):
                self.ins(start, probes, 99, False)
            else:
                rt = self.meta[func]["result_type"]
                end = self.term_end(r)
                self.edits.append(Edit(start, start + len("return"), f"{{ {rt} __ipoint_rv = (", 99, False))
                self.edits.append(Edit(end - 1, end, f"); {probes}return __ipoint_rv; }}", 99, True))
        # break / continue: close every unit up to and including the loop body
        for chain_uids, j in self.jumps:
            probes = closes(chain_uids)
            if probes:
                self.ins(j.extent.start.offset, probes, 99, False)
        self.brace_single_statements()

    def render(self) -> bytes:
        out = bytearray()
        pos = 0
        edits = sorted(self.edits, key=lambda e: e.key())
        for i in range(1, len(edits)):
            if edits[i].start < edits[i - 1].end:
                raise RuntimeError(f"overlapping edits at offset {edits[i].start}")
        for e in edits:
            out += self.src[pos:e.start]
            out += e.text.encode()
            pos = e.end
        out += self.src[pos:]
        header = b'#include "ipoint.h"\n'
        return header + bytes(out)

    def schema(self, entry: Optional[str]) -> Schema:
        return Schema(source=os.path.basename(self.src_path), source_sha256=self.sha256, cflags=self.cflags,
                      policy=self.policy, entry_function=entry, max_id=self.next_id - 1, units=self.units)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("--out", help="instrumented source (default: <src>.ipoint.c)")
    ap.add_argument("--schema", help="schema json (default: <out>.schema.json)")
    ap.add_argument("--cflags", default="-std=gnu11 -fno-builtin", help="flags passed to libclang")
    ap.add_argument("--entry", help="entry function whose outermost IPoint pair is the end-to-end time")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--max-depth", type=int, default=1, help="instrument units nested up to this depth (function = 0)")
    g.add_argument("--all", action="store_true", help="instrument every unit")
    g.add_argument("--functions-only", action="store_true")
    ap.add_argument("--exclude-function", action="append", default=[], help="skip this function entirely")
    ap.add_argument("--keep-main", action="store_true", help="instrument main() too (it is skipped by default; use when main is the entry)")
    ap.add_argument("--exclude-unit", action="append", default=[])
    ap.add_argument("--include-unit", action="append", default=[])
    ap.add_argument("--bounds", help="json {uid: bound | {bound, source}} for loops without a static bound")
    ap.add_argument("--noinline-units", action="store_true", help="add __attribute__((noinline)) to instrumented functions")
    ap.add_argument("--dry-run", action="store_true", help="do not write files")
    ap.add_argument("--print-tree", action="store_true")
    a = ap.parse_args(argv)

    if a.all:
        max_depth = 1 << 20
    elif a.functions_only:
        max_depth = 0
    else:
        max_depth = a.max_depth
    exclude_functions = list(a.exclude_function) + ([] if a.keep_main else ["main"])
    policy = {"max_depth": max_depth, "exclude_functions": exclude_functions, "exclude_units": a.exclude_unit,
              "include_units": a.include_unit, "noinline_units": a.noinline_units}
    bounds = {}
    if a.bounds:
        with open(a.bounds) as f:
            bounds = json.load(f)
    inst = Instrumenter(a.src, a.cflags.split(), policy, bounds)
    inst.build()
    inst.apply_policy()
    inst.generate_edits()
    sch = inst.schema(a.entry)
    errors = sch.validate()
    for w in inst.warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors:
        return 1
    if a.print_tree:
        sch.print_tree()
    if not a.dry_run:
        out = a.out or os.path.splitext(a.src)[0] + ".ipoint.c"
        schema_path = a.schema or out + ".schema.json"
        with open(out, "wb") as f:
            f.write(inst.render())
        sch.to_json(schema_path)
        print(f"wrote {out} and {schema_path} ({len(sch.instrumented_units())} instrumented units, max_id={sch.max_id})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
