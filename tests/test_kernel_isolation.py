"""The Kernel isolation contract, enforced by scanning the source.

ADR-049 forbids the Kernel from depending on the web framework, the ORM, the
database, the network, mutable global state, the system clock, randomness, or
any external service.

A prose contract decays. This scans ``connect_governance_kernel``'s AST on every
run, so a future contributor cannot quietly reintroduce a dependency and leave
the corpus claiming a determinism the code no longer has. That failure mode is
the one the Connect corpus most needs to avoid: a document asserting a property
the implementation stopped honouring.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

KERNEL_DIR = Path(__file__).resolve().parents[1] / "src" / "connect_governance_kernel"

#: Top-level modules the Kernel may never import, and why.
FORBIDDEN_MODULES = {
    "fastapi": "web framework (ADR-049)",
    "starlette": "web framework (ADR-049)",
    "uvicorn": "web server (ADR-049)",
    "sqlalchemy": "ORM (ADR-049)",
    "sqlite3": "database driver (ADR-049)",
    "alembic": "migrations (ADR-049)",
    "socket": "network access (ADR-049)",
    "http": "network access (ADR-049)",
    "urllib": "network access (ADR-049)",
    "requests": "network access (ADR-049)",
    "httpx": "network access (ADR-049)",
    "random": "nondeterminism (ADR-049)",
    "secrets": "nondeterminism (ADR-049)",
    "subprocess": "external process (ADR-049)",
    "os": "ambient environment and I/O (ADR-049)",
    "pathlib": "filesystem access (ADR-049)",
    "connect_governance": "the application layer — the Kernel must not depend on its own caller",
}

#: Attribute call chains that read ambient nondeterministic state.
FORBIDDEN_CALLS = {
    ("datetime", "now"): "system clock — evaluation_time is an explicit input (ADR-049)",
    ("datetime", "utcnow"): "system clock — evaluation_time is an explicit input (ADR-049)",
    ("date", "today"): "system clock (ADR-049)",
    ("time", "time"): "system clock (ADR-049)",
    ("time", "monotonic"): "system clock (ADR-049)",
    ("uuid", "uuid4"): "nondeterminism — identifiers are supplied by the caller (ADR-049)",
}


def kernel_source_files() -> list[Path]:
    files = sorted(KERNEL_DIR.rglob("*.py"))
    assert files, f"no Kernel sources found under {KERNEL_DIR}"
    return files


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # Relative imports (level > 0) stay inside the Kernel package.
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", kernel_source_files(), ids=lambda p: p.name)
def test_kernel_imports_nothing_forbidden(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offending = _imported_roots(tree) & FORBIDDEN_MODULES.keys()
    assert not offending, (
        f"{path.name} imports {sorted(offending)} — forbidden in the Decision Kernel: "
        + "; ".join(f"{m}: {FORBIDDEN_MODULES[m]}" for m in sorted(offending))
    )


@pytest.mark.parametrize("path", kernel_source_files(), ids=lambda p: p.name)
def test_kernel_reads_no_ambient_nondeterminism(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if isinstance(owner, ast.Name):
                key = (owner.id, node.func.attr)
                if key in FORBIDDEN_CALLS:
                    found.append(f"{owner.id}.{node.func.attr}() — {FORBIDDEN_CALLS[key]}")
    assert not found, f"{path.name} reads ambient nondeterministic state: {found}"


@pytest.mark.parametrize("path", kernel_source_files(), ids=lambda p: p.name)
def test_kernel_declares_no_mutable_module_state(path: Path) -> None:
    """Module-level mutable containers are shared state across evaluations.

    Immutable module constants (str, int, tuple, frozenset) are fine; a dict,
    list, or set at module scope is a place for one evaluation to influence the
    next, which would break determinism in a way no unit test would notice.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if isinstance(value, (ast.Dict, ast.List, ast.Set, ast.DictComp, ast.ListComp, ast.SetComp)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    # Dunder names (__all__) are module protocol read at import
                    # time, not state carried between evaluations. Everything
                    # else — caches, registries, accumulators — is a place for
                    # one evaluation to influence the next, and is refused.
                    if isinstance(t, ast.Name) and not (
                        t.id.startswith("__") and t.id.endswith("__")
                    ):
                        offenders.append(t.id)
    assert not offenders, (
        f"{path.name} declares mutable module-level state {offenders}; "
        "the Kernel must hold no state between evaluations (ADR-049)"
    )


def test_kernel_package_imports_cleanly_without_app_extras() -> None:
    """The Kernel must be usable with only its own dependency installed.

    If this fails, the Kernel has acquired a dependency on the application
    layer's extras and is no longer independently substitutable.
    """
    import connect_governance_kernel as k

    assert k.KERNEL_VERSION
    assert k.Outcome.ALLOWED == "Allowed"
    assert k.Outcome.DENIED == "Denied"
    assert k.Outcome.APPROVAL_REQUIRED == "ApprovalRequired"
