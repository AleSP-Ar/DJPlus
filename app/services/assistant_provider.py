"""Provider contracts for future assistant model integrations.

This module is intentionally transport-free.  Providers receive only a
provider-neutral prompt DTO and return data; they never receive runtime,
persistence, filesystem, or UI objects.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .prompt_builder import PromptDTO
from .provider_credentials import (
    CredentialNotFoundError,
    CredentialProvider,
    ProviderCredentialRefDTO,
    SecretRedactor,
)
from .tool_dispatcher import ToolCallDTO


class AssistantProviderError(ValueError):
    """Raised when a provider request or response violates this contract."""


class ProviderExecutionError(AssistantProviderError):
    """Base error for controlled local provider execution failures."""

    code = "provider_error"
    retryable = False

    def __init__(self, message, duration_ms=0):
        super().__init__(message)
        if not isinstance(duration_ms, int) or duration_ms < 0:
            raise AssistantProviderError("La duracion del error debe ser un entero no negativo.")
        self.duration_ms = duration_ms


class ProviderTimeoutError(ProviderExecutionError):
    code = "timeout"
    retryable = True


class ProviderRateLimitError(ProviderExecutionError):
    code = "rate_limit"
    retryable = True


class ProviderUnavailableError(ProviderExecutionError):
    code = "unavailable"
    retryable = True


class ProviderInvalidResponseError(ProviderExecutionError):
    code = "invalid_response"


class ProviderCancelledError(ProviderExecutionError):
    code = "cancelled"


@dataclass(frozen=True)
class ProviderCapabilitiesDTO:
    """Immutable declaration of a provider's supported, local contract."""

    provider_name: str
    provider_version: str
    supports_tool_calls: bool = False
    supports_streaming: bool = False
    max_context_tokens: int | None = None

    def __post_init__(self):
        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise AssistantProviderError("El nombre del proveedor es obligatorio.")
        if not isinstance(self.provider_version, str) or not self.provider_version.strip():
            raise AssistantProviderError("La version del proveedor es obligatoria.")
        if not isinstance(self.supports_tool_calls, bool) or not isinstance(self.supports_streaming, bool):
            raise AssistantProviderError("Las capacidades booleanas del proveedor no son validas.")
        if self.max_context_tokens is not None and (
            not isinstance(self.max_context_tokens, int) or self.max_context_tokens < 1
        ):
            raise AssistantProviderError("El limite de contexto debe ser un entero positivo o nulo.")


@dataclass(frozen=True)
class RetryPolicyDTO:
    """Bounded retry configuration with deterministic virtual delay."""

    max_retries: int = 0
    retry_delay_ms: int = 0

    def __post_init__(self):
        if not isinstance(self.max_retries, int) or not 0 <= self.max_retries <= 5:
            raise AssistantProviderError("El maximo de reintentos debe estar entre 0 y 5.")
        if not isinstance(self.retry_delay_ms, int) or self.retry_delay_ms < 0:
            raise AssistantProviderError("La espera entre reintentos debe ser un entero no negativo.")


@dataclass(frozen=True)
class ProviderConfigDTO:
    """Validated model settings passed unchanged to one provider request."""

    model: str = "mock-model"
    temperature: float = 0.0
    max_tokens: int = 256
    timeout_ms: int = 1000
    retry_policy: RetryPolicyDTO = field(default_factory=RetryPolicyDTO)

    def __post_init__(self):
        if not isinstance(self.model, str) or not self.model.strip():
            raise AssistantProviderError("El modelo es obligatorio.")
        if isinstance(self.temperature, bool) or not isinstance(self.temperature, (int, float)) or not 0 <= self.temperature <= 2:
            raise AssistantProviderError("La temperatura debe estar entre 0 y 2.")
        if not isinstance(self.max_tokens, int) or self.max_tokens < 1:
            raise AssistantProviderError("max_tokens debe ser un entero positivo.")
        if not isinstance(self.timeout_ms, int) or self.timeout_ms < 1:
            raise AssistantProviderError("El timeout debe ser un entero positivo en milisegundos.")
        if not isinstance(self.retry_policy, RetryPolicyDTO):
            raise AssistantProviderError("La configuracion requiere RetryPolicyDTO.")


@dataclass(frozen=True)
class ProviderRequestDTO:
    """Immutable, provider-neutral input for one completion request."""

    request_id: str
    prompt: PromptDTO
    config: ProviderConfigDTO = field(default_factory=ProviderConfigDTO)
    credential_ref: ProviderCredentialRefDTO | None = None

    def __post_init__(self):
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise AssistantProviderError("El identificador de request es obligatorio.")
        if not isinstance(self.prompt, PromptDTO):
            raise AssistantProviderError("El proveedor requiere un PromptDTO provider-neutral.")
        if not isinstance(self.config, ProviderConfigDTO):
            raise AssistantProviderError("El proveedor requiere ProviderConfigDTO.")
        if self.credential_ref is not None and not isinstance(self.credential_ref, ProviderCredentialRefDTO):
            raise AssistantProviderError("credential_ref debe ser ProviderCredentialRefDTO o nula.")


