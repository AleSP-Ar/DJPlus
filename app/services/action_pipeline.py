"""In-memory validation and audit boundary for proposed assistant actions."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from uuid import uuid4


class ActionPipelineError(ValueError):
    """Raised when an action proposal violates the safe pipeline contract."""


class ActionType(str, Enum):
    CREATE_PLAYLIST = "create_playlist"
    CREATE_COLLECTION = "create_collection"
    SYNC_LIBRARY = "sync_library"
    EXPORT_LIBRARY = "export_library"
    IMPORT_LIBRARY = "import_library"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ActionProposalDTO:
    action_id: str
    action_type: ActionType
    title: str
    description: str
    payload: dict
    requires_confirmation: bool
    created_at_utc: datetime

    def __post_init__(self):
        if not isinstance(self.action_id, str) or not self.action_id.strip():
            raise ActionPipelineError("El identificador de acción es obligatorio.")
        if not isinstance(self.action_type, ActionType):
            raise ActionPipelineError("El tipo de acción no es válido.")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ActionPipelineError("El título de la acción es obligatorio.")
        if not isinstance(self.description, str):
            raise ActionPipelineError("La descripción de la acción debe ser texto.")
        if not isinstance(self.payload, dict):
            raise ActionPipelineError("El payload de la acción debe ser un diccionario.")
        if self.requires_confirmation is not True:
            raise ActionPipelineError("Toda acción propuesta requiere confirmación explícita.")
        _validate_utc_timestamp(self.created_at_utc)
        object.__setattr__(self, "payload", _freeze_payload(self.payload))


@dataclass(frozen=True)
class ActionValidationDTO:
    valid: bool
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.valid, bool):
            raise ActionPipelineError("El estado de validación debe ser booleano.")
        if not isinstance(self.warnings, tuple) or not all(isinstance(item, str) for item in self.warnings):
            raise ActionPipelineError("Las advertencias deben ser una tupla de texto.")
        if not isinstance(self.errors, tuple) or not all(isinstance(item, str) for item in self.errors):
            raise ActionPipelineError("Los errores deben ser una tupla de texto.")
        if self.valid != (not self.errors):
            raise ActionPipelineError("El estado de validación no coincide con los errores.")


class ActionPipeline:
    """Store only explicit, validated proposals; never confirm or execute them."""

    def __init__(self):
        self._proposals = {}
        self._discarded_action_ids = set()

    def create_proposal(self, action_type, title, description, payload):
        proposal = ActionProposalDTO(
            action_id=str(uuid4()),
            action_type=action_type,
            title=title,
            description=description,
            payload=payload,
            requires_confirmation=True,
            created_at_utc=datetime.now(timezone.utc),
        )
        self.register_proposal(proposal)
        return proposal

    def validate_proposal(self, proposal):
        if not isinstance(proposal, ActionProposalDTO):
            return ActionValidationDTO(False, errors=("La propuesta debe ser ActionProposalDTO.",))
        if proposal.action_id in self._proposals:
            return ActionValidationDTO(False, errors=("El identificador de acción ya existe.",))
        return ActionValidationDTO(True)

    def revalidate_registered_proposal(self, proposal):
        """Validate that a proposal is still the active immutable proposal before execution."""
        if not isinstance(proposal, ActionProposalDTO):
            return ActionValidationDTO(False, errors=("La propuesta debe ser ActionProposalDTO.",))
        registered = self._proposals.get(proposal.action_id)
        if registered is None:
            return ActionValidationDTO(False, errors=("La propuesta ya no esta registrada.",))
        if registered != proposal:
            return ActionValidationDTO(False, errors=("La propuesta no coincide con el registro activo.",))
        if self.was_discarded(proposal.action_id):
            return ActionValidationDTO(False, errors=("La propuesta fue descartada.",))
        return ActionValidationDTO(True)

    def register_proposal(self, proposal):
        validation = self.validate_proposal(proposal)
        if not validation.valid:
            raise ActionPipelineError(" ".join(validation.errors))
        self._proposals[proposal.action_id] = proposal

    def list_proposals(self):
        return tuple(self._proposals.values())

    def get_proposal(self, action_id):
        return self._proposals.get(action_id)

    def discard_proposal(self, action_id):
        proposal = self._proposals.pop(action_id, None)
        if proposal is not None:
            self._discarded_action_ids.add(action_id)
        return proposal

    def clear(self):
        self._discarded_action_ids.update(self._proposals)
        self._proposals.clear()

    def was_discarded(self, action_id):
        return action_id in self._discarded_action_ids


def _validate_utc_timestamp(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ActionPipelineError("El timestamp de acción debe incluir zona horaria UTC.")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ActionPipelineError("El timestamp de acción debe estar en UTC.")


def _freeze_payload(payload):
    frozen_payload = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            raise ActionPipelineError("Las claves del payload deben ser texto.")
        frozen_payload[key] = _freeze_value(value)
    return MappingProxyType(frozen_payload)


def _freeze_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return _freeze_payload(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    raise ActionPipelineError("El payload solo admite tipos básicos serializables.")
