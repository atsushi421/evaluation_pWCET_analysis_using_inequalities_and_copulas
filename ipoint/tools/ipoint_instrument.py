#!/usr/bin/env python3
"""Extract the scope tree (functions, branches, loops) of a C or C++ source
file with libclang, insert IPOINT(id) probes at unit boundaries and emit
schema.json.

    ipoint_instrument.py SRC.c --out SRC.ipoint.c --schema schema.json \
        [--cflags "-std=gnu11 -fno-builtin"] [--entry FUNC] \
        [--max-depth N | --all | --functions-only] \
        [--exclude-function F]... [--exclude-unit UID]... [--include-unit UID]... \
        [--bounds bounds.json] [--keep-main] [--noinline-units] [--dry-run] [--print-tree]

    ipoint_instrument.py SRC.cpp --lang c++ --compile-commands build/PKG/compile_commands.json \
        --only-function Class::method... --job Class::callback --id-base 1000 --all \
        --in-place --schema schema.json [--print-tree]

Insertion rules (all edits are textual, source order preserved):
  function     IPOINT(e) after the opening brace; IPOINT(x) before every
               `return` (the return value is evaluated into a temporary first
               when it is not a trivial expression) and before the closing brace.
               The --job function uses IPOINT_JOB_BEGIN/IPOINT_JOB_END instead,
               so that every invocation is recorded as one run.
  loop         IPOINT(e) before the statement, IPOINT(x) after it (for, while,
               do and C++ range-for).
  loop_body    IPOINT(e)/IPOINT(x) inside the body (braces are added to a
               single-statement body).
  alternative  IPOINT(e)/IPOINT(x) inside each branch of an if; a missing or
               empty else becomes `else { IPOINT(m); }` with a single marker.
  jumps        before every `return`, `break` and `continue` the exit IPoints of
               all instrumented units the jump leaves are emitted, innermost
               first, so every unit entry is matched by exactly one exit.
The policy (--max-depth etc.) selects which units receive probes; ids are
assigned on the full tree so they do not depend on the policy.

C++: function definitions inside namespaces and classes are found (unit uid =
`Class::method`, namespaces dropped; overloads get a `#n` suffix), lambdas and
local classes are opaque, try/catch bodies are walked, `return expr;` is
rewritten with `auto` (or the canonical result type for braced initializers).
--compile-commands takes the include paths and defines of the file from the
build tree, --only-function restricts the instrumented functions (names match
as a `::`-suffix), --id-base keeps the ids of several schemas loaded into one
process disjoint.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shlex
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

LOOP_KINDS = {CursorKind.FOR_STMT: "for", CursorKind.WHILE_STMT: "while", CursorKind.DO_STMT: "do",
              CursorKind.CXX_FOR_RANGE_STMT: "for-range"}
FUNCTION_KINDS = {CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD}
SCOPE_KINDS = {CursorKind.NAMESPACE, CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE,
               CursorKind.LINKAGE_SPEC, CursorKind.UNEXPOSED_DECL}
OPAQUE_KINDS = {CursorKind.LAMBDA_EXPR, CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CXX_METHOD,
                CursorKind.FUNCTION_DECL}
SIMPLE_EXPR_KINDS = {
    CursorKind.DECL_REF_EXPR,
    CursorKind.INTEGER_LITERAL,
    CursorKind.FLOATING_LITERAL,
    CursorKind.CHARACTER_LITERAL,
    CursorKind.STRING_LITERAL,
    CursorKind.CXX_BOOL_LITERAL_EXPR,
    CursorKind.CXX_NULL_PTR_LITERAL_EXPR,
    CursorKind.CXX_THIS_EXPR,
}
WRAPPER_KINDS = {CursorKind.PAREN_EXPR, CursorKind.UNEXPOSED_EXPR, CursorKind.CSTYLE_CAST_EXPR}
# a statement whose source text does not start with its keyword comes from a
# macro expansion (RCLCPP_INFO_THROTTLE, DEBUG_INFO, ...) and cannot be edited
STMT_KEYWORD = {CursorKind.IF_STMT: "if", CursorKind.FOR_STMT: "for", CursorKind.CXX_FOR_RANGE_STMT: "for",
                CursorKind.WHILE_STMT: "while", CursorKind.DO_STMT: "do", CursorKind.SWITCH_STMT: "switch",
                CursorKind.RETURN_STMT: "return", CursorKind.BREAK_STMT: "break", CursorKind.CONTINUE_STMT: "continue"}


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


def clang_resource_dir() -> Optional[str]:
    """Resource directory of an installed clang (its builtin headers replace the
    GCC intrinsics headers, which libclang cannot parse: with them, statements
    that use unresolved types are silently dropped from the AST)."""
    import glob
    cands = glob.glob("/usr/lib/llvm-*/lib/clang/*/include") + glob.glob("/usr/lib/clang/*/include")

    def ver(p):
        m = re.search(r"/clang/(\d+)(?:\.(\d+))?", p)
        return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)

    cands = [c for c in cands if os.path.exists(os.path.join(c, "stddef.h"))]
    return os.path.dirname(max(cands, key=ver)) if cands else None


def drop_gcc_include_dir(flags: List[str]) -> List[str]:
    """Remove every reference to GCC's builtin include directory (-I/-isystem, joined or split)."""
    pat = re.compile(r"/lib/gcc/[^/]+/\d+/include/?$")
    out: List[str] = []
    skip = False
    for i, x in enumerate(flags):
        if skip:
            skip = False
            continue
        if x in ("-I", "-isystem", "-idirafter") and i + 1 < len(flags) and pat.search(flags[i + 1]):
            skip = True
            continue
        if (x.startswith("-I") or x.startswith("-isystem")) and pat.search(x):
            continue
        out.append(x)
    return out


