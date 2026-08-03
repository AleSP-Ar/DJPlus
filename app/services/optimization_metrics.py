"""Small immutable internal profiling DTOs with no infrastructure dependency."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StageTimingDTO:
    stage: str
    duration_ms: float

    def __post_init__(self):
        if not isinstance(self.stage, str) or not self.stage.strip():
            raise ValueError("La etapa de profiling es obligatoria.")
        if not isinstance(self.duration_ms, (int, float)) or self.duration_ms < 0:
            raise ValueError("La duracion de profiling debe ser no negativa.")


@dataclass(frozen=True)
class OperationMetricsDTO:
    operation: str
    stages: tuple[StageTimingDTO, ...]

    def __post_init__(self):
        if not isinstance(self.operation, str) or not self.operation.strip():
            raise ValueError("La operacion de profiling es obligatoria.")
        if not isinstance(self.stages, tuple) or not all(isinstance(stage, StageTimingDTO) for stage in self.stages):
            raise ValueError("Las metricas deben contener etapas tipadas.")

    @property
    def total_ms(self):
        """Return the explicit total when present, otherwise sum all stages."""
        for stage in self.stages:
            if stage.stage == "total":
                return round(stage.duration_ms, 3)
        return round(sum(stage.duration_ms for stage in self.stages), 3)
