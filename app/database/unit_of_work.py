"""Shared transactional boundary for multi-repository application operations."""

from .database import SessionLocal
from app.repository.history_repository import HistoryRepository
from app.repository.import_repository import ImportRepository
from app.repository.track_repository import TrackRepository


class UnitOfWork:
    """Provide one session and one commit/rollback boundary to cooperating repositories."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory
        self.session = None
        self.tracks = None
        self.history = None
        self.imports = None

    def __enter__(self):
        self.session = self.session_factory()
        self.tracks = TrackRepository(session=self.session)
        self.history = HistoryRepository(session=self.session)
        self.imports = ImportRepository(session=self.session)
        return self

    def __exit__(self, exception_type, exception, traceback):
        try:
            if exception_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False

    def commit(self):
        self._require_session().commit()

    def rollback(self):
        self._require_session().rollback()

    def close(self):
        if self.session is not None:
            self.session.close()

    def _require_session(self):
        if self.session is None:
            raise RuntimeError("El UnitOfWork debe usarse dentro de un bloque with.")
        return self.session
