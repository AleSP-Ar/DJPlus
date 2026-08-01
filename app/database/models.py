from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True)

    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    album = Column(String, nullable=True)

    filepath = Column(String, unique=True, nullable=False)

    bpm = Column(Float, nullable=True)
    key = Column(String, nullable=True)

    duration = Column(Float, nullable=True)

    file_hash = Column(String, nullable=True)
    status = Column(String, default="ok")

    energy = Column(Integer, default=0)
    rating = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return f"<Track {self.artist} - {self.title}>"
