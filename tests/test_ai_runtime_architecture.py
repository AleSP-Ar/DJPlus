import ast
import unittest
from pathlib import Path


RUNTIME_MODULES = {
    "assistant_runtime",
    "assistant_provider",
    "provider_registry",
    "provider_credentials",
    "provider_transport",
    "provider_adapters",
    "library_tools",
    "tool_dispatcher",
    "prompt_builder",
    "conversation_session",
    "action_pipeline",
    "action_executor",
    "confirmation_manager",
    "local_assistant_mvp",
}
INFRASTRUCTURE_IMPORT_PREFIXES = (
    "app.repository", "app.database", "sqlalchemy", "sqlite3", "pathlib", "os", "requests", "httpx",
)
SERVICE_DIRECTORY = Path(__file__).resolve().parents[1] / "app" / "services"


def _imports_for(module_name):
    tree = ast.parse((SERVICE_DIRECTORY / f"{module_name}.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 1 and node.module:
                imports.add(node.module.split(".")[0])
            elif node.module:
                imports.add(node.module)
    return imports


class AIRuntimeArchitectureTests(unittest.TestCase):
    def test_runtime_modules_do_not_import_infrastructure(self):
        for module_name in RUNTIME_MODULES:
            with self.subTest(module=module_name):
                imports = _imports_for(module_name)
                for prefix in INFRASTRUCTURE_IMPORT_PREFIXES:
                    self.assertFalse(
                        any(import_name == prefix or import_name.startswith(f"{prefix}.") for import_name in imports),
                        f"{module_name} no debe importar {prefix}",
                    )

    def test_runtime_module_import_graph_is_acyclic(self):
        graph = {
            module_name: {dependency for dependency in _imports_for(module_name) if dependency in RUNTIME_MODULES}
            for module_name in RUNTIME_MODULES
        }
        visiting = set()
        visited = set()

        def visit(module_name):
            self.assertNotIn(module_name, visiting, f"Dependencia circular detectada en {module_name}")
            if module_name in visited:
                return
            visiting.add(module_name)
            for dependency in graph[module_name]:
                visit(dependency)
            visiting.remove(module_name)
            visited.add(module_name)

        for module_name in graph:
            visit(module_name)

    def test_only_local_transport_may_use_stdlib_network_modules(self):
        for module_name in RUNTIME_MODULES:
            imports = _imports_for(module_name)
            uses_stdlib_network = any(
                name == prefix or name.startswith(f"{prefix}.")
                for name in imports for prefix in ("urllib", "socket")
            )
            self.assertEqual(uses_stdlib_network, module_name == "provider_transport")

    def test_runtime_public_contracts_are_exported(self):
        import app.services as services

        expected_exports = {
            "AssistantRuntime", "RuntimeRequestDTO", "RuntimeResultDTO",
            "AssistantProvider", "ProviderRequestDTO", "ProviderResponseDTO", "ProviderCapabilitiesDTO", "MockAssistantProvider",
            "ProviderConfigDTO", "ProviderPolicy", "RetryPolicyDTO", "ProviderUsageDTO", "ProviderErrorDTO", "ProviderExecutionResultDTO", "ProviderCancellationToken",
            "ProviderRegistry", "ProviderSelectionDTO", "ProviderNotFoundError",
            "CredentialProvider", "InMemoryCredentialProvider", "ProviderCredentialRefDTO", "SecretRedactor", "CredentialNotFoundError",
            "ProviderTransport", "TransportRequestDTO", "TransportResponseDTO", "TransportErrorDTO", "MockProviderTransport", "LocalhostHTTPProviderTransport",
            "OpenAIProvider", "OllamaProvider", "LMStudioProvider", "ProviderFactory", "ProviderCapabilityResolver", "ProviderCapabilityError", "OllamaLocalConfigDTO",
            "LibraryQueryTool", "PlaylistTool", "CollectionTool", "LibraryQueryInputDTO", "PlaylistToolInputDTO", "CollectionToolInputDTO",
            "FavoriteTool", "HistoryTool", "ImportTool", "FavoriteToolInputDTO", "HistoryToolInputDTO", "ImportToolInputDTO",
            "DJCompatibilityTool", "MusicAnalysisTool", "DJCompatibilityInputDTO", "MusicAnalysisInputDTO", "ToolSchemaValidator", "ToolSchemaValidationError",
            "ToolRegistry", "ToolDispatcher", "ToolCallDTO", "ToolResultDTO",
            "PromptBuilder", "PromptDTO",
            "ConversationSession", "ConversationSessionDTO", "ConversationMessageDTO", "MessageRole",
            "ActionPipeline", "ActionProposalDTO", "ActionValidationDTO", "ActionType",
            "ActionExecutor", "ExecutionRequestDTO", "ExecutionResultDTO", "MockActionExecutor", "ActionExecutionError",
            "ExecutionAuditEntryDTO", "ExecutionAuditLog", "IdempotencyRegistry", "RollbackResultDTO",
            "ActionExecutionService", "ActionExecutionServiceError", "ActionExecutionAuthorizationDTO",
            "ActionExecutionServiceResultDTO", "ActionExecutionState",
            "LocalAssistantConfigDTO", "LocalAssistantMVP",
            "ConfirmationManager", "ConfirmationPolicy", "ConfirmationRequestDTO", "ConfirmationResultDTO",
        }
        self.assertTrue(expected_exports.issubset(set(services.__all__)))
