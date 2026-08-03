"""Local credential references and redaction utilities for assistant providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import re


class CredentialNotFoundError(ValueError):
    """Raised when a credential reference cannot be resolved locally."""


@dataclass(frozen=True)
class ProviderCredentialRefDTO:
    """Public identifier for a credential; it never contains its secret value."""

    provider_name: str
    credential_id: str

    def __post_init__(self):
        for field_name in ("provider_name", "credential_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} es obligatorio.")


class CredentialProvider(ABC):
    """Boundary that resolves a secret only inside a concrete provider adapter."""

    @abstractmethod
    def resolve(self, credential_ref):
        """Return the secret for a ProviderCredentialRefDTO without logging it."""


class InMemoryCredentialProvider(CredentialProvider):
    """Test-only volatile credential store with no environment or disk access."""

    def __init__(self, credentials=None):
        self._credentials = {}
        for credential_ref, secret in (credentials or {}).items():
            self.set(credential_ref, secret)

    def set(self, credential_ref, secret):
        if not isinstance(credential_ref, ProviderCredentialRefDTO):
            raise TypeError("InMemoryCredentialProvider requiere ProviderCredentialRefDTO.")
        if not isinstance(secret, str) or not secret:
            raise ValueError("La credencial in-memory debe ser texto no vacio.")
        self._credentials[credential_ref] = secret

    def resolve(self, credential_ref):
        if not isinstance(credential_ref, ProviderCredentialRefDTO):
            raise TypeError("CredentialProvider.resolve requiere ProviderCredentialRefDTO.")
        try:
            return self._credentials[credential_ref]
        except KeyError as error:
            raise CredentialNotFoundError(
                f"No existe una credencial para {credential_ref.provider_name}/{credential_ref.credential_id}."
            ) from error


class SecretRedactor:
    """Redact common secret assignments and configured values from public data."""

    REDACTED = "[REDACTED]"
    _ASSIGNMENT = re.compile(r"(?i)\b(api[_-]?key|token|secret|password|credential)\s*([:=])\s*[^\s,;]+")

    def __init__(self, secrets=()):
        if not all(isinstance(secret, str) and secret for secret in secrets):
            raise ValueError("Los secretos a redactar deben ser textos no vacios.")
        self._secrets = tuple(secrets)

    def redact(self, value):
        if isinstance(value, str):
            redacted = value
            for secret in self._secrets:
                redacted = redacted.replace(secret, self.REDACTED)
            return self._ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}{self.REDACTED}", redacted)
        if isinstance(value, dict):
            return {
                key: self.REDACTED if self._is_sensitive_key(key) else self.redact(item)
                for key, item in value.items()
            }
        if isinstance(value, tuple):
            return tuple(self.redact(item) for item in value)
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        return value

    def _is_sensitive_key(self, key):
        return isinstance(key, str) and any(name in key.casefold() for name in (
            "api_key", "apikey", "authorization", "token", "secret", "password", "credential",
        ))
