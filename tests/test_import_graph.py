"""The architectural invariant: no path from an agent to an adapter bypasses
the kernel. Walk the import graph via AST and fail if one exists."""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "bsos"

# Layers that must never import adapters directly: they reach them only via
# ToolContext.adapters, which only the kernel guard populates.
RESTRICTED_DIRS = ("agents", "skills", "orchestrator")
FORBIDDEN_PREFIX = "bsos.adapters"

# The sanctioned composition root and the adapters package itself.
ALLOWED_FILES = set()


def _imports_of(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def test_no_import_path_bypasses_the_kernel():
    violations = []
    for layer in RESTRICTED_DIRS:
        for py in (PKG / layer).rglob("*.py"):
            if py in ALLOWED_FILES:
                continue
            for imported in _imports_of(py):
                if imported == FORBIDDEN_PREFIX or imported.startswith(FORBIDDEN_PREFIX + "."):
                    violations.append(f"{py.relative_to(REPO)} imports {imported}")
    assert not violations, (
        "adapter imports outside the kernel path:\n  " + "\n  ".join(violations)
    )


def test_agents_do_not_import_skills_directly():
    """Agents act through Kernel.invoke by tool name, never by importing a skill."""
    violations = []
    for py in (PKG / "agents").rglob("*.py"):
        for imported in _imports_of(py):
            if imported.startswith("bsos.skills"):
                violations.append(f"{py.relative_to(REPO)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_no_scraper_libraries_in_dependency_tree():
    """P7: fail the build if a scraper library appears in project dependencies."""
    denylist = {"instaloader", "instagrapi", "instagram-scraper", "instagram_private_api",
                "selenium-instagram", "igramscraper"}
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8").lower()
    hits = {lib for lib in denylist if lib in pyproject}
    assert not hits, f"scraper libraries present in dependency tree: {hits}"
    for py in PKG.rglob("*.py"):
        for imported in _imports_of(py):
            root = imported.split(".")[0]
            assert root not in denylist, f"{py} imports scraper library {root}"