@dataclass(frozen=True)
class ProviderResponseDTO:
    """Immutable provider output, including only planned tool calls."""

    request_id: str
    content: str
    provider_name: str
    provider_version: str
    tool_calls: tuple[ToolCallDTO, ...] = ()
    duration_ms: int = 0

    def __post_init__(self):
        for field_name in ("request_id", "content", "provider_name", "provider_version"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise AssistantProviderError(f"{field_name} es obligatorio.")
        if not isinstance(self.tool_calls, tuple) or not all(
            isinstance(call, ToolCallDTO) for call in self.tool_calls
        ):
            raise AssistantProviderError("Las llamadas de herramientas deben ser ToolCallDTO inmutables.")
        if not isinstance(self.duration_ms, int) or self.duration_ms < 0:
            raise AssistantProviderError("La duracion debe ser un entero no negativo en milisegundos.")


@dataclass(frozen=True)
class ProviderUsageDTO:
    """Deterministic local token estimates for one provider execution."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def __post_init__(self):
        if not all(isinstance(value, int) and value >= 0 for value in (
            self.prompt_tokens, self.completion_tokens, self.total_tokens,
        )):
            raise AssistantProviderError("Las metricas de uso deben ser enteros no negativos.")
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise AssistantProviderError("El total de tokens no coincide con sus componentes.")


@dataclass(frozen=True)
class ProviderErrorDTO:
    """Typed, serializable execution failure without provider internals."""

    code: str
    message: str
    retryable: bool

    def __post_init__(self):
        redactor = SecretRedactor()
        object.__setattr__(self, "message", redactor.redact(self.message))
        if not isinstance(self.code, str) or not self.code.strip():
            raise AssistantProviderError("El codigo de error es obligatorio.")
        if not isinstance(self.message, str) or not self.message.strip():
            raise AssistantProviderError("El mensaje de error es obligatorio.")
        if not isinstance(self.retryable, bool):
            raise AssistantProviderError("retryable debe ser booleano.")


@dataclass(frozen=True)
class ProviderExecutionResultDTO:
    """Complete deterministic outcome of a policy-controlled execution."""

    response: ProviderResponseDTO | None
    usage: ProviderUsageDTO
    error: ProviderErrorDTO | None
    attempts: int
    duration_ms: int

    def __post_init__(self):
        if (self.response is None) == (self.error is None):
            raise AssistantProviderError("El resultado requiere exactamente una respuesta o un error.")
        if not isinstance(self.usage, ProviderUsageDTO):
            raise AssistantProviderError("El resultado requiere ProviderUsageDTO.")
        if self.error is not None and not isinstance(self.error, ProviderErrorDTO):
            raise AssistantProviderError("El error debe ser ProviderErrorDTO o nulo.")
        if not isinstance(self.attempts, int) or self.attempts < 0:
            raise AssistantProviderError("Los intentos deben ser un entero no negativo.")
        if not isinstance(self.duration_ms, int) or self.duration_ms < 0:
            raise AssistantProviderError("La duracion debe ser un entero no negativo.")


class AssistantProvider(ABC):
    """Replaceable model boundary with no transport or infrastructure policy."""

    @abstractmethod
    def capabilities(self):
        """Return the immutable capabilities declared by this provider."""

    @abstractmethod
    def complete(self, request):
        """Return a ProviderResponseDTO for one ProviderRequestDTO."""


class ProviderCancellationToken:
    """Cooperative cancellation state checked before each local attempt."""

    def __init__(self):
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def is_cancelled(self):
        return self._cancelled


class ProviderPolicy:
    """Apply bounded retries, cooperative cancellation, and typed outcomes."""

    def execute(self, provider, request, cancellation_token=None):
        if not isinstance(provider, AssistantProvider):
            raise TypeError("ProviderPolicy requiere AssistantProvider.")
        if not isinstance(request, ProviderRequestDTO):
            raise TypeError("ProviderPolicy.execute requiere ProviderRequestDTO.")
        if cancellation_token is not None and not isinstance(cancellation_token, ProviderCancellationToken):
            raise TypeError("ProviderPolicy requiere ProviderCancellationToken.")

        attempts = 0
        duration_ms = 0
        retry_policy = request.config.retry_policy
        while True:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                return self._failure("cancelled", "La ejecucion fue cancelada.", False, attempts, duration_ms)
            attempts += 1
            try:
                response = provider.complete(request)
                if not isinstance(response, ProviderResponseDTO):
                    raise ProviderInvalidResponseError("El proveedor devolvio una respuesta invalida.")
                if response.duration_ms > request.config.timeout_ms:
                    raise ProviderTimeoutError("El proveedor supero el timeout configurado.", response.duration_ms)
                duration_ms += response.duration_ms
                return ProviderExecutionResultDTO(
                    response=response,
                    usage=self._usage(request, response),
                    error=None,
                    attempts=attempts,
                    duration_ms=duration_ms,
                )
            except ProviderExecutionError as error:
                duration_ms += error.duration_ms
                if error.retryable and attempts <= retry_policy.max_retries:
                    duration_ms += retry_policy.retry_delay_ms
                    continue
                return self._failure(error.code, str(error), error.retryable, attempts, duration_ms)
            except Exception as error:
                return self._failure("provider_error", "El proveedor produjo un error no controlado.", False, attempts, duration_ms)

    def _failure(self, code, message, retryable, attempts, duration_ms):
        return ProviderExecutionResultDTO(
            response=None,
            usage=ProviderUsageDTO(0, 0, 0),
            error=ProviderErrorDTO(code, message, retryable),
            attempts=attempts,
            duration_ms=duration_ms,
        )

    def _usage(self, request, response):
        prompt_tokens = self._token_count(request.prompt.system_prompt) + self._token_count(request.prompt.user_prompt)
        completion_tokens = self._token_count(response.content)
        return ProviderUsageDTO(prompt_tokens, completion_tokens, prompt_tokens + completion_tokens)

    def _token_count(self, text):
        return len(text.split())


class MockAssistantProvider(AssistantProvider):
    """Deterministic in-memory provider for tests and local development."""

    provider_name = "mock"
    provider_version = "1.0"

    def __init__(
        self,
        responses=None,
        default_response="Mock assistant response.",
        scenario="success",
        response_duration_ms=0,
        credential_provider=None,
    ):
        if responses is None:
            responses = {}
        if not isinstance(responses, dict) or not all(
            isinstance(query, str) and query.strip() and isinstance(response, str) and response.strip()
            for query, response in responses.items()
        ):
            raise AssistantProviderError("Las respuestas mock deben ser un diccionario de textos no vacios.")
        if not isinstance(default_response, str) or not default_response.strip():
            raise AssistantProviderError("La respuesta mock por defecto es obligatoria.")
        scenario_outcomes = {
            "success": ("success",),
            "timeout": ("timeout",),
            "rate_limit": ("rate_limit",),
            "unavailable": ("unavailable",),
            "invalid_response": ("invalid_response",),
            "retry_success": ("rate_limit", "success"),
        }
        if scenario not in scenario_outcomes:
            raise AssistantProviderError("El escenario mock no es valido.")
        if not isinstance(response_duration_ms, int) or response_duration_ms < 0:
            raise AssistantProviderError("La duracion mock debe ser un entero no negativo.")
        if credential_provider is not None and not isinstance(credential_provider, CredentialProvider):
            raise TypeError("MockAssistantProvider requiere CredentialProvider.")
        self._responses = dict(responses)
        self._default_response = default_response
        self._outcomes = list(scenario_outcomes[scenario])
        self._response_duration_ms = response_duration_ms
        self._credential_provider = credential_provider
        self.credential_resolution_count = 0
        self.calls = []
        self._capabilities = ProviderCapabilitiesDTO(
            provider_name=self.provider_name,
            provider_version=self.provider_version,
        )

    def capabilities(self):
        return self._capabilities

    def complete(self, request):
        if not isinstance(request, ProviderRequestDTO):
            raise TypeError("MockAssistantProvider.complete requiere ProviderRequestDTO.")
        self.calls.append(request)
        self._resolve_credential_reference(request)
        outcome = self._outcomes.pop(0) if self._outcomes else "success"
        if outcome == "timeout":
            raise ProviderTimeoutError("Timeout simulado por MockAssistantProvider.", request.config.timeout_ms)
        if outcome == "rate_limit":
            raise ProviderRateLimitError("Rate limit simulado por MockAssistantProvider.")
        if outcome == "unavailable":
            raise ProviderUnavailableError("Proveedor no disponible en MockAssistantProvider.")
        if outcome == "invalid_response":
            return object()
        return ProviderResponseDTO(
            request_id=request.request_id,
            content=self._responses.get(request.prompt.user_prompt, self._default_response),
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            duration_ms=self._response_duration_ms,
        )

    def _resolve_credential_reference(self, request):
        if request.credential_ref is None:
            return
        if self._credential_provider is None:
            raise ProviderUnavailableError("No hay proveedor local para la referencia de credencial.")
        try:
            self._credential_provider.resolve(request.credential_ref)
        except CredentialNotFoundError:
            raise ProviderUnavailableError("La referencia de credencial no esta disponible.")
        self.credential_resolution_count += 1
