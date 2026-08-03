import unittest
from dataclasses import FrozenInstanceError

from app.services.assistant_provider import AssistantProviderError, MockAssistantProvider, ProviderCapabilitiesDTO
from app.services.provider_registry import ProviderNotFoundError, ProviderRegistry, ProviderSelectionDTO


class NamedMockAssistantProvider(MockAssistantProvider):
    def __init__(self, name):
        super().__init__()
        self.provider_name = name
        self._capabilities = ProviderCapabilitiesDTO(name, self.provider_version)


class ProviderRegistryTests(unittest.TestCase):
    def setUp(self):
        self.mock = MockAssistantProvider()
        self.local = NamedMockAssistantProvider("local")
        self.registry = ProviderRegistry()

    def test_registers_and_returns_provider_by_normalized_name(self):
        selection = self.registry.register(self.mock)

        self.assertEqual(selection, ProviderSelectionDTO("mock", ProviderCapabilitiesDTO("mock", "1.0")))
        self.assertIs(self.registry.get_provider(" MOCK "), self.mock)
        self.assertFalse(selection.is_default)

    def test_rejects_duplicate_provider_names_case_insensitively(self):
        self.registry.register(self.mock)

        with self.assertRaises(AssistantProviderError):
            self.registry.register(NamedMockAssistantProvider("MOCK"))

    def test_supports_optional_default_provider_and_selection(self):
        self.registry.register(self.mock)
        registered = self.registry.register(self.local, make_default=True)

        self.assertTrue(registered.is_default)
        self.assertIs(self.registry.get_default_provider(), self.local)
        self.assertEqual(self.registry.selection(), registered)
        self.assertEqual(self.registry.selection("mock").provider_name, "mock")
        selected = self.registry.set_default("mock")
        self.assertTrue(selected.is_default)
        self.assertFalse(self.registry.selection("local").is_default)

    def test_rejects_unknown_provider_and_invalid_selection_contracts(self):
        with self.assertRaises(ProviderNotFoundError):
            self.registry.get_default_provider()
        with self.assertRaises(ProviderNotFoundError):
            self.registry.get_provider("missing")
        with self.assertRaises(TypeError):
            self.registry.register(object())
        selection = ProviderSelectionDTO("mock", ProviderCapabilitiesDTO("mock", "1.0"))
        with self.assertRaises(FrozenInstanceError):
            selection.is_default = True
        with self.assertRaises(AssistantProviderError):
            ProviderSelectionDTO("other", ProviderCapabilitiesDTO("mock", "1.0"))
