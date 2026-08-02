import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Track
from app.repository.history_repository import HistoryRepository


class HistoryRepositoryTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        self.repository = HistoryRepository(session=self.session)
        self.track = Track(title="First", artist="Artist", filepath="first.mp3")
        self.other_track = Track(title="Second", artist="Artist", filepath="second.mp3")
        self.session.add_all((self.track, self.other_track))
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_records_queries_and_relates_history_events(self):
        self.repository.record_event(self.track.id, "selected")
        self.repository.record_event(self.track.id, "played")
        self.repository.record_event(self.other_track.id, "added")
        selected = self.repository.list_history(track_id=self.track.id, event_type="selected")
        self.assertEqual([event.event_type for event in selected], ["selected"])
        self.assertEqual(self.repository.count_history(track_id=self.track.id), 2)
        self.assertEqual(self.repository.count_history(event_type="added"), 1)
        self.assertEqual(len(self.track.history_events), 2)

    def test_invalid_track_and_event_type_are_rejected(self):
        with self.assertRaises(ValueError):
            self.repository.record_event(999, "selected")
        with self.assertRaises(ValueError):
            self.repository.record_event(self.track.id, "unknown")
