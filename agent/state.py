"""
Agent state definition for LangGraph.

State tracks the conversation, tool calls, results, and retry count.
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """A tool invocation with parameters and result."""

    tool_name: str
    params: dict
    result: Optional[dict] = None
    error: Optional[str] = None


class AgentState(BaseModel):
    """State for FDA Device Analyst agent graph."""

    # User input
    question: str = Field(description="Original user question")

    # Routing & tool selection
    detected_entities: dict = Field(
        default_factory=dict, description="Detected entities (product codes, dates, etc.)"
    )
    selected_tools: List[str] = Field(
        default_factory=list, description="Tools selected by router"
    )

    # Planning & strategy
    plan: List[str] = Field(default_factory=list, description="Execution plan steps")
    current_plan_step: int = Field(0, description="Current step in plan")
    search_strategy: str = Field("", description="How to search (exact, category, broad)")
    is_safety_check: bool = Field(False, description="True if performing comprehensive safety check")
    safety_results: dict = Field(default_factory=dict, description="Results from multiple safety endpoints")
    query_analysis: dict = Field(default_factory=dict, description="LLM analysis of query type and intent")

    # Tool execution
    tool_calls: List[ToolCall] = Field(
        default_factory=list, description="History of tool calls"
    )
    current_result: Optional[dict] = Field(None, description="Latest tool result")
    extracted_params: Optional[dict] = Field(None, description="Extracted parameters from question")
    lucene_query: str = Field("", description="Generated Lucene query for API (CEO Resolution #4)")

    # Assessment
    is_sufficient: bool = Field(False, description="True if answer meets requirements")
    assessment_reason: str = Field("", description="Explanation from assessor")
    retry_count: int = Field(0, description="Number of retry attempts")
    rag_retry_count: int = Field(0, description="RAG field discovery retries (CEO Resolution #3)")

    # Final output
    answer: str = Field("", description="Final answer to user")
    provenance: dict = Field(
        default_factory=dict,
        description="Provenance: endpoint, filters, last_updated",
    )

    # Conversation memory
    messages: List[dict] = Field(
        default_factory=list, description="Conversation history for LLM"
    )
