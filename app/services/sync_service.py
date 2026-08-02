"""Safe, provider-neutral READ → PLAN → PREVIEW → APPLY sync foundation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class SyncError(ValueError):
    """Base error for controlled synchronization requests."""


class SyncConfirmationRequiredError(SyncError):
    """Raised when apply is attempted without an explicit preview confirmation."""


class SyncConflictError(SyncError):
    """Raised when a plan with unresolved conflicts is applied."""


class SyncAction(str, Enum):
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"


@dataclass(frozen=True)
class SyncChangeDTO:
    action: SyncAction
    external_id: str
    value: object | None


@dataclass(frozen=True)
class SyncConflictDTO:
    external_id: str
    local_value: object
    external_value: object
    reason: str


@dataclass(frozen=True)
class SyncPlanDTO:
    changes: tuple[SyncChangeDTO, ...]
    conflicts: tuple[SyncConflictDTO, ...]
    warnings: tuple[str, ...]
    affected_items: tuple[str, ...]


@dataclass(frozen=True)
class SyncPreviewDTO:
    additions: tuple[SyncChangeDTO, ...]
    updates: tuple[SyncChangeDTO, ...]
    deletions: tuple[SyncChangeDTO, ...]
    conflicts: tuple[SyncConflictDTO, ...]
    warnings: tuple[str, ...]


class SyncAdapter(ABC):
    """External-platform boundary; adapters never receive DJPlus persistence objects."""

    @abstractmethod
    def read_external_state(self):
        """Return a normalized external-state DTO or mapping."""

    @abstractmethod
    def plan_changes(self, local_state, external_state):
        """Return a deterministic SyncPlanDTO without applying it."""

    @abstractmethod
    def preview_changes(self, plan):
        """Return a user-visible SyncPreviewDTO for a plan."""

    @abstractmethod
    def apply_changes(self, plan):
        """Apply only the already-approved changes in ``plan``."""


class MockSyncAdapter(SyncAdapter):
    """In-memory adapter for sync contracts; it performs no platform I/O."""

    def __init__(self, external_state=None):
        self.external_state = dict(external_state or {})
        self.applied_plans = []

    def read_external_state(self):
        return dict(self.external_state)

    def plan_changes(self, local_state, external_state):
        local = dict(local_state or {})
        external = dict(external_state or {})
        changes = []
        conflicts = []
        for external_id in sorted(set(local) | set(external)):
            in_local, in_external = external_id in local, external_id in external
            if in_local and not in_external:
                changes.append(SyncChangeDTO(SyncAction.ADD, external_id, local[external_id]))
                continue
            if in_external and not in_local:
                changes.append(SyncChangeDTO(SyncAction.DELETE, external_id, None))
                continue
            external_value, locked = self._external_value(external[external_id])
            if local[external_id] == external_value:
                continue
            if locked:
                conflicts.append(
                    SyncConflictDTO(external_id, local[external_id], external_value, "Cambio externo bloqueado")
                )
            else:
                changes.append(SyncChangeDTO(SyncAction.UPDATE, external_id, local[external_id]))
        warnings = ("La aplicación requiere confirmación explícita.",)
        if conflicts:
            warnings += ("Existen conflictos que deben resolverse antes de aplicar.",)
        affected = tuple(sorted({change.external_id for change in changes} | {conflict.external_id for conflict in conflicts}))
        return SyncPlanDTO(tuple(changes), tuple(conflicts), warnings, affected)

    def preview_changes(self, plan):
        return SyncPreviewDTO(
            additions=tuple(change for change in plan.changes if change.action == SyncAction.ADD),
            updates=tuple(change for change in plan.changes if change.action == SyncAction.UPDATE),
            deletions=tuple(change for change in plan.changes if change.action == SyncAction.DELETE),
            conflicts=plan.conflicts,
            warnings=plan.warnings,
        )

    def apply_changes(self, plan):
        for change in plan.changes:
            if change.action == SyncAction.DELETE:
                self.external_state.pop(change.external_id, None)
            else:
                self.external_state[change.external_id] = change.value
        self.applied_plans.append(plan)
        return tuple(change.external_id for change in plan.changes)

    def _external_value(self, value):
        if isinstance(value, Mapping) and "value" in value:
            return value["value"], bool(value.get("conflict"))
        return value, False


class SyncService:
    """Coordinate explicit sync stages and reject automatic or conflicting apply."""

    def __init__(self, adapter):
        if not isinstance(adapter, SyncAdapter):
            raise TypeError("SyncService requiere un SyncAdapter.")
        self.adapter = adapter
        self._previewed_plan_ids = set()

    def read(self):
        return self.adapter.read_external_state()

    def plan(self, local_state):
        plan = self.adapter.plan_changes(local_state, self.read())
        if not isinstance(plan, SyncPlanDTO):
            raise SyncError("El adaptador debe devolver SyncPlanDTO.")
        return plan

    def preview(self, plan):
        if not isinstance(plan, SyncPlanDTO):
            raise SyncError("La vista previa requiere SyncPlanDTO.")
        preview = self.adapter.preview_changes(plan)
        if not isinstance(preview, SyncPreviewDTO):
            raise SyncError("El adaptador debe devolver SyncPreviewDTO.")
        self._previewed_plan_ids.add(id(plan))
        return preview

    def apply(self, plan, confirmed=False):
        if not confirmed or id(plan) not in self._previewed_plan_ids:
            raise SyncConfirmationRequiredError("Debe previsualizar y confirmar el plan antes de aplicarlo.")
        if plan.conflicts:
            raise SyncConflictError("No se puede aplicar un plan con conflictos sin resolver.")
        applied = self.adapter.apply_changes(plan)
        self._previewed_plan_ids.discard(id(plan))
        return applied
