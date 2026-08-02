"""Engine and session helpers.

SQLite is the first-slice persistence mechanism, not a constitutional
requirement (ADR-049). Nothing above this module should assume it.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def make_engine(url: str = "sqlite+pysqlite:///:memory:"):
    engine = create_engine(url, future=True)
    return engine


def create_all(engine) -> None:
    """Create the schema directly.

    Used by tests and by the in-memory case. A real deployment uses the Alembic
    migrations so that schema history is auditable rather than implied.
    """
    Base.metadata.create_all(engine)


def session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)
