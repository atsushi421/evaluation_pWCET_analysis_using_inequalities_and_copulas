"""Sequential R-vine construction (Dissmann et al., 2013) with a custom pair-copula selector.

pyvinecopulib selects pair-copula families with its built-in criteria only
(loglik, aic, bic, mbic, mbicv). To use any criterion of :mod:`copula.select`
(cross-validation, tail-concentration fit, hybrid) and the Kendall's tau
independence pre-test inside a vine, this module rebuilds the tree-wise
maximum-spanning-tree algorithm, selects every pair copula with
:func:`copula.select.select`, and converts the result into a
:class:`pyvinecopulib.Vinecop` (whose C++ engine then does the simulation).
The conversion is verified by comparing the vine log-likelihood with the sum
of the pair-copula log-likelihoods.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pyvinecopulib as pv

from .families import F, resolve_pool
from .select import Selection, kendall_tau, select

_SWAPPED_ROTATION = {0: 0, 90: 270, 180: 180, 270: 90}


def swap_arguments(bicop: pv.Bicop, pseudo: np.ndarray | None = None) -> pv.Bicop:
    """The copula of (V, U) given the copula of (U, V).

    Rotations 90 and 270 are exchanged, the two asymmetry parameters of the
    Tawn copula are swapped, and the nonparametric TLL copula is refitted on
    the swapped pseudo-observations.
    """
    fam, rot = bicop.family, bicop.rotation
    if fam == F.indep:
        return pv.Bicop()
    if fam == F.tll:
        if pseudo is None:
            raise ValueError("swapping a TLL copula needs the pseudo-observations for refitting")
        b = pv.Bicop(family=F.tll)
        b.fit(np.asfortranarray(pseudo[:, ::-1]), controls=pv.FitControlsBicop(family_set=[F.tll]))
        return b
    params = np.array(bicop.parameters, dtype=float)
    if fam == F.tawn:
        params = params[[1, 0, 2], :]
    return pv.Bicop(family=fam, rotation=_SWAPPED_ROTATION[rot], parameters=params)


@dataclass
class Edge:
    a: int                      # conditioned variables (0-based); ``pseudo`` columns are (a, b)
    b: int
    cond: frozenset             # conditioning set
    pseudo: np.ndarray          # n x 2 pseudo-observations (u_{a|D}, u_{b|D})
    selection: Selection
    parents: tuple              # the two nodes of the previous tree joined by this edge
    _h_a: np.ndarray | None = None
    _h_b: np.ndarray | None = None

    @property
    def variables(self) -> frozenset:
        return frozenset((self.a, self.b)) | self.cond

    @property
    def bicop(self) -> pv.Bicop:
        return self.selection.bicop

    @property
    def loglik(self) -> float:
        return float(self.bicop.loglik(self.pseudo))

    def h_given(self, x: int) -> np.ndarray:
        """Pseudo-observations of x conditioned on the other variable and D."""
        if x == self.a:
            if self._h_a is None:
                self._h_a = self.bicop.hfunc2(self.pseudo)   # P(U_a <= u_a | U_b = u_b)
            return self._h_a
        if x == self.b:
            if self._h_b is None:
                self._h_b = self.bicop.hfunc1(self.pseudo)   # P(U_b <= u_b | U_a = u_a)
            return self._h_b
        raise KeyError(x)

    def describe(self, tree: int) -> dict:
        s = self.selection
        lo, up = _tail(self.bicop)
        return {"tree": tree + 1, "conditioned": (self.a + 1, self.b + 1),
                "conditioning": tuple(sorted(v + 1 for v in self.cond)), "label": s.label,
                "tau": s.tau, "indep_pvalue": s.indep_pvalue, "independent_by_test": s.independent_by_test,
                "lambda_l": lo, "lambda_u": up, "loglik": self.loglik, "seconds": s.seconds}


def _tail(bicop: pv.Bicop) -> tuple[float, float]:
    from .families import tail_dependence_of
    return tail_dependence_of(bicop)


def max_spanning_tree(weight: np.ndarray, adjacent: np.ndarray) -> list[tuple[int, int]]:
    """Prim's algorithm for the spanning tree with maximum total edge weight."""
    m = len(weight)
    visited = np.zeros(m, dtype=bool)
    best = np.full(m, -np.inf)
    parent = np.zeros(m, dtype=int)
    visited[0] = True
    best[adjacent[0]] = weight[0, adjacent[0]]
    edges = []
    for _ in range(m - 1):
        cand = np.where(visited, -np.inf, best)
        j = int(np.argmax(cand))
        if not np.isfinite(cand[j]):
            raise ValueError("proximity graph is not connected")
        visited[j] = True
        edges.append((int(parent[j]), j))
        upd = (~visited) & adjacent[j] & (weight[j] > best)
        best[upd] = weight[j, upd]
        parent[upd] = j
    return edges


