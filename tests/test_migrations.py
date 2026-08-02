"""The Alembic head and the ORM metadata must agree.

A migration that has drifted from the models is worse than no migration: it
produces a deployment whose schema differs from what every test exercised. This
runs the real migrations against a real database file and then asks Alembic
whether anything remains to be generated. Anything at all is a failure.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from connect_governance.db.models import Base

REPO = Path(__file__).resolve().parents[1]


def _alembic_config(url: str) -> Config:
    cfg = Config(str(REPO / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migration_head_matches_the_orm_metadata(tmp_path: Path) -> None:
    from alembic import command

    db = tmp_path / "drift.db"
    url = f"sqlite+pysqlite:///{db}"
    cfg = _alembic_config(url)
    command.upgrade(cfg, "head")

    engine = create_engine(url, future=True)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"render_as_batch": True})
        diff = compare_metadata(ctx, Base.metadata)

    assert not diff, (
        "the Alembic head has drifted from the ORM models; "
        f"outstanding changes: {diff}"
    )


def test_migration_creates_every_governed_table(tmp_path: Path) -> None:
    from alembic import command

    db = tmp_path / "tables.db"
    url = f"sqlite+pysqlite:///{db}"
    command.upgrade(_alembic_config(url), "head")

    engine = create_engine(url, future=True)
    present = set(inspect(engine).get_table_names())
    expected = set(Base.metadata.tables) | {"alembic_version"}
    assert expected <= present, f"missing tables: {sorted(expected - present)}"


def test_there_is_exactly_one_migration_head() -> None:
    """Branching migration history is an operational trap in a governance store."""
    script = ScriptDirectory(str(REPO / "alembic"))
    assert len(script.get_heads()) == 1, f"multiple heads: {script.get_heads()}"
