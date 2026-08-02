import inspect
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from app.services.conversation_session import (
    ConversationMessageDTO,
    ConversationSession,
    ConversationSessionError,
    MessageRole,
)


class ConversationSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = ConversationSession("session-1", metadata={"origin": "test"})

    def test_creates_a_live_session_with_immutable_snapshot(self):
        snapshot = self.session.snapshot()

        self.assertEqual(snapshot.session_id, "session-1")
        self.assertEqual(snapshot.conversation_version, "1.0")
        self.assertEqual(snapshot.metadata["origin"], "test")
        with self.assertRaises(FrozenInstanceError):
            snapshot.session_id = "other"
        with self.assertRaises(TypeError):
            snapshot.metadata["origin"] = "changed"

    def test_adds_immutable_messages_in_chronological_order(self):
        first = self.session.add_message(MessageRole.USER, "first")
        second = self.session.add_message(MessageRole.ASSISTANT, "second")

        self.assertEqual(self.session.history(), (first, second))
        self.assertLessEqual(first.created_at_utc, second.created_at_utc)
        with self.assertRaises(FrozenInstanceError):
            first.content = "changed"

    def test_clears_history_and_updates_last_activity(self):
        before = self.session.snapshot().last_activity_utc
        self.session.add_message(MessageRole.USER, "one")
        self.session.update_last_activity()
        self.session.clear_history()

        self.assertEqual(self.session.get_message_count(), 0)
        self.assertEqual(self.session.get_history(), ())
        self.assertGreaterEqual(self.session.snapshot().last_activity_utc, before)

    def test_close_preserves_history_and_blocks_future_mutation(self):
        self.session.add_message(MessageRole.USER, "one")
        self.session.close()

        self.assertTrue(self.session.is_closed)
        self.assertEqual(self.session.message_count(), 1)
        with self.assertRaises(ConversationSessionError):
            self.session.add_message(MessageRole.USER, "two")
        with self.assertRaises(ConversationSessionError):
            self.session.clear_history()

    def test_message_contract_requires_enum_and_utc_timestamp(self):
        with self.assertRaises(ConversationSessionError):
            ConversationMessageDTO("message-1", "user", "content", datetime.now(timezone.utc))
        with self.assertRaises(ConversationSessionError):
            ConversationMessageDTO("message-1", MessageRole.USER, "content", datetime.now())

    def test_session_has_no_infrastructure_imports(self):
        source = inspect.getsource(__import__("app.services.conversation_session", fromlist=["*"]))

        self.assertNotIn("app.repository", source)
        self.assertNotIn("sqlalchemy", source.lower())
        self.assertNotIn("sqlite3", source.lower())
        self.assertNotIn("pathlib", source.lower())