@dataclass
class VineFit:
    vinecop: pv.Vinecop
    trees: list
    matrix: np.ndarray
    seconds: float
    edge_loglik: float

    @property
    def dim(self) -> int:
        return len(self.trees) + 1

    def edges(self) -> list[dict]:
        return [e.describe(t) for t, tree in enumerate(self.trees) for e in tree]

    def n_independent(self) -> int:
        return sum(e.bicop.family == F.indep for tree in self.trees for e in tree)


def fit_vine(U: np.ndarray, pool="par", criterion: str = "bic", indep_alpha: float | None = None,
             trunc_lvl: int | None = None, **select_kwargs) -> VineFit:
    """Fit an R-vine copula to pseudo-observations ``U`` (n x d, d >= 2).

    Structure: tree-wise maximum spanning trees on |Kendall's tau| (Dissmann
    et al., 2013). Pair copulas: :func:`copula.select.select` with ``pool``,
    ``criterion``, ``indep_alpha`` and ``select_kwargs``. Trees above
    ``trunc_lvl`` receive independence copulas.
    """
    U = np.asfortranarray(np.asarray(U, dtype=float))
    n, d = U.shape
    if d < 2:
        raise ValueError("need at least two variables")
    t0 = time.perf_counter()

    def pick(ps: np.ndarray, level: int) -> Selection:
        if trunc_lvl is not None and level >= trunc_lvl:
            return Selection(pv.Bicop(), criterion, pool if isinstance(pool, str) else "custom",
                             kendall_tau(ps), 1.0, True)
        return select(ps, pool, criterion, indep_alpha, **select_kwargs)

    trees: list[list[Edge]] = []
    weight = np.full((d, d), -np.inf)
    adjacent = ~np.eye(d, dtype=bool)
    for i in range(d):
        for j in range(i + 1, d):
            weight[i, j] = weight[j, i] = abs(kendall_tau(U[:, [i, j]]))
    edges = []
    for i, j in max_spanning_tree(weight, adjacent):
        a, b = (i, j) if i < j else (j, i)
        ps = np.asfortranarray(U[:, [a, b]])
        edges.append(Edge(a, b, frozenset(), ps, pick(ps, 0), parents=(a, b)))
    trees.append(edges)

    for level in range(1, d - 1):
        prev = trees[-1]
        m = len(prev)
        weight = np.full((m, m), -np.inf)
        adjacent = np.zeros((m, m), dtype=bool)
        cache = {}
        for i in range(m):
            for j in range(i + 1, m):
                e, f = prev[i], prev[j]
                if not (set(e.parents) & set(f.parents)):
                    continue  # proximity condition: must share a node of the previous tree
                cond = e.variables & f.variables
                (x,) = tuple(e.variables - cond)
                (y,) = tuple(f.variables - cond)
                ps = np.asfortranarray(np.column_stack([e.h_given(x), f.h_given(y)]))
                weight[i, j] = weight[j, i] = abs(kendall_tau(ps))
                adjacent[i, j] = adjacent[j, i] = True
                cache[(i, j)] = (x, y, cond, ps)
        edges = []
        for i, j in max_spanning_tree(weight, adjacent):
            i, j = (i, j) if i < j else (j, i)
            x, y, cond, ps = cache[(i, j)]
            edges.append(Edge(x, y, frozenset(cond), ps, pick(ps, level), parents=(i, j)))
        trees.append(edges)

    matrix, pair_copulas = to_matrix(trees, d)
    vinecop = pv.Vinecop.from_structure(matrix=matrix, pair_copulas=pair_copulas)
    ll_edges = sum(e.loglik for tree in trees for e in tree)
    ll_vine = float(vinecop.loglik(U))
    if abs(ll_edges - ll_vine) > 1e-6 * max(1.0, abs(ll_edges)):
        raise RuntimeError(f"vine construction inconsistent: sum of pair-copula loglik {ll_edges:.6f}"
                           f" != vine loglik {ll_vine:.6f}")
    return VineFit(vinecop, trees, matrix, time.perf_counter() - t0, ll_edges)


