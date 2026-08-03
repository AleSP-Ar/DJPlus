"""Confirmation-gated, fully simulated orchestration for action proposals."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from .action_executor import ActionExecutor, ExecutionRequestDTO, ExecutionResultDTO
from .action_pipeline import ActionPipeline, ActionValidationDTO
from .confirmation_manager import ConfirmationManager, ConfirmationRequestDTO, ConfirmationResultDTO


class ActionExecutionServiceError(ValueError):
    """Raised when an execution-service boundary contract is invalid."""


class ActionExecutionState(str, Enum):
    """Terminal states of the confirmation-gated simulated execution flow."""

    CONFIRMATION_REJECTED = "confirmation_rejected"
    AUTHORIZATION_REJECTED = "authorization_rejected"
    VALIDATION_REJECTED = "validation_rejected"
    EXECUTED = "executed"
    EXECUTION_FAILED = "execution_failed"


@dataclass(frozen=True)
class ActionExecutionAuthorizationDTO:
    """Explicit, action-scoped authorization supplied by the caller."""

    action_id: str
    authorized: bool
    authorized_by: str
    authorized_at_utc: datetime

    def __post_init__(self):
        if not isinstance(self.action_id, str) or not self.action_id.strip():
            raise ActionExecutionServiceError("El action_id de autorizacion es obligatorio.")
        if not isinstance(self.authorized, bool):
            raise ActionExecutionServiceError("La autorizacion debe ser booleana.")
        if not isinstance(self.authorized_by, str) or not self.authorized_by.strip():
            raise ActionExecutionServiceError("El autorizador es obligatorio.")
        _validate_utc_timestamp(self.authorized_at_utc)


@dataclass(frozen=True)
class ActionExecutionServiceResultDTO:
    """Typed terminal state of an attempt; no state represents a real write."""

    state: ActionExecutionState
    action_id: str
    message: str
    confirmation: ConfirmationResultDTO | None = None
    validation: ActionValidationDTO | None = None
    execution_result: ExecutionResultDTO | None = None

    def __post_init__(self):
        if not isinstance(self.state, ActionExecutionState):
            raise ActionExecutionServiceError("El estado final de ejecucion no es valido.")
        if not isinstance(self.action_id, str) or not self.action_id.strip():
            raise ActionExecutionServiceError("El action_id es obligatorio.")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ActionExecutionServiceError("El mensaje final es obligatorio.")
        if self.confirmation is not None and not isinstance(self.confirmation, ConfirmationResultDTO):
            raise ActionExecutionServiceError("confirmation debe ser ConfirmationResultDTO.")
        if self.validation is not None and not isinstance(self.validation, ActionValidationDTO):
            raise ActionExecutionServiceError("validation debe ser ActionValidationDTO.")
        if self.execution_result is not None and not isinstance(self.execution_result, ExecutionResultDTO):
            raise ActionExecutionServiceError("execution_result debe ser ExecutionResultDTO.")
        if self.state in {ActionExecutionState.EXECUTED, ActionExecutionState.EXECUTION_FAILED}:
            if self.execution_result is None:
                raise ActionExecutionServiceError("Los estados de ejecucion requieren resultado tipado.")
        elif self.execution_result is not None:
            raise ActionExecutionServiceError("Los rechazos no deben contener resultado de ejecucion.")


class ActionExecutionService:
    """Orchestrates confirmation, authorization, revalidation, and mock execution only."""

    def __init__(self, action_pipeline, confirmation_manager, action_executor):
        if not isinstance(action_pipeline, ActionPipeline):
            raise TypeError("ActionExecutionService requiere ActionPipeline.")
        if not isinstance(confirmation_manager, ConfirmationManager):
            raise TypeError("ActionExecutionService requiere ConfirmationManager.")
        if not isinstance(action_executor, ActionExecutor):
            raise TypeError("ActionExecutionService requiere ActionExecutor.")
        self._action_pipeline = action_pipeline
        self._confirmation_manager = confirmation_manager
        self._action_executor = action_executor

    def execute(self, confirmation_request, authorization, execution_id=None):
        if not isinstance(confirmation_request, ConfirmationRequestDTO):
            raise TypeError("execute requiere ConfirmationRequestDTO.")
        if not isinstance(authorization, ActionExecutionAuthorizationDTO):
            raise TypeError("execute requiere ActionExecutionAuthorizationDTO.")
        if execution_id is not None and (not isinstance(execution_id, str) or not execution_id.strip()):
            raise ActionExecutionServiceError("execution_id debe ser texto no vacio.")

        confirmation = self._confirmation_manager.request_confirmation(confirmation_request)
        action_id = confirmation_request.action_id
        if not confirmation.confirmed or not confirmation.allowed:
            return ActionExecutionServiceResultDTO(
                ActionExecutionState.CONFIRMATION_REJECTED, action_id, confirmation.reason, confirmation=confirmation
            )
        if authorization.action_id != action_id or authorization.authorized is not True:
            return ActionExecutionServiceResultDTO(
                ActionExecutionState.AUTHORIZATION_REJECTED,
                action_id,
                "La autorizacion explicita no permite esta propuesta.",
                confirmation=confirmation,
            )

        proposal = self._action_pipeline.get_proposal(action_id)
        validation = self._action_pipeline.revalidate_registered_proposal(proposal)
        if not validation.valid:
            return ActionExecutionServiceResultDTO(
                ActionExecutionState.VALIDATION_REJECTED,
                action_id,
                "La propuesta no supero la revalidacion previa a la ejecucion.",
                confirmation=confirmation,
                validation=validation,
            )

        request = ExecutionRequestDTO(
            proposal=proposal,
            confirmation_granted=True,
            execution_id=execution_id or str(uuid4()),
        )
        execution_result = self._action_executor.execute(request)
        state = ActionExecutionState.EXECUTED if execution_result.success else ActionExecutionState.EXECUTION_FAILED
        return ActionExecutionServiceResultDTO(
            state,
            action_id,
            execution_result.message,
            confirmation=confirmation,
            validation=validation,
            execution_result=execution_result,
        )


def _validate_utc_timestamp(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ActionExecutionServiceError("El timestamp de autorizacion debe incluir UTC.")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ActionExecutionServiceError("El timestamp de autorizacion debe estar en UTC.")
