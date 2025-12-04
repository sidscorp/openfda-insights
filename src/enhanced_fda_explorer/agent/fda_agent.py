"""
FDA Intelligence Agent - LangGraph-based agent for FDA data exploration.
"""
from dataclasses import dataclass, field
from typing import TypedDict, Annotated, Sequence, Optional, Any
import operator
import json
import uuid
import asyncio

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage

from .prompts import get_fda_system_prompt
from .tools import (
    DeviceResolverTool,
    ManufacturerResolverTool,
    SearchEventsTool,
    SearchRecallsTool,
    Search510kTool,
    SearchPMATool,
    SearchClassificationsTool,
    SearchUDITool,
    SearchRegistrationsTool,
    LocationResolverTool,
)
from ..config import get_config
from ..llm_factory import LLMFactory
from ..models.responses import (
    AgentResponse as StructuredAgentResponse,
    ResolvedEntities,
    RecallSearchResult,
    LocationContext,
    ManufacturerInfo,
    ToolExecution,
    TokenUsage,
)


def _merge_context(existing: Optional[dict], new: Optional[dict]) -> dict:
    """Merge resolver context, keeping most recent non-None values."""
    if existing is None:
        return new or {}
    if new is None:
        return existing
    merged = dict(existing)
    for key, value in new.items():
        if value is not None:
            merged[key] = value
    return merged


class ResolverContext(TypedDict, total=False):
    """Context from resolver tools for search tools to reference."""
    devices: Optional[ResolvedEntities]
    manufacturers: Optional[list[ManufacturerInfo]]
    location: Optional[LocationContext]


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    resolver_context: Annotated[ResolverContext, _merge_context]
    session_id: Optional[str]


class ContextAwareToolNode:
    """
    Tool node that executes tools and extracts structured results from resolvers.
    Updates resolver_context in state after tool execution.
    Supports both sync and async tool execution.
    """

    def __init__(self, tools: list, resolver_tools: dict[str, Any]):
        self.tools = {t.name: t for t in tools}
        self.resolver_tools = resolver_tools

    def __call__(self, state: AgentState) -> dict:
        messages = state["messages"]
        last_message = messages[-1]

        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            return {"messages": []}

        tool_messages = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "")

            tool = self.tools.get(tool_name)
            if tool:
                try:
                    result = tool.invoke(tool_args)
                    tool_messages.append(ToolMessage(
                        content=str(result),
                        tool_call_id=tool_id,
                        name=tool_name
                    ))
                except Exception as e:
                    tool_messages.append(ToolMessage(
                        content=f"Error executing {tool_name}: {str(e)}",
                        tool_call_id=tool_id,
                        name=tool_name
                    ))
            else:
                tool_messages.append(ToolMessage(
                    content=f"Unknown tool: {tool_name}",
                    tool_call_id=tool_id,
                    name=tool_name
                ))

        new_context = self._extract_resolver_context()

        return {
            "messages": tool_messages,
            "resolver_context": new_context if new_context else None
        }

    async def ainvoke(self, state: AgentState) -> dict:
        """Async version that runs tool _arun methods concurrently."""
        messages = state["messages"]
        last_message = messages[-1]

        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            return {"messages": []}

        async def execute_tool(tool_call: dict) -> ToolMessage:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "")

            tool = self.tools.get(tool_name)
            if not tool:
                return ToolMessage(
                    content=f"Unknown tool: {tool_name}",
                    tool_call_id=tool_id,
                    name=tool_name
                )

            try:
                if hasattr(tool, 'ainvoke'):
                    result = await tool.ainvoke(tool_args)
                elif hasattr(tool, '_arun'):
                    result = await tool._arun(**tool_args)
                else:
                    result = tool.invoke(tool_args)
                return ToolMessage(
                    content=str(result),
                    tool_call_id=tool_id,
                    name=tool_name
                )
            except Exception as e:
                return ToolMessage(
                    content=f"Error executing {tool_name}: {str(e)}",
                    tool_call_id=tool_id,
                    name=tool_name
                )

        tool_messages = await asyncio.gather(*[
            execute_tool(tc) for tc in last_message.tool_calls
        ])

        new_context = self._extract_resolver_context()

        return {
            "messages": list(tool_messages),
            "resolver_context": new_context if new_context else None
        }

    def _extract_resolver_context(self) -> Optional[ResolverContext]:
        """Extract structured results from resolver tools."""
        context: ResolverContext = {}

        for tool_name, tool in self.resolver_tools.items():
            if not hasattr(tool, 'get_last_structured_result'):
                continue

            result = tool.get_last_structured_result()
            if result is None:
                continue

            if tool_name == "resolve_device":
                context["devices"] = result
            elif tool_name == "resolve_manufacturer":
                context["manufacturers"] = result
            elif tool_name == "resolve_location":
                context["location"] = result

        return context if context else None


