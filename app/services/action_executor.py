"""Side-effect-free execution foundation for confirmed action proposals."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from uuid import uuid4

from .action_pipeline import ActionProposalDTO


class ActionExecutionError(ValueError):
    """Raised when an execution request or result violates this foundation contract."""


@dataclass(frozen=True)
class ExecutionAuditEntryDTO:
    """Immutable record of one simulated execution or rollback attempt."""

    execution_id: str
    action_id: str
    operation: str
    outcome: str
    message: str
    recorded_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        for field_name in ("execution_id", "action_id", "message"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ActionExecutionError(f"{field_name} es obligatorio en la auditoria.")
        if self.operation not in {"execute", "rollback"}:
            raise ActionExecutionError("La operacion auditada debe ser execute o rollback.")
        if self.outcome not in {"success", "failure", "rejected"}:
            raise ActionExecutionError("El resultado auditado no es valido.")
        if not isinstance(self.recorded_at_utc, datetime) or self.recorded_at_utc.tzinfo is None:
            raise ActionExecutionError("El timestamp de auditoria debe incluir UTC.")
        if self.recorded_at_utc.utcoffset() != timezone.utc.utcoffset(self.recorded_at_utc):
            raise ActionExecutionError("El timestamp de auditoria debe estar en UTC.")
        if not isinstance(self.details, dict):
            raise ActionExecutionError("Los detalles de auditoria deben ser un diccionario.")
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


class ExecutionAuditLog:
    """Append-only in-memory audit log for the simulated execution boundary."""

    def __init__(self):
        self._entries = []

    @property
    def entries(self):
        return tuple(self._entries)

    def record(self, entry):
        if not isinstance(entry, ExecutionAuditEntryDTO):
            raise TypeError("ExecutionAuditLog.record requiere ExecutionAuditEntryDTO.")
        self._entries.append(entry)
        return entry


class IdempotencyRegistry:
    """In-memory registry which atomically consumes execution identifiers once."""

    def __init__(self):
        self._claimed_execution_ids = set()

    def claim(self, execution_id):
        if not isinstance(execution_id, str) or not execution_id.strip():
            raise ActionExecutionError("El identificador de ejecucion es obligatorio.")
        if execution_id in self._claimed_execution_ids:
            return False
        self._claimed_execution_ids.add(execution_id)
        return True

    def contains(self, execution_id):
        return execution_id in self._claimed_execution_ids


@dataclass(frozen=True)
class ExecutionRequestDTO:
    """Validated request to simulate one explicitly confirmed action proposal."""

    proposal: ActionProposalDTO
    confirmation_granted: bool
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    requested_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not isinstance(self.proposal, ActionProposalDTO):
            raise ActionExecutionError("La ejecucion requiere ActionProposalDTO.")
        if self.confirmation_granted is not True:
            raise ActionExecutionError("La ejecucion requiere confirmacion explicita.")
        if not isinstance(self.execution_id, str) or not self.execution_id.strip():
            raise ActionExecutionError("El identificador de ejecucion es obligatorio.")
        if not isinstance(self.requested_at_utc, datetime) or self.requested_at_utc.tzinfo is None:
            raise ActionExecutionError("El timestamp de ejecucion debe incluir UTC.")
        if self.requested_at_utc.utcoffset() != timezone.utc.utcoffset(self.requested_at_utc):
            raise ActionExecutionError("El timestamp de ejecucion debe estar en UTC.")


@dataclass(frozen=True)
class ExecutionResultDTO:
    """Typed result of a simulated execution; it cannot represent a real write."""

    execution_id: str
    action_id: str
    success: bool
    simulated: bool
    message: str
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        for field_name in ("execution_id", "action_id", "message"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ActionExecutionError(f"{field_name} es obligatorio.")
        if not isinstance(self.success, bool) or self.simulated is not True:
            raise ActionExecutionError("El resultado debe ser booleano y estrictamente simulado.")
        if not isinstance(self.details, dict):
            raise ActionExecutionError("details debe ser un diccionario.")
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


@dataclass(frozen=True)
class RollbackResultDTO:
    """Typed outcome of a simulated rollback; it cannot represent a real write."""

    execution_id: str
    action_id: str
    success: bool
    simulated: bool
    message: str
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        for field_name in ("execution_id", "action_id", "message"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ActionExecutionError(f"{field_name} es obligatorio.")
        if not isinstance(self.success, bool) or self.simulated is not True:
            raise ActionExecutionError("El rollback debe ser booleano y estrictamente simulado.")
        if not isinstance(self.details, dict):
            raise ActionExecutionError("details debe ser un diccionario.")
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


class ActionExecutor(ABC):
    """Future execution boundary; implementations receive proposals, not services."""

    @abstractmethod
    def execute(self, request):
        """Return one ExecutionResultDTO without exposing side-effectful collaborators."""

    @abstractmethod
    def rollback(self, request):
        """Return one RollbackResultDTO without applying a real rollback."""


class MockActionExecutor(ActionExecutor):
    """Deterministic in-memory executor used only to simulate outcomes in tests."""

    def __init__(self, outcomes=None, rollback_outcomes=None, audit_log=None, idempotency_registry=None):
        if outcomes is None:
            outcomes = {}
        if rollback_outcomes is None:
            rollback_outcomes = {}
        if not isinstance(outcomes, dict) or not all(
            isinstance(action_id, str) and action_id.strip() and isinstance(success, bool)
            for action_id, success in outcomes.items()
        ):
            raise ActionExecutionError("Los outcomes mock deben mapear action_id a booleanos.")
        if not isinstance(rollback_outcomes, dict) or not all(
            isinstance(action_id, str) and action_id.strip() and isinstance(success, bool)
            for action_id, success in rollback_outcomes.items()
        ):
            raise ActionExecutionError("Los outcomes de rollback deben mapear action_id a booleanos.")
        if audit_log is not None and not isinstance(audit_log, ExecutionAuditLog):
            raise TypeError("audit_log debe ser ExecutionAuditLog.")
        if idempotency_registry is not None and not isinstance(idempotency_registry, IdempotencyRegistry):
            raise TypeError("idempotency_registry debe ser IdempotencyRegistry.")
        self._outcomes = dict(outcomes)
        self._rollback_outcomes = dict(rollback_outcomes)
        self.audit_log = audit_log or ExecutionAuditLog()
        self.idempotency_registry = idempotency_registry or IdempotencyRegistry()
        self.requests = []

    def execute(self, request):
        if not isinstance(request, ExecutionRequestDTO):
            raise TypeError("MockActionExecutor.execute requiere ExecutionRequestDTO.")
        self.requests.append(request)
        if not self.idempotency_registry.claim(request.execution_id):
            result = ExecutionResultDTO(
                execution_id=request.execution_id,
                action_id=request.proposal.action_id,
                success=False,
                simulated=True,
                message="La execution_id ya fue procesada.",
                details={"action_type": request.proposal.action_type.value, "reason": "duplicate_execution_id"},
            )
            self._audit(request, "execute", "rejected", result.message, result.details)
            return result
        success = self._outcomes.get(request.proposal.action_id, True)
        message = "Accion simulada correctamente." if success else "La simulacion de accion fallo."
        result = ExecutionResultDTO(
            execution_id=request.execution_id,
            action_id=request.proposal.action_id,
            success=success,
            simulated=True,
            message=message,
            details={"action_type": request.proposal.action_type.value},
        )
        self._audit(request, "execute", "success" if success else "failure", result.message, result.details)
        return result

    def rollback(self, request):
        if not isinstance(request, ExecutionRequestDTO):
            raise TypeError("MockActionExecutor.rollback requiere ExecutionRequestDTO.")
        if not self.idempotency_registry.contains(request.execution_id):
            result = RollbackResultDTO(
                execution_id=request.execution_id,
                action_id=request.proposal.action_id,
                success=False,
                simulated=True,
                message="No existe una ejecucion simulada para revertir.",
                details={"reason": "execution_not_found"},
            )
            self._audit(request, "rollback", "rejected", result.message, result.details)
            return result
        success = self._rollback_outcomes.get(request.proposal.action_id, True)
        message = "Rollback simulado correctamente." if success else "La simulacion de rollback fallo."
        result = RollbackResultDTO(
            execution_id=request.execution_id,
            action_id=request.proposal.action_id,
            success=success,
            simulated=True,
            message=message,
            details={"action_type": request.proposal.action_type.value},
        )
        self._audit(request, "rollback", "success" if success else "failure", result.message, result.details)
        return result

    def _audit(self, request, operation, outcome, message, details):
        self.audit_log.record(
            ExecutionAuditEntryDTO(
                execution_id=request.execution_id,
                action_id=request.proposal.action_id,
                operation=operation,
                outcome=outcome,
                message=message,
                details=dict(details),
            )
        )
