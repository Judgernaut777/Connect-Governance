"""The grants package isolation contract, enforced by scanning the source.

``connect_governance_grants`` is held to the same discipline as the Decision
Kernel (ADR-049): signing and verification are pure functions of their inputs.
No clock (validity is judged against a caller-supplied instant), no randomness
(Ed25519 is deterministic; key *generation* lives outside this package), no
network, no filesystem, no ORM, no mutable module state.

This mirrors ``tests/test_kernel_isolation.py`` for the same reason it exists:
a prose contract decays, and a grant verifier that can quietly reach the
environment is a verifier whose answers cannot be reproduced.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

GRANTS_DIR = Path(__file__).resolve().parents[1] / "src" / "connect_governance_grants"

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
    "random": "nondeterminism — Ed25519 is deterministic (ADR-050)",
    "secrets": "nondeterminism — key generation lives in connect_governance.keys",
    "subprocess": "external process (ADR-049)",
    "os": "ambient environment and I/O (ADR-049)",
    "pathlib": "filesystem access (ADR-049)",
    "connect_governance": "the application layer — grants must not depend on their caller",
}

FORBIDDEN_CALLS = {
    ("datetime", "now"): "system clock — the instant is an explicit input (ADR-049)",
    ("datetime", "utcnow"): "system clock (ADR-049)",
    ("date", "today"): "system clock (ADR-049)",
    ("time", "time"): "system clock (ADR-049)",
    ("time", "monotonic"): "system clock (ADR-049)",
    ("uuid", "uuid4"): "nondeterminism — identifiers are supplied by the caller",
}


def grants_source_files() -> list[Path]:
    files = sorted(GRANTS_DIR.rglob("*.py"))
    assert files, f"no grants sources found under {GRANTS_DIR}"
    return files


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", grants_source_files(), ids=lambda p: p.name)
def test_grants_imports_nothing_forbidden(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offending = _imported_roots(tree) & FORBIDDEN_MODULES.keys()
    assert not offending, (
        f"{path.name} imports {sorted(offending)} — forbidden in grant sign/verify: "
        + "; ".join(f"{m}: {FORBIDDEN_MODULES[m]}" for m in sorted(offending))
    )


@pytest.mark.parametrize("path", grants_source_files(), ids=lambda p: p.name)
def test_grants_reads_no_ambient_nondeterminism(path: Path) -> None:
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


@pytest.mark.parametrize("path", grants_source_files(), ids=lambda p: p.name)
def test_grants_declares_no_mutable_module_state(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if isinstance(value, (ast.Dict, ast.List, ast.Set, ast.DictComp, ast.ListComp, ast.SetComp)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Name) and not (
                        t.id.startswith("__") and t.id.endswith("__")
                    ):
                        offenders.append(t.id)
    assert not offenders, (
        f"{path.name} declares mutable module-level state {offenders}; "
        "grant signing must hold no state between calls"
    )


def test_randomness_is_confined_to_key_generation() -> None:
    """The only sanctioned source of nondeterminism in the repo is
    ``connect_governance.keys`` — and it may never be imported by a sign or
    verify path."""
    import connect_governance.keys  # noqa: F401 — must exist and import

    for path in grants_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert "connect_governance" not in _imported_roots(tree), (
            f"{path.name} imports the application layer (home of key generation)"
        )