_LIBCLANG_SELECTED = False


def select_libclang(resource_dir: Optional[str]) -> Optional[str]:
    """Use the system libclang whose version matches the resource directory
    (IPOINT_LIBCLANG overrides). The pip `libclang` wheel is newer than the
    installed clang headers; the mismatch leaves parse errors in the intrinsics
    headers, and libclang silently drops statements that use unresolved types.
    Must run before the first use of the bindings."""
    global _LIBCLANG_SELECTED
    if _LIBCLANG_SELECTED:
        return None
    _LIBCLANG_SELECTED = True
    path = os.environ.get("IPOINT_LIBCLANG")
    if not path and resource_dir:
        m = re.search(r"/clang/(\d+)", resource_dir)
        if m:
            for cand in (f"/usr/lib/llvm-{m.group(1)}/lib/libclang-{m.group(1)}.so.1",
                         f"/usr/lib/llvm-{m.group(1)}/lib/libclang.so.1", f"/usr/lib/x86_64-linux-gnu/libclang-{m.group(1)}.so.1"):
                if os.path.exists(cand):
                    path = cand
                    break
    if path and os.path.exists(path):
        cindex.Config.set_compatibility_check(False)
        cindex.Config.set_library_file(path)
        return path
    return None


def gxx_system_include_flags() -> List[str]:
    """System include directories of the host g++ (libstdc++ and friends), as
    -isystem flags, for parsing C++ with the resource-less libclang wheel."""
    try:
        out = subprocess.run(["g++", "-E", "-x", "c++", "-v", "/dev/null"], capture_output=True, text=True).stderr
    except OSError:
        return []
    flags: List[str] = []
    grab = False
    for line in out.splitlines():
        if line.startswith("#include <...> search starts here"):
            grab = True
            continue
        if line.startswith("End of search list"):
            break
        if grab and line.strip():
            d = line.strip()
            if os.path.isdir(d):
                flags += ["-isystem", d]
    return flags


def compile_command_flags(cc_path: str, src_path: str) -> List[str]:
    """Include paths, defines and language flags of src_path in a
    compile_commands.json (the compiler, output and dependency flags are dropped)."""
    with open(cc_path) as f:
        entries = json.load(f)
    real = os.path.realpath(src_path)
    for e in entries:
        f_ = e["file"]
        if not os.path.isabs(f_):
            f_ = os.path.join(e.get("directory", ""), f_)
        if os.path.realpath(f_) != real:
            continue
        args = e.get("arguments") or shlex.split(e["command"])
        out: List[str] = []
        skip = False
        for a in args[1:]:
            if skip:
                skip = False
                continue
            if a in ("-o", "-MF", "-MT", "-MQ"):
                skip = True
                continue
            if a in ("-c", "-MD", "-MMD", "-MP") or a.startswith("-fdiagnostics") or a.startswith("-W"):
                continue
            if os.path.realpath(a if os.path.isabs(a) else os.path.join(e.get("directory", ""), a)) == real:
                continue
            out.append(a)
        return out
    raise SystemExit(f"{src_path} not found in {cc_path}")


