"""
Router with proper LangChain tool calling.

Replaces string-matching with structured tool selection.
Rationale: CEO resolution #1 - deterministic routing with confidence scores.
"""
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool


# Define tool selectors (not the actual HTTP tools, just routing indicators)
@tool
def select_classification(query: str) -> str:
    """Use for device class queries, regulation numbers, and product code classifications."""
    return ""


@tool
def select_510k(query: str) -> str:
    """Use for 510(k) clearances, K-numbers, premarket notifications."""
    return ""


@tool
def select_pma(query: str) -> str:
    """Use for PMA approvals, P-numbers, premarket approvals."""
    return ""


@tool
def select_recall(query: str) -> str:
    """Use for enforcement actions, recalls, recall classifications."""
    return ""


@tool
def select_maude(query: str) -> str:
    """Use for adverse events, MAUDE reports, event types, injuries, deaths."""
    return ""


@tool
def select_udi(query: str) -> str:
    """Use for UDI lookups, GUDID, device identifiers, DI/PI."""
    return ""


@tool
def select_rl(query: str) -> str:
    """Use for registration & listing, establishments, owner/operator, FEI numbers."""
    return ""


# All selector tools
SELECTORS = [
    select_classification,
    select_510k,
    select_pma,
    select_recall,
    select_maude,
    select_udi,
    select_rl,
]

# System prompt for router
ROUTER_SYSTEM = """You are the Router for an FDA Device Analyst agent.

Your job: Choose EXACTLY ONE tool that best answers the user's question.

Rules:
1. Pick the MOST LIKELY endpoint based on question semantics
2. If truly ambiguous, return no tool call (we'll handle disambiguation)
3. Do not invent tools or combine multiple tools
4. Use the tool descriptions to understand endpoint semantics
5. Consider RAG hints if provided (they contain endpoint-specific docs)

Examples:
- "Show me Class II devices" → select_classification
- "Find 510k clearances from Medtronic" → select_510k
- "What PMA approvals happened in 2024?" → select_pma
- "Any recalls for syringes?" → select_recall
- "Adverse events for pacemakers" → select_maude
- "Lookup UDI 00819320201234" → select_udi
- "Show establishments in California" → select_rl
"""


def route(question: str, llm: ChatAnthropic, rag_hints: Optional[str] = None) -> str:
    """
    Route a question to the appropriate endpoint using LangChain tool calling.

    Args:
        question: User's natural language question
        llm: ChatAnthropic instance
        rag_hints: Optional RAG documentation hints

    Returns:
        Endpoint name: "classification", "510k", "pma", "recall", "maude", "udi", "rl_search"
        or "disambiguate" if unclear
    """
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(SELECTORS)

    # Build messages
    messages = [SystemMessage(content=ROUTER_SYSTEM)]

    # Add RAG hints if available
    if rag_hints:
        messages.append(
            HumanMessage(
                content=f"Routing hints from documentation:\n\n{rag_hints}\n\nNow route this question:"
            )
        )

    messages.append(HumanMessage(content=question))

    # Get response with tool calls
    response = llm_with_tools.invoke(messages)

    # Extract tool call
    tool_calls = getattr(response, "tool_calls", None)
    if not tool_calls:
        # No clear choice - ask for disambiguation
        return "disambiguate"

    # Map tool name to endpoint
    tool_name = tool_calls[0]["name"]
    endpoint_map = {
        "select_classification": "classification",
        "select_510k": "510k",
        "select_pma": "pma",
        "select_recall": "recall",
        "select_maude": "maude",
        "select_udi": "udi",
        "select_rl": "rl_search",
    }

    return endpoint_map.get(tool_name, "disambiguate")
