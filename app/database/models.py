from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String, Table, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


collection_tracks = Table(
    "collection_tracks",
    Base.metadata,
    Column("collection_id", ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    Column("track_id", ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_collection_tracks_track_id", "track_id"),
)


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (
        CheckConstraint("type IN ('manual', 'smart')", name="ck_collections_type"),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(120, collation="NOCASE"), nullable=False, unique=True)
    description = Column(String, nullable=True)
    color = Column(String(32), nullable=True)
    icon = Column(String(64), nullable=True)
    type = Column(String(16), nullable=False, default="manual")
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    tracks = relationship("Track", secondary=collection_tracks, back_populates="collections")
    rules = relationship(
        "CollectionRule",
        back_populates="collection",
        cascade="all, delete-orphan",
        order_by="CollectionRule.id",
    )

    def __repr__(self) -> str:
        return f"<Collection {self.name}>"


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True)
    name = Column(String(120, collation="NOCASE"), nullable=False, unique=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    entries = relationship(
        "PlaylistTrack",
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistTrack.position",
    )

    def __repr__(self) -> str:
        return f"<Playlist {self.name}>"


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"
    __table_args__ = (
        UniqueConstraint("playlist_id", "track_id", name="uq_playlist_tracks_playlist_track"),
        UniqueConstraint("playlist_id", "position", name="uq_playlist_tracks_playlist_position"),
        CheckConstraint("position >= 0", name="ck_playlist_tracks_position"),
        Index("ix_playlist_tracks_track_id", "track_id"),
    )

    id = Column(Integer, primary_key=True)
    playlist_id = Column(ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False)
    track_id = Column(ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False)
    added_at = Column(DateTime, default=datetime.now, nullable=False)

    playlist = relationship("Playlist", back_populates="entries")
    track = relationship("Track", back_populates="playlist_entries")


class TrackHistory(Base):
    __tablename__ = "track_history"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('selected', 'played', 'added', 'playlist_used')",
            name="ck_track_history_event_type",
        ),
        Index("ix_track_history_track_created_at", "track_id", "created_at"),
        Index("ix_track_history_event_created_at", "event_type", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    track_id = Column(ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    track = relationship("Track", back_populates="history_events")


class CollectionRule(Base):
    __tablename__ = "collection_rules"
    __table_args__ = (Index("ix_collection_rules_collection_id", "collection_id"),)

    id = Column(Integer, primary_key=True)
    collection_id = Column(ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    field = Column(String(64), nullable=False)
    operator = Column(String(16), nullable=False)
    value = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    collection = relationship("Collection", back_populates="rules")


IMPORT_STATUSES = (
    "pending",
    "scanning",
    "reading_metadata",
    "imported",
    "skipped",
    "failed",
    "cancelled",
)


class ImportJob(Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'scanning', 'reading_metadata', 'imported', "
            "'skipped', 'failed', 'cancelled')",
            name="ck_import_jobs_status",
        ),
        Index("ix_import_jobs_status", "status"),
    )

    id = Column(Integer, primary_key=True)
    status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    total_items = Column(Integer, nullable=False, default=0)
    processed_items = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)

    items = relationship(
        "ImportItem",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ImportItem.id",
    )


class ImportItem(Base):
    __tablename__ = "import_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'scanning', 'reading_metadata', 'imported', "
            "'skipped', 'failed', 'cancelled')",
            name="ck_import_items_status",
        ),
        UniqueConstraint("job_id", "filepath", name="uq_import_items_job_filepath"),
        Index("ix_import_items_job_status", "job_id", "status"),
    )

    id = Column(Integer, primary_key=True)
    job_id = Column(ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False)
    filepath = Column(String, nullable=False)
    status = Column(String(32), nullable=False, default="pending")
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    job = relationship("ImportJob", back_populates="items")


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True)

    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    album = Column(String, nullable=True)
    genre = Column(String, nullable=True)

    filepath = Column(String, unique=True, nullable=False)

    bpm = Column(Float, nullable=True)
    key = Column(String, nullable=True)

    duration = Column(Float, nullable=True)
    bitrate = Column(Integer, nullable=True)
    sample_rate = Column(Integer, nullable=True)

    file_hash = Column(String, nullable=True)
    status = Column(String, default="ok")
    import_file_size = Column(Integer, nullable=True)
    import_file_modified_at = Column(DateTime, nullable=True)

    energy = Column(Integer, default=0)
    analyzed_at = Column(DateTime, nullable=True)
    analyzer_version = Column(String, nullable=True)
    bpm_confidence = Column(Float, nullable=True)
    key_confidence = Column(Float, nullable=True)
    energy_confidence = Column(Float, nullable=True)
    primary_genre_confidence = Column(Float, nullable=True)
    secondary_genres_json = Column(String, nullable=True)
    styles_json = Column(String, nullable=True)
    rating = Column(Integer, default=0)
    is_favorite = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.now)

    collections = relationship("Collection", secondary=collection_tracks, back_populates="tracks")
    playlist_entries = relationship("PlaylistTrack", back_populates="track")
    history_events = relationship("TrackHistory", back_populates="track")

class TrackMetadataHistory(Base):
    __tablename__ = "track_metadata_history"
    id = Column(Integer, primary_key=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    changed_at = Column(DateTime, default=datetime.now, nullable=False)
    fields_json = Column(String, nullable=False)
    previous_json = Column(String, nullable=False)
    new_json = Column(String, nullable=False)
    origin = Column(String, nullable=False)
    status = Column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<Track {self.artist} - {self.title}>"