@dataclass
class AgentResponse:
    """Response from the FDA agent with usage statistics."""
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: Optional[float] = None
    model: str = ""
    generation_id: str = ""
    structured: Optional[StructuredAgentResponse] = None


class FDAAgent:
    """
    FDA Intelligence Agent using LangGraph StateGraph.
    Single agent with 10 tools for comprehensive FDA data exploration.
    Supports multi-turn conversations via session persistence.
    """

    def __init__(
        self,
        provider: str = "openrouter",
        model: Optional[str] = None,
        enable_persistence: bool = True,
        **kwargs
    ):
        """
        Initialize the FDA Agent.

        Args:
            provider: LLM provider ("openrouter", "bedrock", "ollama")
            model: Model name (provider-specific). If None, uses provider default.
            enable_persistence: Whether to enable session persistence for multi-turn chat
            **kwargs: Additional provider-specific arguments (e.g., region for bedrock)
        """
        config = get_config()

        self.provider = provider
        self.llm = LLMFactory.create(
            provider=provider,
            model=model,
            temperature=0.1,
            **kwargs
        )

        self.tools = self._create_tools(config)
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self._checkpointer = MemorySaver() if enable_persistence else None
        self.graph = self._build_graph()

    def _create_tools(self, config) -> list:
        fda_api_key = config.openfda.api_key if hasattr(config, 'openfda') and config.openfda else None

        self._device_resolver = DeviceResolverTool(db_path=config.gudid_db_path)
        self._manufacturer_resolver = ManufacturerResolverTool(db_path=config.gudid_db_path)
        self._recalls_tool = SearchRecallsTool(api_key=fda_api_key)
        self._location_resolver = LocationResolverTool(api_key=fda_api_key)

        self._resolver_tools = {
            "resolve_device": self._device_resolver,
            "resolve_manufacturer": self._manufacturer_resolver,
            "resolve_location": self._location_resolver,
        }

        return [
            self._device_resolver,
            self._manufacturer_resolver,
            SearchEventsTool(api_key=fda_api_key),
            self._recalls_tool,
            Search510kTool(api_key=fda_api_key),
            SearchPMATool(api_key=fda_api_key),
            SearchClassificationsTool(api_key=fda_api_key),
            SearchUDITool(api_key=fda_api_key),
            SearchRegistrationsTool(api_key=fda_api_key),
            self._location_resolver,
        ]

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ContextAwareToolNode(self.tools, self._resolver_tools))

        workflow.set_entry_point("agent")

        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {"continue": "tools", "end": END}
        )
        workflow.add_edge("tools", "agent")

        return workflow.compile(checkpointer=self._checkpointer)

    def _call_model(self, state: AgentState) -> dict:
        messages = list(state["messages"])

        has_system = any(isinstance(m, SystemMessage) for m in messages)
        if not has_system:
            messages = [SystemMessage(content=get_fda_system_prompt())] + messages

        response = self.llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def _should_continue(self, state: AgentState) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"
        return "end"

    def ask(self, question: str, session_id: Optional[str] = None) -> AgentResponse:
        """
        Ask the FDA agent a question and get a response with usage statistics.

        Args:
            question: The question to ask about FDA data
            session_id: Optional session ID for multi-turn conversations.
                        If provided, conversation history and resolver context persist.
                        If None with persistence enabled, creates a new session.

        Returns:
            AgentResponse with content, token counts, and cost
        """
        input_state = {
            "messages": [HumanMessage(content=question)],
            "resolver_context": {},
            "session_id": session_id
        }

        config = None
        if self._checkpointer:
            thread_id = session_id or str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}

        result = self.graph.invoke(input_state, config=config)
        return self._extract_response(result)

    async def ask_async(self, question: str, session_id: Optional[str] = None) -> AgentResponse:
        """
        Async version of ask() for non-blocking execution.

        This method enables concurrent tool execution when the LLM requests
        multiple tools. Each tool's async HTTP calls run in parallel, significantly
        reducing response time for queries that span multiple FDA databases.

        Args:
            question: The question to ask about FDA data
            session_id: Optional session ID for multi-turn conversations

        Returns:
            AgentResponse with content, token counts, and cost
        """
        input_state = {
            "messages": [HumanMessage(content=question)],
            "resolver_context": {},
            "session_id": session_id
        }

        config = None
        if self._checkpointer:
            thread_id = session_id or str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}

        result = await self.graph.ainvoke(input_state, config=config)
        return self._extract_response(result)

    def _extract_response(self, result: dict) -> AgentResponse:
        """Extract usage statistics and structured data from result messages."""
        total_input = 0
        total_output = 0
        total_cost = 0.0
        generation_ids = []
        model_name = ""
        tool_executions = []

        for msg in result["messages"]:
            if isinstance(msg, AIMessage):
                if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                    total_input += msg.usage_metadata.get("input_tokens", 0)
                    total_output += msg.usage_metadata.get("output_tokens", 0)
                if hasattr(msg, 'response_metadata') and msg.response_metadata:
                    gen_id = msg.response_metadata.get("id")
                    if gen_id:
                        generation_ids.append(gen_id)
                    model_name = msg.response_metadata.get("model_name", model_name)
                    token_usage = msg.response_metadata.get("token_usage", {})
                    if token_usage.get("cost"):
                        total_cost += token_usage["cost"]

                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_executions.append(ToolExecution(
                            tool_name=tc.get("name", ""),
                            arguments=tc.get("args", {}),
                            result_type="pending"
                        ))

        structured = self._build_structured_response(
            summary=result["messages"][-1].content,
            model_name=model_name,
            total_input=total_input,
            total_output=total_output,
            total_cost=total_cost,
            tool_executions=tool_executions
        )

        return AgentResponse(
            content=result["messages"][-1].content,
            input_tokens=total_input,
            output_tokens=total_output,
            total_tokens=total_input + total_output,
            cost=total_cost if total_cost > 0 else None,
            model=model_name,
            generation_id=generation_ids[-1] if generation_ids else "",
            structured=structured
        )

    def _build_structured_response(
        self,
        summary: str,
        model_name: str,
        total_input: int,
        total_output: int,
        total_cost: float,
        tool_executions: list[ToolExecution]
    ) -> StructuredAgentResponse:
        resolved_entities = self._device_resolver.get_last_structured_result()
        recall_results = self._recalls_tool.get_last_structured_result()

        return StructuredAgentResponse(
            summary=summary,
            resolved_entities=resolved_entities,
            recall_results=recall_results,
            tools_executed=tool_executions,
            model=model_name,
            token_usage=TokenUsage(
                input_tokens=total_input,
                output_tokens=total_output,
                total_tokens=total_input + total_output,
                cost_usd=total_cost if total_cost > 0 else None
            )
        )

    def stream(self, question: str, session_id: Optional[str] = None):
        """
        Stream the agent's response for real-time updates.

        Args:
            question: The question to ask
            session_id: Optional session ID for multi-turn conversations

        Yields:
            Events from the agent execution
        """
        input_state = {
            "messages": [HumanMessage(content=question)],
            "resolver_context": {},
            "session_id": session_id
        }

        config = None
        if self._checkpointer:
            thread_id = session_id or str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}

        for event in self.graph.stream(input_state, config=config):
            yield event

    async def stream_async(self, question: str, session_id: Optional[str] = None):
        """
        Async stream the agent's response for real-time updates.

        Args:
            question: The question to ask
            session_id: Optional session ID for multi-turn conversations

        Yields:
            Events from the agent execution
        """
        input_state = {
            "messages": [HumanMessage(content=question)],
            "resolver_context": {},
            "session_id": session_id
        }

        config = None
        if self._checkpointer:
            thread_id = session_id or str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}

        async for event in self.graph.astream(input_state, config=config):
            yield event

    def ask_with_history(self, question: str, history: list[BaseMessage], session_id: Optional[str] = None) -> AgentResponse:
        """
        Ask a question with conversation history for follow-up questions.
        Note: Prefer using ask() with session_id for multi-turn conversations.

        Args:
            question: The new question
            history: Previous messages in the conversation
            session_id: Optional session ID for context persistence

        Returns:
            AgentResponse with content, token counts, and cost
        """
        messages = list(history) + [HumanMessage(content=question)]
        input_state = {
            "messages": messages,
            "resolver_context": {},
            "session_id": session_id
        }

        config = None
        if self._checkpointer and session_id:
            config = {"configurable": {"thread_id": session_id}}

        result = self.graph.invoke(input_state, config=config)
        return self._extract_response(result)

    def get_session_context(self, session_id: str) -> Optional[ResolverContext]:
        """
        Retrieve the current resolver context for a session.

        Args:
            session_id: The session ID to retrieve context for

        Returns:
            ResolverContext if session exists and has context, None otherwise
        """
        if not self._checkpointer:
            return None

        try:
            config = {"configurable": {"thread_id": session_id}}
            state = self.graph.get_state(config)
            if state and state.values:
                return state.values.get("resolver_context")
        except Exception:
            pass
        return None

    def clear_session(self, session_id: str) -> bool:
        """
        Clear a session's state (conversation history and resolver context).

        Args:
            session_id: The session ID to clear

        Returns:
            True if session was cleared successfully
        """
        if not self._checkpointer:
            return False

        try:
            config = {"configurable": {"thread_id": session_id}}
            self.graph.update_state(config, {
                "messages": [],
                "resolver_context": {},
                "session_id": None
            })
            return True
        except Exception:
            return False
