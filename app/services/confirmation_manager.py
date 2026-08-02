"""Policy-based, non-executing confirmation boundary for action proposals."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from .action_pipeline import ActionPipeline, ActionProposalDTO


class ConfirmationError(ValueError):
    """Raised when a confirmation request or policy contract is invalid."""


@dataclass(frozen=True)
class ConfirmationRequestDTO:
    action_id: str
    requested_at_utc: datetime

    def __post_init__(self):
        if not isinstance(self.action_id, str) or not self.action_id.strip():
            raise ConfirmationError("El identificador de acción es obligatorio.")
        _validate_utc_timestamp(self.requested_at_utc, "El timestamp de solicitud")


@dataclass(frozen=True)
class ConfirmationResultDTO:
    confirmed: bool
    allowed: bool
    reason: str
    checked_at_utc: datetime

    def __post_init__(self):
        if not isinstance(self.confirmed, bool) or not isinstance(self.allowed, bool):
            raise ConfirmationError("El resultado de confirmación debe ser booleano.")
        if self.confirmed and not self.allowed:
            raise ConfirmationError("Una confirmación no puede estar desautorizada.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ConfirmationError("El motivo de confirmación es obligatorio.")
        _validate_utc_timestamp(self.checked_at_utc, "El timestamp de validación")


class ConfirmationPolicy(ABC):
    """Pure policy contract for assessing one confirmation request."""

    @abstractmethod
    def validate(self, proposal, request, was_discarded, was_confirmed):
        """Return a typed confirmation decision without causing side effects."""


class AlwaysRequireConfirmationPolicy(ConfirmationPolicy):
    """Allow each existing explicit-confirmation proposal once."""

    def validate(self, proposal, request, was_discarded, was_confirmed):
        checked_at_utc = datetime.now(timezone.utc)
        if was_discarded:
            return ConfirmationResultDTO(False, False, "La propuesta fue descartada.", checked_at_utc)
        if proposal is None:
            return ConfirmationResultDTO(False, False, "La propuesta no existe.", checked_at_utc)
        if was_confirmed:
            return ConfirmationResultDTO(False, False, "La propuesta ya fue confirmada.", checked_at_utc)
        if proposal.requires_confirmation is not True:
            return ConfirmationResultDTO(False, False, "La propuesta no exige confirmación válida.", checked_at_utc)
        return ConfirmationResultDTO(True, True, "La propuesta puede confirmarse.", checked_at_utc)


class ConfirmationManager:
    """Evaluate proposal confirmation once through a composed policy; never execute it."""

    def __init__(self, action_pipeline, policy=None):
        if not isinstance(action_pipeline, ActionPipeline):
            raise TypeError("ConfirmationManager requiere ActionPipeline.")
        self._action_pipeline = action_pipeline
        self._policy = policy or AlwaysRequireConfirmationPolicy()
        if not isinstance(self._policy, ConfirmationPolicy):
            raise TypeError("ConfirmationManager requiere ConfirmationPolicy.")
        self._confirmed_action_ids = set()

    def request_confirmation(self, request):
        if not isinstance(request, ConfirmationRequestDTO):
            raise TypeError("ConfirmationManager requiere ConfirmationRequestDTO.")
        proposal = self._action_pipeline.get_proposal(request.action_id)
        result = self._policy.validate(
            proposal=proposal,
            request=request,
            was_discarded=self._action_pipeline.was_discarded(request.action_id),
            was_confirmed=request.action_id in self._confirmed_action_ids,
        )
        if not isinstance(result, ConfirmationResultDTO):
            raise ConfirmationError("La política debe devolver ConfirmationResultDTO.")
        if result.confirmed:
            self._confirmed_action_ids.add(request.action_id)
        return result


def _validate_utc_timestamp(value, label):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ConfirmationError(f"{label} debe incluir zona horaria UTC.")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ConfirmationError(f"{label} debe estar en UTC.")
