"""In-memory, provider-neutral conversation state for one live assistant session."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from uuid import uuid4


class ConversationSessionError(ValueError):
    """Raised when a conversation lifecycle or message contract is invalid."""


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class ConversationSessionDTO:
    session_id: str
    created_at_utc: datetime
    last_activity_utc: datetime
    conversation_version: str
    metadata: object = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self):
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ConversationSessionError("El identificador de sesión es obligatorio.")
        _validate_utc_timestamp(self.created_at_utc, "La creación de sesión")
        _validate_utc_timestamp(self.last_activity_utc, "La actividad de sesión")
        if self.last_activity_utc < self.created_at_utc:
            raise ConversationSessionError("La última actividad no puede preceder a la creación.")
        if not isinstance(self.conversation_version, str) or not self.conversation_version.strip():
            raise ConversationSessionError("La versión de conversación es obligatoria.")
        if not isinstance(self.metadata, dict) and not isinstance(self.metadata, MappingProxyType):
            raise ConversationSessionError("Los metadatos de sesión deben ser un diccionario.")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class ConversationMessageDTO:
    message_id: str
    role: MessageRole
    content: str
    created_at_utc: datetime

    def __post_init__(self):
        if not isinstance(self.message_id, str) or not self.message_id.strip():
            raise ConversationSessionError("El identificador de mensaje es obligatorio.")
        if not isinstance(self.role, MessageRole):
            raise ConversationSessionError("El rol del mensaje no es válido.")
        if not isinstance(self.content, str):
            raise ConversationSessionError("El contenido del mensaje debe ser texto.")
        _validate_utc_timestamp(self.created_at_utc, "La creación del mensaje")


class ConversationSession:
    """Own mutable live-session state while exposing immutable DTO snapshots."""

    CONVERSATION_VERSION = "1.0"

    def __init__(self, session_id=None, metadata=None, conversation_version=CONVERSATION_VERSION):
        now = _utc_now()
        self._session_id = session_id or str(uuid4())
        self._created_at_utc = now
        self._last_activity_utc = now
        self._conversation_version = conversation_version
        self._metadata = _freeze_mapping(metadata or {})
        self._messages = []
        self._is_closed = False
        self._validate_state()

    @property
    def session_id(self):
        return self._session_id

    @property
    def is_closed(self):
        return self._is_closed

    def snapshot(self):
        """Return the immutable, auditable public state of this live session."""
        return ConversationSessionDTO(
            session_id=self._session_id,
            created_at_utc=self._created_at_utc,
            last_activity_utc=self._last_activity_utc,
            conversation_version=self._conversation_version,
            metadata=self._metadata,
        )

    def add_message(self, role, content):
        self._ensure_open()
        created_at_utc = self._touch()
        message = ConversationMessageDTO(
            message_id=str(uuid4()),
            role=role,
            content=content,
            created_at_utc=created_at_utc,
        )
        self._messages.append(message)
        return message

    def history(self):
        """Return messages in their append-only chronological order."""
        return tuple(self._messages)

    def get_history(self):
        """Compatibility-friendly explicit accessor for chronological history."""
        return self.history()

    def clear_history(self):
        self._ensure_open()
        self._messages.clear()
        self._touch()

    def message_count(self):
        return len(self._messages)

    def get_message_count(self):
        """Return the current number of messages without exposing mutable state."""
        return self.message_count()

    def update_last_activity(self):
        """Explicitly record activity while the live session remains open."""
        self._ensure_open()
        return self._touch()

    def close(self):
        if not self._is_closed:
            self._touch()
            self._is_closed = True

    def _touch(self):
        now = _utc_now()
        self._last_activity_utc = max(now, self._last_activity_utc)
        return self._last_activity_utc

    def _ensure_open(self):
        if self._is_closed:
            raise ConversationSessionError("La sesión de conversación está cerrada.")

    def _validate_state(self):
        ConversationSessionDTO(
            session_id=self._session_id,
            created_at_utc=self._created_at_utc,
            last_activity_utc=self._last_activity_utc,
            conversation_version=self._conversation_version,
            metadata=self._metadata,
        )


def _utc_now():
    return datetime.now(timezone.utc)


def _validate_utc_timestamp(value, label):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ConversationSessionError(f"{label} debe incluir zona horaria UTC.")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ConversationSessionError(f"{label} debe estar en UTC.")


def _freeze_mapping(value):
    return MappingProxyType({key: _freeze_value(item) for key, item in dict(value).items()})


def _freeze_value(value):
    if isinstance(value, dict) or isinstance(value, MappingProxyType):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    return value
