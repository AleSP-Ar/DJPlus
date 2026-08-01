from __future__ import annotations

from pathlib import Path
import sqlite3

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    from .models import Base
except ImportError:  # pragma: no cover - fallback for direct execution
    from models import Base


DATABASE_URL = "sqlite:///data/djplus.db"

Path("data").mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine)


def init_database() -> None:
    conn = sqlite3.connect("data/djplus.db")
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracks'")
        if cursor.fetchone() is None:
            Base.metadata.create_all(engine)
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracks'")
            if cursor.fetchone() is not None:
                cursor.execute("DROP TABLE tracks")
            Base.metadata.create_all(engine)
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    init_database()
