from __future__ import annotations

from pathlib import Path
import sqlite3

from sqlalchemy import create_engine, text
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
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            Base.metadata.create_all(engine)
        else:
            cursor.execute("PRAGMA table_info(tracks)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            if "file_hash" not in existing_columns:
                with engine.connect() as connection:
                    connection.execute(text("ALTER TABLE tracks ADD COLUMN file_hash VARCHAR"))

            if "status" not in existing_columns:
                with engine.connect() as connection:
                    connection.execute(text("ALTER TABLE tracks ADD COLUMN status VARCHAR DEFAULT 'ok'"))

        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    init_database()
