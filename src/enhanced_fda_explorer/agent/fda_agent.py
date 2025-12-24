"""
FDA Intelligence Agent - LangGraph-based agent for FDA data exploration.
"""
from dataclasses import dataclass, field
from typing import TypedDict, Annotated, Sequence, Optional, Any
import os
import operator
import json
import uuid
import asyncio
import logging
import time

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage

logger = logging.getLogger("fda_agent")
tool_logger = logging.getLogger("fda_agent.tools")

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
    AggregateRegistrationsTool,
)
from .tools.response_tool import RespondToUserTool
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
from ..models.artifacts import DataArtifact, ArtifactType


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


def _truncate_tool_output(content: str, max_chars: int = 2000) -> str:
    """Truncate tool output to reduce token usage in conversation history.

    Preserves the beginning of the output (usually contains summary/headers)
    and adds a truncation notice if content exceeds max_chars.
    """
    if len(content) <= max_chars:
        return content
    truncated = content[:max_chars]
    last_newline = truncated.rfind('\n')
    if last_newline > max_chars * 0.7:
        truncated = truncated[:last_newline]
    return truncated + "\n\n[Output truncated for context efficiency. Full data available in structured response.]"


class ResolverContext(TypedDict, total=False):
    """Context from resolver tools for search tools to reference."""
    devices: Optional[ResolvedEntities]
    manufacturers: Optional[list[ManufacturerInfo]]
    location: Optional[LocationContext]


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    resolver_context: Annotated[ResolverContext, _merge_context]
    artifacts: Annotated[list[DataArtifact], operator.add]
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
        self._call_count = 0
        self._tool_history: list[dict] = []
        self._recent_calls: list[tuple[str, str]] = []

    def _is_duplicate_call(self, tool_name: str, args_key: str) -> bool:
        """Check if this exact tool+args combination was called recently."""
        call_sig = (tool_name, args_key)
        if call_sig in self._recent_calls[-5:]:
            tool_logger.warning(f"Duplicate tool call detected: {tool_name}({args_key})")
            return True
        self._recent_calls.append(call_sig)
        if len(self._recent_calls) > 20:
            self._recent_calls = self._recent_calls[-20:]
        return False

    def __call__(self, state: AgentState) -> dict:
        messages = state["messages"]
        last_message = messages[-1]

        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            return {"messages": []}

        self._call_count += 1
        tool_messages = []

        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "")

            args_key = json.dumps(tool_args, sort_keys=True, default=str)
            if self._is_duplicate_call(tool_name, args_key):
                tool_messages.append(ToolMessage(
                    content=f"This exact {tool_name} call was already made. The results are in a previous message. Please use those results instead of calling the tool again.",
                    tool_call_id=tool_id,
                    name=tool_name
                ))
                continue

            start_time = time.time()
            tool_logger.info(f"[Step {self._call_count}] TOOL_CALL: {tool_name}")
            tool_logger.info(f"  Args: {json.dumps(tool_args, default=str)[:500]}")

            tool = self.tools.get(tool_name)
            if tool:
                try:
                    result = tool.invoke(tool_args)
                    elapsed_ms = (time.time() - start_time) * 1000
                    result_preview = str(result)[:300] + "..." if len(str(result)) > 300 else str(result)
                    tool_logger.info(f"  Result ({elapsed_ms:.0f}ms): {result_preview}")

                    self._tool_history.append({
                        "step": self._call_count,
                        "tool": tool_name,
                        "args": tool_args,
                        "elapsed_ms": elapsed_ms,
                        "success": True
                    })

                    tool_messages.append(ToolMessage(
                        content=_truncate_tool_output(str(result)),
                        tool_call_id=tool_id,
                        name=tool_name
                    ))
                except Exception as e:
                    elapsed_ms = (time.time() - start_time) * 1000
                    tool_logger.error(f"  ERROR ({elapsed_ms:.0f}ms): {str(e)}")
                    self._tool_history.append({
                        "step": self._call_count,
                        "tool": tool_name,
                        "args": tool_args,
                        "elapsed_ms": elapsed_ms,
                        "success": False,
                        "error": str(e)
                    })
                    tool_messages.append(ToolMessage(
                        content=f"Error executing {tool_name}: {str(e)}",
                        tool_call_id=tool_id,
                        name=tool_name
                    ))
            else:
                tool_logger.warning(f"  Unknown tool: {tool_name}")
                tool_messages.append(ToolMessage(
                    content=f"Unknown tool: {tool_name}",
                    tool_call_id=tool_id,
                    name=tool_name
                ))

        new_context, new_artifacts = self._extract_context_and_artifacts(last_message.tool_calls)

        return {
            "messages": tool_messages,
            "resolver_context": new_context if new_context else None,
            "artifacts": new_artifacts or []
        }

    async def ainvoke(self, state: AgentState) -> dict:
        """Async version that runs tool _arun methods concurrently."""
        messages = state["messages"]
        last_message = messages[-1]

        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            return {"messages": []}

        self._call_count += 1
        step = self._call_count

        async def execute_tool(tool_call: dict) -> ToolMessage:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "")

            args_key = json.dumps(tool_args, sort_keys=True, default=str)
            if self._is_duplicate_call(tool_name, args_key):
                return ToolMessage(
                    content=f"This exact {tool_name} call was already made. The results are in a previous message. Please use those results instead of calling the tool again.",
                    tool_call_id=tool_id,
                    name=tool_name
                )

            start_time = time.time()
            tool_logger.info(f"[Step {step}] TOOL_CALL: {tool_name}")
            tool_logger.info(f"  Args: {json.dumps(tool_args, default=str)[:500]}")

            tool = self.tools.get(tool_name)
            if not tool:
                tool_logger.warning(f"  Unknown tool: {tool_name}")
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

                elapsed_ms = (time.time() - start_time) * 1000
                result_preview = str(result)[:300] + "..." if len(str(result)) > 300 else str(result)
                tool_logger.info(f"  Result ({elapsed_ms:.0f}ms): {result_preview}")

                self._tool_history.append({
                    "step": step,
                    "tool": tool_name,
                    "args": tool_args,
                    "elapsed_ms": elapsed_ms,
                    "success": True
                })

                return ToolMessage(
                    content=str(result),
                    tool_call_id=tool_id,
                    name=tool_name
                )
            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                tool_logger.error(f"  ERROR ({elapsed_ms:.0f}ms): {str(e)}")
                self._tool_history.append({
                    "step": step,
                    "tool": tool_name,
                    "args": tool_args,
                    "elapsed_ms": elapsed_ms,
                    "success": False,
                    "error": str(e)
                })
                return ToolMessage(
                    content=f"Error executing {tool_name}: {str(e)}",
                    tool_call_id=tool_id,
                    name=tool_name
                )

        tool_messages = await asyncio.gather(*[
            execute_tool(tc) for tc in last_message.tool_calls
        ])

        new_context, new_artifacts = self._extract_context_and_artifacts(last_message.tool_calls)

        return {
            "messages": list(tool_messages),
            "resolver_context": new_context if new_context else None,
            "artifacts": new_artifacts or []
        }

    def _extract_context_and_artifacts(self, tool_calls: list) -> tuple[Optional[ResolverContext], list[DataArtifact]]:
        """Extract structured results and create artifacts from tool executions."""
        context: ResolverContext = {}
        artifacts: list[DataArtifact] = []
        
        # Map tool calls to find arguments for artifact metadata
        tool_args_map = {tc.get("name"): tc.get("args", {}) for tc in tool_calls}

        for tool_name, tool in self.resolver_tools.items():
            # Also check aggregations tool which is now a "generator" of artifacts
            if tool_name not in self.resolver_tools and tool_name != "aggregate_registrations":
                 # We might want to add other tools here later
                 pass

        # Check all tools that might produce artifacts
        # (We iterate through self.tools basically, but filtering for ones we know produce structure)
        # Ideally we'd iterate over tool_calls, but we need the tool instance.
        
        # Let's check the specific tools we know about
        tools_to_check = list(self.resolver_tools.items())
        # Find aggregate tool in self.tools if it's not in resolver_tools dict yet (it wasn't passed in explicitly as such)
        if "aggregate_registrations" in self.tools:
            tools_to_check.append(("aggregate_registrations", self.tools["aggregate_registrations"]))

        for tool_name, tool in tools_to_check:
            # Only process if this tool was actually called in this step
            if tool_name not in tool_args_map:
                continue

            if not hasattr(tool, 'get_last_structured_result'):
                continue

            result = tool.get_last_structured_result()
            if result is None:
                continue

            # 1. Legacy Context Update
            if tool_name == "resolve_device":
                context["devices"] = result
                # Create Artifact
                artifacts.append(DataArtifact(
                    type="resolved_entities",
                    description=f"Device resolution for '{result.query}'",
                    data=result,
                    tool_name=tool_name,
                    tool_args=tool_args_map.get(tool_name, {})
                ))
            elif tool_name == "resolve_manufacturer":
                context["manufacturers"] = result
                # Create Artifact (Need to define ManufacturerList model or just use raw list?)
                # result is list[ManufacturerInfo]
                artifacts.append(DataArtifact(
                    type="manufacturers_list",
                    description=f"Manufacturer resolution",
                    data=result,
                    tool_name=tool_name,
                    tool_args=tool_args_map.get(tool_name, {})
                ))
            elif tool_name == "resolve_location":
                context["location"] = result
                artifacts.append(DataArtifact(
                    type="location_context",
                    description=f"Location resolution for '{result.location_name}'",
                    data=result,
                    tool_name=tool_name,
                    tool_args=tool_args_map.get(tool_name, {})
                ))
            elif tool_name == "aggregate_registrations":
                # New artifact type!
                query_term = result.get("query") or str(result.get("product_codes", "Unknown"))
                artifacts.append(DataArtifact(
                    type="aggregated_registrations",
                    description=f"Registration counts for '{query_term}'",
                    data=result,
                    tool_name=tool_name,
                    tool_args=tool_args_map.get(tool_name, {})
                ))

        return (context if context else None, artifacts)


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
        guard_model: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
        enable_guard: bool = False,
        checkpointer: Optional[MemorySaver] = None,
        **kwargs
    ):
        """
        Initialize the FDA Agent.

        Args:
            provider: LLM provider ("openrouter", "bedrock", "ollama")
            model: Model name (provider-specific). If None, uses provider default.
            enable_persistence: Whether to enable session persistence for multi-turn chat
            guard_model: Optional cheaper/different model for the guardrail pass
            allowed_tools: Optional list of tool names to include. If None, uses all tools.
            enable_guard: Whether to enable the guardrail audit pass (extra LLM call)
            checkpointer: Optional shared checkpointer for cross-request session persistence.
                         If provided, enable_persistence is ignored.
            **kwargs: Additional provider-specific arguments (e.g., region for bedrock)
        """
        config = get_config()

        if config.langsmith.configure_environment():
            logger.info("LangSmith tracing enabled")

        self.provider = provider
        self.enable_guard = enable_guard
        if model is None:
            env_model = os.getenv("AI_MODEL")
            if env_model:
                model = env_model
            elif getattr(config.ai, "model", None):
                model = config.ai.model
        if "max_tokens" not in kwargs and getattr(config.ai, "max_tokens", None):
            kwargs["max_tokens"] = config.ai.max_tokens
        if "timeout" not in kwargs and getattr(config.ai, "timeout", None):
            kwargs["timeout"] = config.ai.timeout
        if "streaming" not in kwargs and provider == "openrouter":
            kwargs["streaming"] = True

        self.llm = LLMFactory.create(
            provider=provider,
            model=model,
            temperature=0.1,
            **kwargs
        )
        # Guardrail model can be cheaper/different; falls back to primary LLM.
        self.guard_llm = (
            self.llm if guard_model is None
            else LLMFactory.create(provider=provider, model=guard_model, temperature=0.0, **kwargs)
        )

        self.tools = self._create_tools(config, allowed_tools)
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        if checkpointer is not None:
            self._checkpointer = checkpointer
        else:
            self._checkpointer = MemorySaver() if enable_persistence else None
        self.graph = self._build_graph()

    def _create_tools(self, config, allowed_tools: Optional[list[str]] = None) -> list:
        fda_api_key = config.openfda.api_key if hasattr(config, 'openfda') and config.openfda else None

        # Create ALL tools (needed for resolver_tools mapping)
        self._device_resolver = DeviceResolverTool(db_path=config.gudid_db_path)
        self._manufacturer_resolver = ManufacturerResolverTool(db_path=config.gudid_db_path)
        self._recalls_tool = SearchRecallsTool(api_key=fda_api_key)
        self._events_tool = SearchEventsTool(api_key=fda_api_key)
        self._location_resolver = LocationResolverTool(api_key=fda_api_key)
        self._aggregations_tool = AggregateRegistrationsTool(api_key=fda_api_key)
        self._response_tool = RespondToUserTool()

        self._resolver_tools = {
            "resolve_device": self._device_resolver,
            "resolve_manufacturer": self._manufacturer_resolver,
            "resolve_location": self._location_resolver,
        }

        # Map of all available tools by name
        all_tools_map = {
            "resolve_device": self._device_resolver,
            "resolve_manufacturer": self._manufacturer_resolver,
            "search_events": self._events_tool,
            "search_recalls": self._recalls_tool,
            "search_510k": Search510kTool(api_key=fda_api_key),
            "search_pma": SearchPMATool(api_key=fda_api_key),
            "search_classifications": SearchClassificationsTool(api_key=fda_api_key),
            "search_udi": SearchUDITool(api_key=fda_api_key),
            "search_registrations": SearchRegistrationsTool(api_key=fda_api_key),
            "resolve_location": self._location_resolver,
            "aggregate_registrations": self._aggregations_tool,
        }

        # If allowed_tools specified, filter to only those tools
        if allowed_tools:
            filtered_tools = []
            for tool_name in allowed_tools:
                if tool_name in all_tools_map:
                    filtered_tools.append(all_tools_map[tool_name])
            return filtered_tools

        # Otherwise return all tools (default behavior)
        return list(all_tools_map.values())

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ContextAwareToolNode(self.tools, self._resolver_tools))
        
        if self.enable_guard:
            workflow.add_node("guard", self._guard_response)
            workflow.set_entry_point("agent")
            workflow.add_conditional_edges(
                "agent",
                self._should_continue,
                {"continue": "tools", "end": "guard"}
            )
            workflow.add_edge("tools", "agent")
            workflow.add_edge("guard", END)
        else:
            workflow.set_entry_point("agent")
            workflow.add_conditional_edges(
                "agent",
                self._should_continue,
                {"continue": "tools", "end": END}
            )
            workflow.add_edge("tools", "agent")

        return workflow.compile(checkpointer=self._checkpointer)

    def _call_model(self, state: AgentState) -> dict:
        messages = list(state.get("messages") or [])
        msg_count = len(messages)
        tool_msg_count = sum(1 for m in messages if isinstance(m, ToolMessage))
        logger.debug(f"_call_model: {msg_count} messages ({tool_msg_count} tool results)")

        # Inject artifact context into system prompt
        artifacts = state.get("artifacts", [])
        artifact_context = ""
        if artifacts:
            artifact_list = "\n".join([
                f"- ID: {a.id} | Type: {a.type} | Desc: {a.description}"
                for a in artifacts
            ])
            artifact_context = (
                "\n\n## Available Data Artifacts\n"
                "You have created the following data artifacts in this session. "
                "You can display them to the user by referencing their IDs in the `respond_to_user` tool:\n"
                f"{artifact_list}"
            )

        has_system = any(isinstance(m, SystemMessage) for m in messages)
        if not has_system:
            system_prompt = get_fda_system_prompt() + artifact_context
            messages = [SystemMessage(content=system_prompt)] + messages
        elif artifact_context:
            # If system prompt exists, append artifact context to the last message if it's user, or inject a new system message
            # Simplest: Replace the first system message with updated one
            first_msg = messages[0]
            if isinstance(first_msg, SystemMessage):
                # We assume the first message is the main system prompt. 
                # To avoid growing it infinitely, we should ideally rebuild it.
                # For now, let's just append a fresh SystemMessage with the artifact context.
                messages.append(SystemMessage(content=artifact_context))

        response = self.llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def _should_continue(self, state: AgentState) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # Check if the agent chose the final response tool
            for tool_call in last_message.tool_calls:
                if tool_call.get("name") == "respond_to_user":
                    return "end"
            return "continue"
        return "end"

    def _guard_response(self, state: AgentState) -> dict:
        """
        Lightweight guardrail: verify the final answer against tool outputs.
        Rewrites the answer to align with tool data when unsupported claims appear.
        """
        review_prompt = (
            "You are a response auditor. Review the conversation and the final assistant answer.\n"
            "- Use only facts contained in prior tool outputs (ToolMessage content) and provided context.\n"
            "- If the final answer makes claims not supported by tool data or contradicts it, rewrite the answer to be fully grounded, "
            "explicitly noting when data is unavailable.\n"
            "- If the answer is already supported, return it unchanged.\n"
            "- Never return an empty reply. If you cannot improve the answer, return it unchanged.\n"
            "- Never invent counts, rankings, or firm names. If data is missing, say so plainly.\n"
            "- Output only the vetted answer; do not add commentary about the audit process."
        )

        guard_messages = [SystemMessage(content=review_prompt)] + list(state.get("messages") or [])
        review = self.guard_llm.invoke(guard_messages)
        content = getattr(review, "content", "")
        original = state["messages"][-1]
        original_content = getattr(original, "content", "")
        
        # If guard returns empty/whitespace, don't add any message (keep original as-is)
        if not str(content).strip():
            return {"messages": []}
        
        # If the guard response is much shorter than the original (likely dropped data), don't add any message
        if len(str(content).strip()) < max(10, 0.3 * len(str(original_content).strip())) and str(original_content).strip():
            return {"messages": []}
        
        # If the guard content is essentially the same as original, don't add duplicate
        if str(content).strip() == str(original_content).strip():
            return {"messages": []}
        
        # Only return the guard response if it's meaningfully different from the original
        return {"messages": [review]}

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

        config = {"recursion_limit": 15}
        if self._checkpointer:
            thread_id = session_id or str(uuid.uuid4())
            config["configurable"] = {"thread_id": thread_id}

        logger.info(f"Agent.ask: '{question[:80]}...' (session={session_id})")
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

        config = {"recursion_limit": 15}
        if self._checkpointer:
            thread_id = session_id or str(uuid.uuid4())
            config["configurable"] = {"thread_id": thread_id}

        logger.info(f"Agent.ask_async: '{question[:80]}...' (session={session_id})")
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

        config = {"recursion_limit": 15}
        if self._checkpointer:
            thread_id = session_id or str(uuid.uuid4())
            config["configurable"] = {"thread_id": thread_id}

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

        config = {"recursion_limit": 15}
        if self._checkpointer:
            thread_id = session_id or str(uuid.uuid4())
            config["configurable"] = {"thread_id": thread_id}

        async for event in self.graph.astream(input_state, config=config):
            yield event

    async def stream_tokens_async(self, question: str, session_id: Optional[str] = None):
        """
        Stream token-by-token for real-time typing effect on final response.

        Uses LangGraph's astream_events to capture on_chat_model_stream events,
        providing character-level streaming for the LLM's final answer.

        Args:
            question: The question to ask
            session_id: Optional session ID for multi-turn conversations

        Yields:
            dict events:
            - {"type": "clear"}  # Signals start of new LLM turn, clear previous content
            - {"type": "tool_call", "tool": str, "args": dict}
            - {"type": "tool_result", "content": str}
            - {"type": "token", "content": str}  # Individual token from LLM
            - {"type": "message_complete"}  # Signals end of an LLM message
            - {"type": "usage", "input_tokens": int, "output_tokens": int, "model": str}
        """
        input_state = {
            "messages": [HumanMessage(content=question)],
            "resolver_context": {},
            "session_id": session_id
        }

        config = {"recursion_limit": 15}
        if self._checkpointer:
            thread_id = session_id or str(uuid.uuid4())
            config["configurable"] = {"thread_id": thread_id}

        current_tool_calls = []

        async for event in self.graph.astream_events(input_state, config=config, version="v2"):
            event_type = event.get("event")

            if event_type == "on_chat_model_start":
                yield {"type": "clear"}

            elif event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk:
                    if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                        for tc in chunk.tool_call_chunks:
                            if tc.get("name"):
                                current_tool_calls.append({
                                    "name": tc.get("name"),
                                    "args": tc.get("args", {})
                                })

                    content = getattr(chunk, "content", "")
                    if content:
                        yield {"type": "token", "content": content}

            elif event_type == "on_chat_model_end":
                if current_tool_calls:
                    for tc in current_tool_calls:
                        yield {"type": "tool_call", "tool": tc["name"], "args": tc["args"]}
                    current_tool_calls = []

                output = event.get("data", {}).get("output")
                if output and isinstance(output, AIMessage):
                    usage_meta = getattr(output, "usage_metadata", None)
                    resp_meta = getattr(output, "response_metadata", None)
                    if usage_meta or resp_meta:
                        yield {
                            "type": "usage",
                            "input_tokens": usage_meta.get("input_tokens", 0) if usage_meta else 0,
                            "output_tokens": usage_meta.get("output_tokens", 0) if usage_meta else 0,
                            "model": resp_meta.get("model_name", "") if resp_meta else "",
                        }

                yield {"type": "message_complete"}

            elif event_type == "on_tool_end":
                output = event.get("data", {}).get("output", "")
                if output:
                    yield {"type": "tool_result", "content": str(output)[:500]}

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
        messages = list(history or []) + [HumanMessage(content=question)]
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

    def get_artifacts(self, session_id: str) -> list[DataArtifact]:
        """
        Retrieve the list of data artifacts for a session.

        Args:
            session_id: The session ID to retrieve artifacts for

        Returns:
            List of DataArtifact objects
        """
        if not self._checkpointer:
            return []

        try:
            config = {"configurable": {"thread_id": session_id}}
            state = self.graph.get_state(config)
            if state and state.values:
                return state.values.get("artifacts", [])
        except Exception:
            pass
        return []

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
