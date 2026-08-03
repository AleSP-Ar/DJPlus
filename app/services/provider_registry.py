"""Local registration and deterministic selection of assistant providers."""

from dataclasses import dataclass

from .assistant_provider import AssistantProvider, AssistantProviderError, ProviderCapabilitiesDTO


class ProviderNotFoundError(AssistantProviderError):
    """Raised when a requested or default provider is not registered."""


@dataclass(frozen=True)
class ProviderSelectionDTO:
    """Immutable public description of a registered provider selection."""

    provider_name: str
    capabilities: ProviderCapabilitiesDTO
    is_default: bool = False

    def __post_init__(self):
        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise AssistantProviderError("El nombre del proveedor seleccionado es obligatorio.")
        if not isinstance(self.capabilities, ProviderCapabilitiesDTO):
            raise AssistantProviderError("La seleccion requiere ProviderCapabilitiesDTO.")
        if self.provider_name.casefold() != self.capabilities.provider_name.casefold():
            raise AssistantProviderError("La seleccion no coincide con las capacidades del proveedor.")
        if not isinstance(self.is_default, bool):
            raise AssistantProviderError("El indicador de proveedor por defecto no es valido.")


class ProviderRegistry:
    """Own registered provider instances without invoking them or doing I/O."""

    def __init__(self, providers=(), default_provider_name=None):
        self._providers = {}
        self._default_key = None
        for provider in providers:
            self.register(provider)
        if default_provider_name is not None:
            self.set_default(default_provider_name)

    def register(self, provider, make_default=False):
        """Register one provider and optionally make it the default selection."""
        if not isinstance(provider, AssistantProvider):
            raise TypeError("ProviderRegistry requiere AssistantProvider.")
        capabilities = provider.capabilities()
        if not isinstance(capabilities, ProviderCapabilitiesDTO):
            raise AssistantProviderError("El proveedor debe declarar ProviderCapabilitiesDTO.")
        key = self._key(capabilities.provider_name)
        if key in self._providers:
            raise AssistantProviderError(f"El proveedor '{capabilities.provider_name}' ya esta registrado.")
        if not isinstance(make_default, bool):
            raise AssistantProviderError("make_default debe ser booleano.")
        self._providers[key] = provider
        if make_default:
            self._default_key = key
        return self.selection(capabilities.provider_name)

    def get_provider(self, provider_name):
        """Return the registered provider instance with the requested name."""
        key = self._key(provider_name)
        try:
            return self._providers[key]
        except KeyError as error:
            raise ProviderNotFoundError(f"El proveedor '{provider_name}' no esta registrado.") from error

    def get_default_provider(self):
        """Return the explicitly selected default provider instance."""
        if self._default_key is None:
            raise ProviderNotFoundError("No hay proveedor por defecto configurado.")
        return self._providers[self._default_key]

    def set_default(self, provider_name):
        """Select an already registered provider as the default."""
        provider = self.get_provider(provider_name)
        self._default_key = self._key(provider.capabilities().provider_name)
        return self.selection(provider_name)

    def selection(self, provider_name=None):
        """Return a DTO for an explicit name or for the optional default provider."""
        provider = self.get_default_provider() if provider_name is None else self.get_provider(provider_name)
        capabilities = provider.capabilities()
        key = self._key(capabilities.provider_name)
        return ProviderSelectionDTO(
            provider_name=capabilities.provider_name,
            capabilities=capabilities,
            is_default=key == self._default_key,
        )

    def _key(self, provider_name):
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ProviderNotFoundError("El nombre del proveedor es obligatorio.")
        return provider_name.strip().casefold()