def to_matrix(trees: list[list[Edge]], d: int) -> tuple[np.ndarray, list[list[pv.Bicop]]]:
    """R-vine matrix in vinecopulib's convention and the pair copulas indexed [tree][edge].

    Column j holds its diagonal variable at row d-1-j and, at row t, the
    partner variable of the tree-t edge whose conditioned set contains the
    diagonal variable; that edge's conditioning set is the column entries
    above row t. The pair copula of column j is oriented so that its first
    argument belongs to the diagonal variable.
    """
    remaining = [list(t) for t in trees]
    matrix = np.zeros((d, d), dtype=np.uint64)
    pair_copulas: list[list[pv.Bicop | None]] = [[None] * (d - 1 - t) for t in range(d - 1)]
    diagonals = []
    for j in range(d - 1):
        t_top = d - 2 - j
        if len(remaining[t_top]) != 1:
            raise RuntimeError("tree sequence is not a regular vine")
        e = remaining[t_top][0]
        x = e.a
        chain = []
        for t in range(t_top, -1, -1):
            chain.append((t, e))
            y = e.b if e.a == x else e.a
            matrix[t, j] = y + 1
            pair_copulas[t][j] = e.bicop if e.a == x else swap_arguments(e.bicop, e.pseudo)
            remaining[t].remove(e)
            if t > 0:
                parents = [trees[t - 1][p] for p in e.parents]
                (e,) = [c for c in parents if x in (c.a, c.b)]
        for t, e in chain:
            expected = frozenset(int(matrix[s, j]) - 1 for s in range(t))
            if e.cond != expected:
                raise RuntimeError("conditioning set does not match the matrix column")
        matrix[d - 1 - j, j] = x + 1
        diagonals.append(x)
    (last,) = set(range(d)) - set(diagonals)
    matrix[0, d - 1] = last + 1
    if any(remaining[t] for t in range(d - 1)):
        raise RuntimeError("edges left over after matrix construction")
    return matrix, pair_copulas  # type: ignore[return-value]


def fit_vine_native(U: np.ndarray, pool="par", criterion: str = "bic", preselect: bool = True,
                    psi0: float = 0.9, num_threads: int = 1) -> pv.Vinecop:
    """pyvinecopulib's own Dissmann selection (criteria loglik/aic/bic/mbic/mbicv only)."""
    controls = pv.FitControlsVinecop(family_set=resolve_pool(pool), selection_criterion=criterion, psi0=psi0,
                                     preselect_families=preselect, allow_rotations=True,
                                     tree_criterion="tau", num_threads=num_threads)
    return pv.Vinecop.from_data(np.asfortranarray(np.asarray(U, dtype=float)), controls=controls)


def edge_sets(vinecop: pv.Vinecop) -> list[set[frozenset]]:
    """Conditioned pairs per tree of a pyvinecopulib vine, for structure comparisons."""
    m = vinecop.matrix
    d = m.shape[0]
    out = []
    for t in range(d - 1):
        s = set()
        for j in range(d - 1 - t):
            s.add(frozenset((int(m[d - 1 - j, j]), int(m[t, j]))))
        out.append(s)
    return out


def edge_sets_of_fit(fit: VineFit) -> list[set[frozenset]]:
    return [{frozenset((e.a + 1, e.b + 1)) for e in tree} for tree in fit.trees]
