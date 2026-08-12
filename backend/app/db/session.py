"""SQLAlchemy engine/session setup.

SQLite note: background threads (run executors, event loggers) access the DB
concurrently with the FastAPI request thread.  SQLite requires
check_same_thread=False to allow this — it is safe here because SQLAlchemy
manages per-session isolation.  Postgres does not need this flag.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings

_settings = get_settings()

# Build connect_args: SQLite needs check_same_thread=False for multi-threaded use.
_connect_args: dict = {}
if _settings.database_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_engine(
    _settings.database_url,
    connect_args=_connect_args,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
