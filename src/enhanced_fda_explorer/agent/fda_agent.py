"""
FDA Intelligence Agent - LangGraph-based agent for FDA data exploration.
"""
from dataclasses import dataclass
from typing import TypedDict, Annotated, Sequence, Optional
import operator

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage

from .prompts import FDA_SYSTEM_PROMPT
from .tools import (
    DeviceResolverTool,
    SearchEventsTool,
    SearchRecallsTool,
    Search510kTool,
    SearchPMATool,
    SearchClassificationsTool,
    SearchUDITool,
)
from ..config import get_config
from ..llm_factory import LLMFactory


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]


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


class FDAAgent:
    """
    FDA Intelligence Agent using LangGraph StateGraph.
    Single agent with 7 tools for comprehensive FDA data exploration.
    """

    def __init__(
        self,
        provider: str = "openrouter",
        model: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the FDA Agent.

        Args:
            provider: LLM provider ("openrouter", "bedrock", "ollama")
            model: Model name (provider-specific). If None, uses provider default.
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
        self.graph = self._build_graph()

    def _create_tools(self, config) -> list:
        fda_api_key = config.openfda.api_key if hasattr(config, 'openfda') and config.openfda else None

        return [
            DeviceResolverTool(db_path=config.gudid_db_path),
            SearchEventsTool(api_key=fda_api_key),
            SearchRecallsTool(api_key=fda_api_key),
            Search510kTool(api_key=fda_api_key),
            SearchPMATool(api_key=fda_api_key),
            SearchClassificationsTool(api_key=fda_api_key),
            SearchUDITool(api_key=fda_api_key),
        ]

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ToolNode(self.tools))

        workflow.set_entry_point("agent")

        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {"continue": "tools", "end": END}
        )
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    def _call_model(self, state: AgentState) -> dict:
        messages = list(state["messages"])

        has_system = any(isinstance(m, SystemMessage) for m in messages)
        if not has_system:
            messages = [SystemMessage(content=FDA_SYSTEM_PROMPT)] + messages

        response = self.llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def _should_continue(self, state: AgentState) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"
        return "end"

    def ask(self, question: str) -> AgentResponse:
        """
        Ask the FDA agent a question and get a response with usage statistics.

        Args:
            question: The question to ask about FDA data

        Returns:
            AgentResponse with content, token counts, and cost
        """
        result = self.graph.invoke({
            "messages": [HumanMessage(content=question)]
        })

        return self._extract_response(result)

    def _extract_response(self, result: dict) -> AgentResponse:
        """Extract usage statistics from result messages."""
        total_input = 0
        total_output = 0
        total_cost = 0.0
        generation_ids = []
        model_name = ""

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

        return AgentResponse(
            content=result["messages"][-1].content,
            input_tokens=total_input,
            output_tokens=total_output,
            total_tokens=total_input + total_output,
            cost=total_cost if total_cost > 0 else None,
            model=model_name,
            generation_id=generation_ids[-1] if generation_ids else ""
        )

    def stream(self, question: str):
        """
        Stream the agent's response for real-time updates.

        Args:
            question: The question to ask

        Yields:
            Events from the agent execution
        """
        for event in self.graph.stream({
            "messages": [HumanMessage(content=question)]
        }):
            yield event

    def ask_with_history(self, question: str, history: list[BaseMessage]) -> AgentResponse:
        """
        Ask a question with conversation history for follow-up questions.

        Args:
            question: The new question
            history: Previous messages in the conversation

        Returns:
            AgentResponse with content, token counts, and cost
        """
        messages = list(history) + [HumanMessage(content=question)]
        result = self.graph.invoke({"messages": messages})
        return self._extract_response(result)
