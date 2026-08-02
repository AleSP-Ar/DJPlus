import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Base, ImportJob, Track, TrackHistory
from app.database.unit_of_work import UnitOfWork


class TrackingSession(Session):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.was_closed = False

    def close(self):
        self.was_closed = True
        super().close()


class UnitOfWorkTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, class_=TrackingSession)

    def test_commits_multiple_repositories_with_one_shared_session(self):
        with UnitOfWork(session_factory=self.session_factory) as unit_of_work:
            self.assertIs(unit_of_work.tracks.session, unit_of_work.session)
            self.assertIs(unit_of_work.history.session, unit_of_work.session)
            self.assertIs(unit_of_work.imports.session, unit_of_work.session)
            track = Track(title="Atomic", artist="DJ Plus", filepath="atomic.mp3")
            unit_of_work.session.add(track)
            unit_of_work.session.flush()
            unit_of_work.history.record_event(track.id, "added", commit=False)
            unit_of_work.imports.create_job(commit=False)

        verification = self.session_factory()
        try:
            self.assertEqual(verification.query(Track).count(), 1)
            self.assertEqual(verification.query(TrackHistory).count(), 1)
            self.assertEqual(verification.query(ImportJob).count(), 1)
        finally:
            verification.close()

    def test_rolls_back_all_repository_work_when_an_exception_occurs(self):
        with self.assertRaises(RuntimeError):
            with UnitOfWork(session_factory=self.session_factory) as unit_of_work:
                track = Track(title="Rollback", artist="DJ Plus", filepath="rollback.mp3")
                unit_of_work.session.add(track)
                unit_of_work.session.flush()
                unit_of_work.history.record_event(track.id, "added", commit=False)
                unit_of_work.imports.create_job(commit=False)
                raise RuntimeError("force rollback")

        verification = self.session_factory()
        try:
            self.assertEqual(verification.query(Track).count(), 0)
            self.assertEqual(verification.query(TrackHistory).count(), 0)
            self.assertEqual(verification.query(ImportJob).count(), 0)
        finally:
            verification.close()

    def test_closes_the_session_after_context_exit(self):
        with UnitOfWork(session_factory=self.session_factory) as unit_of_work:
            session = unit_of_work.session

        self.assertTrue(session.was_closed)

    def test_rejects_commit_outside_context(self):
        with self.assertRaises(RuntimeError):
            UnitOfWork(session_factory=self.session_factory).commit()