def qualified_name(c) -> str:
    parts = [c.spelling]
    p = c.semantic_parent
    while p is not None and p.kind in (CursorKind.NAMESPACE, CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL,
                                       CursorKind.CLASS_TEMPLATE):
        if p.spelling:
            parts.append(p.spelling)
        p = p.semantic_parent
    return "::".join(reversed(parts))


def class_qualified_name(c) -> str:
    """Class::method (namespaces dropped); a free function keeps its bare name."""
    p = c.semantic_parent
    if p is not None and p.kind in (CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE):
        return f"{p.spelling}::{c.spelling}"
    return c.spelling


def name_matches(pattern: str, qualified: str) -> bool:
    return qualified == pattern or qualified.endswith("::" + pattern)


class Instrumenter:
    def __init__(self, src_path: str, cflags: List[str], policy: Dict, bounds: Dict[str, Dict], lang: str = "c",
                 id_base: int = 0):
        self.src_path = src_path
        self.cflags = cflags
        self.policy = policy
        self.bounds = bounds
        self.lang = lang
        self.id_base = id_base
        with open(src_path, "rb") as f:
            self.src = f.read()
        if (b'#include "ipoint.h"' in self.src or re.search(rb"\bIPOINT(_JOB_BEGIN|_JOB_END)?\(", self.src)) \
                and not policy.get("allow_instrumented"):
            sys.exit(f"{src_path} already contains IPoint probes; restore the original first (or --allow-instrumented)")
        self.sha256 = hashlib.sha256(self.src).hexdigest()
        rd = clang_resource_dir() if lang == "c++" else None
        self.libclang = select_libclang(rd) if lang == "c++" else None
        idx = cindex.Index.create()
        args = list(cflags)
        if lang == "c++":
            sysinc = gxx_system_include_flags()
            if rd:
                # clang's builtin headers must win over GCC's intrinsics directory:
                # drop `-isystem <gcc include dir>` (flag + path) from both lists
                sysinc = drop_gcc_include_dir(sysinc)
                args = drop_gcc_include_dir(args)
            args = ["-x", "c++"] + args + sysinc
        if rd and not any(x.startswith("-resource-dir") for x in args):
            args += ["-resource-dir", rd]
        else:
            args += gcc_include_flags()
        self.resource_dir = rd
        self.tu = idx.parse(src_path, args=args, options=cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
        errors = [d for d in self.tu.diagnostics if d.severity >= cindex.Diagnostic.Error]
        main_errors = [d for d in errors if d.location.file is not None
                       and os.path.realpath(d.location.file.name) == os.path.realpath(src_path)]
        shown = 0
        for d in self.tu.diagnostics:
            if d.severity >= cindex.Diagnostic.Error or lang == "c":
                if shown < 30:
                    print(f"clang: {d}", file=sys.stderr)
                shown += 1
        if shown > 30:
            print(f"clang: ... {shown - 30} more diagnostics", file=sys.stderr)
        if main_errors or (errors and (lang == "c" or policy.get("strict"))):
            sys.exit("parse errors; aborting")
        self.header_errors = len(errors) - len(main_errors)
        self.macros = self._collect_macros()
        self.units: List[Unit] = []
        self.meta: Dict[str, dict] = {}  # uid -> {"cursor", "body", ...}
        self.edits: List[Edit] = []
        self.next_id = id_base + 1
        self.warnings: List[str] = []
        self.returns: List[Tuple[str, "cindex.Cursor", List[str]]] = []
        self.jumps: List[Tuple[List[str], "cindex.Cursor"]] = []
        self.counters: Dict[str, Dict[str, int]] = {}
        self.function_uids: Dict[str, int] = {}
        self.macro_lines = set()
        self.errors: List[str] = []

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
        if c.kind == CursorKind.COMPOUND_STMT:
            return e
        if c.kind in (CursorKind.IF_STMT, CursorKind.FOR_STMT, CursorKind.WHILE_STMT, CursorKind.CXX_FOR_RANGE_STMT,
                      CursorKind.SWITCH_STMT, CursorKind.CXX_TRY_STMT):
            kids = list(c.get_children())
            if kids:
                last = kids[-1]
                if last.kind in (CursorKind.COMPOUND_STMT, CursorKind.CXX_CATCH_STMT) and self.src[e - 1:e] == b"}":
                    return e
                if last.kind in STMT_KEYWORD or last.kind == CursorKind.CXX_TRY_STMT:
                    return self.term_end(last)  # else-if chain, nested single-statement loop/if
        if e > 0 and self.src[e - 1:e] == b";":
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
        self.visit_scope(self.tu.cursor)

    def visit_scope(self, scope) -> None:
        for c in scope.get_children():
            if not self._in_main_file(c):
                continue
            if c.kind in FUNCTION_KINDS and c.is_definition():
                self.consider_function(c)
            elif c.kind in SCOPE_KINDS:
                self.visit_scope(c)

    def consider_function(self, c) -> None:
        q = qualified_name(c)
        if any(name_matches(x, q) for x in self.policy["exclude_functions"]):
            return
        only = self.policy.get("only_functions") or []
        if only and not any(name_matches(x, q) for x in only):
            return
        self.visit_function(c, q)

    def visit_function(self, c, qualified: str) -> None:
        body = next((k for k in c.get_children() if k.kind == CursorKind.COMPOUND_STMT), None)
        if body is None:
            return
        uid = class_qualified_name(c) if self.lang == "c++" else c.spelling
        n = self.function_uids.get(uid, 0) + 1
        self.function_uids[uid] = n
        if n > 1:
            self.warnings.append(f"overloaded function {uid} (definition {n} at line {c.location.line}) is named {uid}#{n}")
            uid = f"{uid}#{n}"
        u = self.add_unit(uid, "function", None, 0, c.location.line, qualified=qualified if self.lang == "c++" else None)
        u.entry, u.exit = self.new_id(), self.new_id()
        u.job = any(name_matches(x, qualified) for x in self.policy.get("jobs", []))
        rt = c.result_type
        self.meta[u.uid] = {"cursor": c, "body": body, "result_type": rt.spelling,
                            "canonical_type": rt.get_canonical().spelling,
                            "decl_type_text": self.declared_result_type(c),
                            "is_ref": rt.kind in (cindex.TypeKind.LVALUEREFERENCE, cindex.TypeKind.RVALUEREFERENCE),
                            "is_void": rt.kind == cindex.TypeKind.VOID}
        for k in body.get_children():
            self.walk(k, u, 0, u.uid, None, 1, [u])
        self.verify_returns(u, body)

    def verify_returns(self, u: Unit, body) -> None:
        """libclang drops statements whose expressions failed to type-check (e.g.
        when a header did not parse), so the return statements found in the AST
        are compared with the `return` keywords in the body text (comments,
        strings and lambda bodies removed)."""
        text = self.text(body)
        text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
        text = re.sub(r'"(\\.|[^"\\])*"', '""', text)
        lam = re.compile(r"\[[^\[\]]*\]\s*(\([^()]*\))?\s*(mutable\s*)?(->\s*[^{]+)?\{")
        out, i = [], 0
        while i < len(text):
            m = lam.match(text, i)
            if m:
                depth, j = 1, m.end()
                while j < len(text) and depth:
                    depth += 1 if text[j] == "{" else -1 if text[j] == "}" else 0
                    j += 1
                i = j
                continue
            out.append(text[i])
            i += 1
        n_text = len(re.findall(r"\breturn\b", "".join(out)))
        n_ast = sum(1 for f, _, _ in self.returns if f == u.uid)
        if n_text != n_ast:
            msg = (f"{u.uid}: {n_text} `return` in the source but {n_ast} in the AST "
                   f"(statements with parse errors are dropped by libclang; fix the include paths)")
            if self.policy.get("allow_missing_returns"):
                self.warnings.append(msg)
            else:
                self.errors.append(msg)

    def declared_result_type(self, c) -> str:
        """The result type as written in the definition (the text before the
        function name, without specifiers and the Class:: qualifier). libclang's
        type spellings are unreliable when headers failed to parse (Eigen
        types become `int`), the source text is not."""
        head = self.src[c.extent.start.offset:c.location.offset].decode("utf-8", "replace")
        head = re.sub(r"/\*.*?\*/|//[^\n]*", " ", head, flags=re.S)
        head = re.sub(r"\[\[.*?\]\]", " ", head)
        head = re.sub(r"\b(static|inline|virtual|constexpr|explicit|extern|friend)\b", " ", head)
        head = re.sub(r"(\w+\s*::\s*)+$", "", head.strip()).strip()
        head = re.sub(r"\s+", " ", head)
        if not head or head.startswith("template") or re.match(r"^(auto|decltype\(auto\))\b", head):
            return ""
        return head

    def walk(self, c, unit: Unit, depth: int, func: str, loop_body: Optional[Unit], level: int, chain: List[Unit]) -> None:
        """chain: open units from the function down to the innermost one."""
        kind = c.kind
        if kind in OPAQUE_KINDS:
            return  # lambdas, local classes and nested definitions are part of the enclosing unit
        if self.from_macro(c):
            if c.location.line not in self.macro_lines:
                self.macro_lines.add(c.location.line)
                self.warnings.append(f"statement expanded from a macro at line {c.location.line} is treated as part of {unit.uid}")
            return
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
            if c.spelling:
                unit.calls.append(c.spelling)
            for k in c.get_children():
                self.walk(k, unit, depth, func, loop_body, level + 1, chain)
        else:
            for k in c.get_children():
                self.walk(k, unit, depth, func, loop_body, level + 1, chain)

    def from_macro(self, c) -> bool:
        kw = STMT_KEYWORD.get(c.kind)
        if kw is None:
            return False
        return re.match(kw + r"\b", self.text(c).lstrip()) is None

    def visit_if(self, c, parent: Unit, depth: int, func: str, loop_body: Optional[Unit], level: int, chain: List[Unit]) -> None:
        kids = list(c.get_children())
        if len(kids) < 2:
            return
        cond, then, els = self._split_if(kids)
        n = self.counter(parent.uid, "if")
        b = self.add_unit(f"{parent.uid}.if{n}", "branch", parent, depth, c.location.line, "if")
        self.meta[b.uid] = {"cursor": c, "then": then, "else": els, "level": level}
        for pre in kids[:kids.index(then)]:
            self.walk(pre, parent, depth - 1, func, loop_body, level + 1, chain)
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

    def _split_if(self, kids):
        """(condition, then, else) of an if statement. libclang lists an optional
        init-statement and/or condition variable before the condition, so the
        else branch is recognized by the `else` keyword between the last two
        children instead of by the number of children."""
        has_else = False
        if len(kids) >= 3:
            gap = self.src[kids[-2].extent.end.offset:kids[-1].extent.start.offset].decode("utf-8", "replace")
            gap = re.sub(r"/\*.*?\*/|//[^\n]*", " ", gap, flags=re.S)
            has_else = re.search(r"\belse\b", gap) is not None
        if has_else:
            then, els, cond = kids[-2], kids[-1], kids[-3]
        else:
            then, els, cond = kids[-1], None, kids[-2]
        return cond, then, els

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
        m_init = re.match(r"^\s*(?:[A-Za-z_][\w:<>]*\s+)*\**\s*([A-Za-z_]\w*)\s*=\s*(.+?)\s*$", init.replace("\n", " "))
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
        unknown = [x for x in inc | exc if x not in by]
        for x in unknown:
            self.warnings.append(f"unknown unit in include/exclude list: {x}")

    # ---- edits --------------------------------------------------------------
    def ins(self, off: int, text: str, level: int, close: bool) -> None:
        self.edits.append(Edit(off, off, text, level, close))

    def probe(self, uid_id: int) -> str:
        return f"IPOINT({uid_id});"

    def entry_probe(self, u: Unit) -> str:
        return f"IPOINT_JOB_BEGIN({u.entry});" if u.job else self.probe(u.entry)

    def exit_probe(self, u: Unit) -> str:
        return f"IPOINT_JOB_END({u.exit});" if u.job else self.probe(u.exit)

    def is_simple_expr(self, c) -> bool:
        if c.kind in SIMPLE_EXPR_KINDS:
            return True
        kids = list(c.get_children())
        if c.kind in WRAPPER_KINDS and len(kids) == 1:
            return self.is_simple_expr(kids[0])
        if c.kind == CursorKind.MEMBER_REF_EXPR and len(kids) <= 1:
            return not kids or self.is_simple_expr(kids[0])
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
                self.ins(body.extent.start.offset + 1, f" {self.entry_probe(u)}", 0, False)
                kids = list(body.get_children())
                if not kids or kids[-1].kind != CursorKind.RETURN_STMT:
                    self.ins(body.extent.end.offset - 1, f"{self.exit_probe(u)} ", 0, True)
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
            probes = closes(chain_uids) + f"{self.exit_probe(fu)} "
            kids = list(r.get_children())
            start = r.extent.start.offset
            if not kids or self.is_simple_expr(kids[0]):
                self.ins(start, probes, 99, False)
                continue
            end = self.term_end(r)
            fm = self.meta[func]
            if fm["is_void"]:
                # `return void_call();` in a void function: evaluate, then close
                self.edits.append(Edit(start, start + len("return"), "{ (", 99, False))
                self.edits.append(Edit(end - 1, end, f"); {probes}return; }}", 99, True))
                continue
            braced = kids[0].kind == CursorKind.INIT_LIST_EXPR or self.text(r)[len("return"):].lstrip().startswith("{")
            if braced:
                # `return {a, b};` keeps its braced initializer; the declared type is needed
                # (libclang may wrap the initializer list in conversion/constructor cursors)
                decl = fm["decl_type_text"] if self.lang == "c++" else fm["result_type"]
                if not decl:
                    decl = fm["result_type"]
                    self.warnings.append(f"return at line {r.location.line}: result type taken from libclang ({decl})")
                self.edits.append(Edit(start, start + len("return"), f"{{ {decl} __ipoint_rv = ", 99, False))
                self.edits.append(Edit(end - 1, end, f"; {probes}return __ipoint_rv; }}", 99, True))
            else:
                if self.lang == "c++":
                    decl = "decltype(auto)" if fm["is_ref"] else "auto"
                else:
                    decl = fm["result_type"]
                self.edits.append(Edit(start, start + len("return"), f"{{ {decl} __ipoint_rv = (", 99, False))
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
        policy = dict(self.policy)
        if self.lang == "c++":
            policy["libclang"] = getattr(self, "libclang", None) or "pip libclang"
            policy["resource_dir"] = getattr(self, "resource_dir", None)
        return Schema(source=os.path.basename(self.src_path), source_sha256=self.sha256, cflags=self.cflags,
                      policy=policy, entry_function=entry, max_id=self.next_id - 1, units=self.units,
                      lang=self.lang, id_base=self.id_base)


def resolve_function_uid(units: List[Unit], name: str) -> Optional[str]:
    """uid of the function unit whose (qualified) name matches `name`."""
    for u in units:
        if u.kind != "function":
            continue
        if u.uid == name or (u.qualified and name_matches(name, u.qualified)) or name_matches(name, u.uid):
            return u.uid
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("--out", help="instrumented source (default: <src>.ipoint.c / .ipoint.cpp)")
    ap.add_argument("--in-place", action="store_true", help="overwrite src with the instrumented source")
    ap.add_argument("--schema", help="schema json (default: <out>.schema.json)")
    ap.add_argument("--lang", choices=["c", "c++"], default=None, help="source language (default from the extension)")
    ap.add_argument("--cflags", default=None, help="flags passed to libclang (default: -std=gnu11 -fno-builtin / -std=gnu++17)")
    ap.add_argument("--compile-commands", help="compile_commands.json to take include paths and defines from")
    ap.add_argument("--entry", help="entry function whose outermost IPoint pair is the end-to-end time")
    ap.add_argument("--job", action="append", default=[], help="function recorded as one run per invocation (IPOINT_JOB_BEGIN/END); implies --entry when single")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--max-depth", type=int, default=1, help="instrument units nested up to this depth (function = 0)")
    g.add_argument("--all", action="store_true", help="instrument every unit")
    g.add_argument("--functions-only", action="store_true")
    ap.add_argument("--exclude-function", action="append", default=[], help="skip this function entirely")
    ap.add_argument("--only-function", action="append", default=[], help="instrument only these functions (Class::method or method)")
    ap.add_argument("--keep-main", action="store_true", help="instrument main() too (it is skipped by default; use when main is the entry)")
    ap.add_argument("--exclude-unit", action="append", default=[])
    ap.add_argument("--include-unit", action="append", default=[])
    ap.add_argument("--bounds", help="json {uid: bound | {bound, source}} for loops without a static bound")
    ap.add_argument("--id-base", type=int, default=0, help="first ipoint id minus one (disjoint ids for several schemas in one process)")
    ap.add_argument("--noinline-units", action="store_true", help="add __attribute__((noinline)) to instrumented functions")
    ap.add_argument("--strict", action="store_true", help="abort on parse errors in headers too")
    ap.add_argument("--allow-instrumented", action="store_true", help="instrument a source that already contains IPoint probes")
    ap.add_argument("--allow-missing-returns", action="store_true", help="only warn when return statements are missing from the AST")
    ap.add_argument("--dry-run", action="store_true", help="do not write files")
    ap.add_argument("--print-tree", action="store_true")
    a = ap.parse_args(argv)

    lang = a.lang or ("c++" if os.path.splitext(a.src)[1].lower() in (".cpp", ".cc", ".cxx", ".hpp") else "c")
    cflags = shlex.split(a.cflags) if a.cflags is not None else (["-std=gnu++17"] if lang == "c++" else ["-std=gnu11", "-fno-builtin"])
    if a.compile_commands:
        cflags = compile_command_flags(a.compile_commands, a.src) + (shlex.split(a.cflags) if a.cflags else [])
    if a.all:
        max_depth = 1 << 20
    elif a.functions_only:
        max_depth = 0
    else:
        max_depth = a.max_depth
    exclude_functions = list(a.exclude_function) + ([] if a.keep_main else ["main"])
    policy = {"max_depth": max_depth, "exclude_functions": exclude_functions, "exclude_units": a.exclude_unit,
              "include_units": a.include_unit, "noinline_units": a.noinline_units,
              "only_functions": a.only_function, "jobs": a.job, "strict": a.strict,
              "allow_instrumented": a.allow_instrumented, "allow_missing_returns": a.allow_missing_returns}
    bounds = {}
    if a.bounds:
        with open(a.bounds) as f:
            bounds = json.load(f)
    inst = Instrumenter(a.src, cflags, policy, bounds, lang=lang, id_base=a.id_base)
    inst.build()
    inst.apply_policy()
    inst.generate_edits()
    entry = a.entry
    if entry is None and len(a.job) == 1:
        entry = a.job[0]
    if entry is not None:
        resolved = resolve_function_uid(inst.units, entry)
        if resolved is None:
            print(f"error: entry/job function {entry} not found in {a.src}", file=sys.stderr)
            return 1
        entry = resolved
    for j in a.job:
        if resolve_function_uid(inst.units, j) is None:
            print(f"error: job function {j} not found in {a.src}", file=sys.stderr)
            return 1
    sch = inst.schema(entry)
    errors = sch.validate() + inst.errors
    if inst.header_errors:
        inst.warnings.append(f"{inst.header_errors} parse errors in included headers were ignored")
    for w in inst.warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors:
        return 1
    if a.print_tree:
        sch.print_tree()
    if a.in_place:
        out = a.src
    else:
        out = a.out or os.path.splitext(a.src)[0] + (".ipoint.cpp" if lang == "c++" else ".ipoint.c")
    schema_path = a.schema or out + ".schema.json"
    summary = f"{len(sch.instrumented_units())} instrumented units, ids {sch.id_base + 1}..{sch.max_id}"
    if a.dry_run:
        rendered = inst.render()  # detects overlapping edits even without writing
        print(f"dry run: would write {out} and {schema_path} ({summary}, {len(rendered)} bytes)", file=sys.stderr)
        return 0
    rendered = inst.render()
    with open(out, "wb") as f:
        f.write(rendered)
    sch.to_json(schema_path)
    print(f"wrote {out} and {schema_path} ({summary})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
