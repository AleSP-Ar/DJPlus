"""Provider-neutral, side-effect-free runtime core for the assistant."""

from dataclasses import dataclass
from datetime import datetime, timezone

from .assistant_context import AssistantContextDTO
from .action_pipeline import ActionPipeline, ActionType
from .conversation_session import ConversationSession, MessageRole
from .confirmation_manager import ConfirmationManager, ConfirmationRequestDTO, ConfirmationResultDTO
from .prompt_builder import PromptBuilder, PromptDTO
from .tool_dispatcher import ToolCallDTO, ToolDispatcher, ToolRegistry, ToolResultDTO


class AssistantRuntimeError(ValueError):
    """Raised when a runtime request or result violates its safe contract."""


@dataclass(frozen=True)
class RuntimeRequestDTO:
    """Validated input for one isolated assistant runtime request."""

    user_query: str
    assistant_context: AssistantContextDTO
    session_id: str
    timestamp_utc: datetime
    tool_calls: tuple[ToolCallDTO, ...] = ()
    confirmation_request: ConfirmationRequestDTO | None = None

    def __post_init__(self):
        if not isinstance(self.user_query, str) or not self.user_query.strip():
            raise AssistantRuntimeError("La consulta del usuario es obligatoria.")
        if not isinstance(self.assistant_context, AssistantContextDTO):
            raise AssistantRuntimeError("El runtime requiere AssistantContextDTO.")
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise AssistantRuntimeError("La sesión del runtime es obligatoria.")
        if not isinstance(self.timestamp_utc, datetime) or self.timestamp_utc.tzinfo is None:
            raise AssistantRuntimeError("El timestamp debe incluir zona horaria UTC.")
        if self.timestamp_utc.utcoffset() != timezone.utc.utcoffset(self.timestamp_utc):
            raise AssistantRuntimeError("El timestamp del runtime debe estar en UTC.")
        if not isinstance(self.tool_calls, tuple) or not all(isinstance(call, ToolCallDTO) for call in self.tool_calls):
            raise AssistantRuntimeError("Las llamadas del runtime deben ser ToolCallDTO inmutables.")
        if self.confirmation_request is not None and not isinstance(self.confirmation_request, ConfirmationRequestDTO):
            raise AssistantRuntimeError("La confirmación del runtime debe ser ConfirmationRequestDTO.")


@dataclass(frozen=True)
class RuntimeResultDTO:
    """Side-effect-free runtime output prepared for future collaborators."""

    generated_prompt: PromptDTO | None
    tool_calls: tuple[ToolCallDTO, ...] = ()
    tool_results: tuple[ToolResultDTO, ...] = ()
    assistant_response: object | None = None
    proposed_actions: tuple = ()
    confirmation_result: ConfirmationResultDTO | None = None

    def __post_init__(self):
        if self.generated_prompt is not None and not isinstance(self.generated_prompt, PromptDTO):
            raise AssistantRuntimeError("El prompt generado debe ser PromptDTO o nulo.")
        for field_name in ("tool_calls", "tool_results", "proposed_actions"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple):
                raise AssistantRuntimeError(f"{field_name} debe ser una tupla inmutable.")


class AssistantRuntime:
    """Own the runtime flow while remaining independent of providers and infrastructure."""

    def __init__(self, dispatcher=None, prompt_builder=None, conversation_session=None, action_pipeline=None, confirmation_manager=None):
        self._dispatcher = dispatcher or ToolDispatcher(ToolRegistry())
        if not isinstance(self._dispatcher, ToolDispatcher):
            raise TypeError("AssistantRuntime requiere ToolDispatcher.")
        self._prompt_builder = prompt_builder or PromptBuilder(self._dispatcher.registry)
        if not isinstance(self._prompt_builder, PromptBuilder):
            raise TypeError("AssistantRuntime requiere PromptBuilder.")
        if conversation_session is not None and not isinstance(conversation_session, ConversationSession):
            raise TypeError("AssistantRuntime requiere ConversationSession.")
        self._conversation_session = conversation_session
        self._action_pipeline = action_pipeline or ActionPipeline()
        if not isinstance(self._action_pipeline, ActionPipeline):
            raise TypeError("AssistantRuntime requiere ActionPipeline.")
        self._confirmation_manager = confirmation_manager or ConfirmationManager(self._action_pipeline)
        if not isinstance(self._confirmation_manager, ConfirmationManager):
            raise TypeError("AssistantRuntime requiere ConfirmationManager.")

    def process(self, request):
        """Validate a request and delegate every requested tool call to the dispatcher."""
        if not isinstance(request, RuntimeRequestDTO):
            raise TypeError("AssistantRuntime.process requiere RuntimeRequestDTO.")

        self._record_user_message(request)
        prompt = self._prompt_builder.build(request)
        tool_results = tuple(self._dispatcher.dispatch(call) for call in request.tool_calls)
        proposed_actions = self._store_tool_proposals(tool_results)
        confirmation_result = self._confirm_proposal(request.confirmation_request)
        return RuntimeResultDTO(
            generated_prompt=prompt,
            tool_calls=request.tool_calls,
            tool_results=tool_results,
            assistant_response=None,
            proposed_actions=proposed_actions,
            confirmation_result=confirmation_result,
        )

    def _record_user_message(self, request):
        if self._conversation_session is None:
            return
        if request.session_id != self._conversation_session.session_id:
            raise AssistantRuntimeError("La sesión del request no coincide con ConversationSession.")
        self._conversation_session.add_message(MessageRole.USER, request.user_query)

    def _store_tool_proposals(self, tool_results):
        proposals = []
        for tool_result in tool_results:
            if not tool_result.success:
                continue
            for tool_proposal in tool_result.result.proposed_actions:
                try:
                    action_type = ActionType(tool_proposal.action_type)
                except ValueError:
                    action_type = ActionType.CUSTOM
                proposals.append(
                    self._action_pipeline.create_proposal(
                        action_type=action_type,
                        title=tool_proposal.label,
                        description="Propuesta generada por una herramienta permitida.",
                        payload=dict(tool_proposal.payload),
                    )
                )
        return tuple(proposals)

    def _confirm_proposal(self, confirmation_request):
        if confirmation_request is None:
            return None
        return self._confirmation_manager.request_confirmation(confirmation_request)
