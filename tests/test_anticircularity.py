"""D12: the generator's module graph must never reach the rate-card config, and
the other ground-truth walls from the strategy doc hold the same way. Static,
AST-based, so a lane cannot satisfy it by importing lazily inside a function.
"""

import ast
from pathlib import Path

from tests.conftest import SRC

PKG = "leakproof"

#: importer package -> packages it must never reach, transitively
WALLS: dict[str, set[str]] = {
    f"{PKG}.generator": {f"{PKG}.ratecard", f"{PKG}.labels", f"{PKG}.evidence", f"{PKG}.detect"},
    f"{PKG}.ratecard": {f"{PKG}.generator"},
    f"{PKG}.labels": {f"{PKG}.evidence", f"{PKG}.ratecard", f"{PKG}.generator"},
    f"{PKG}.evidence": {f"{PKG}.labels", f"{PKG}.generator"},
    f"{PKG}.detect": {f"{PKG}.generator", f"{PKG}.labels"},
}


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _modules() -> dict[str, Path]:
    return {_module_name(p): p for p in SRC.rglob("*.py")}


def _imports(path: Path, module: str) -> set[str]:
    """Dotted names a module's import statements can bind, resolved precisely.

    ``from leakproof import contract`` binds ``leakproof.contract`` and nothing
    else. An earlier version recorded only the bare package and let the
    reachability walk expand it into every submodule, which made any module
    importing ``leakproof.gates`` (whose first import is exactly that form)
    "reach" every lane package and fail the walls for reasons unrelated to
    the importer's own graph (lane C, Wave 1).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.rsplit(".", node.level - 1)[0] if node.level > 1 else package
                base = f"{base}.{node.module}" if node.module else base
            else:
                base = node.module or ""
            if not base:
                continue
            found.add(base)
            # ``from a.b import c`` may name a submodule ``a.b.c``; names that
            # are not modules are dropped by the reachability walk.
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return {m for m in found if m == PKG or m.startswith(PKG + ".")}


def _with_ancestors(name: str) -> list[str]:
    """Importing ``a.b.c`` also executes the ``a`` and ``a.b`` package inits."""
    parts = name.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts) + 1)]


def _reachable(root: str, modules: dict[str, Path]) -> set[str]:
    seen: set[str] = set()
    stack = [m for m in modules if m == root or m.startswith(root + ".")]
    while stack:
        mod = stack.pop()
        if mod in seen:
            continue
        seen.add(mod)
        if mod in modules:
            for imp in _imports(modules[mod], mod):
                stack.extend(_with_ancestors(imp))
    return seen


def test_ground_truth_walls_hold():
    modules = _modules()
    violations = []
    for importer, forbidden in WALLS.items():
        reach = _reachable(importer, modules)
        for f in sorted(forbidden):
            hit = sorted(m for m in reach if m == f or m.startswith(f + "."))
            if hit:
                violations.append(f"{importer} reaches {f} via {hit}")
    assert not violations, "\n".join(violations)


def test_walls_cover_every_lane_package_that_encodes_a_source():
    # Two encodings of the rate card, two readings of the policy text.
    assert f"{PKG}.ratecard" in WALLS[f"{PKG}.generator"]
    assert f"{PKG}.labels" in WALLS[f"{PKG}.evidence"]


def test_from_package_import_resolves_to_the_named_submodule_only():
    modules = _modules()
    gates = f"{PKG}.gates"
    assert gates in modules
    imports = _imports(modules[gates], gates)
    assert f"{PKG}.contract" in imports
    assert not any(m.startswith(f"{PKG}.generator") for m in imports)


def test_shared_gate_module_is_wall_neutral():
    # Every lane that ships a hard gate imports leakproof.gates; that import must
    # not count as reaching any walled package.
    modules = _modules()
    reach = _reachable(f"{PKG}.gates", modules)
    forbidden = set().union(*WALLS.values())
    hits = sorted(m for m in reach if any(m == f or m.startswith(f + ".") for f in forbidden))
    assert not hits, f"leakproof.gates reaches {hits}"
