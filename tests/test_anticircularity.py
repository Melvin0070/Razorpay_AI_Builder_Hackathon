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
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.rsplit(".", node.level - 1)[0] if node.level > 1 else package
                found.add(f"{base}.{node.module}" if node.module else base)
            elif node.module:
                found.add(node.module)
    return {m for m in found if m == PKG or m.startswith(PKG + ".")}


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
                stack.append(imp)
                # ``from leakproof.x import y`` may name a submodule y
                stack.extend(m for m in modules if m.startswith(imp + "."))
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
