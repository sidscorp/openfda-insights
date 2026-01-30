"""
Query Router - Fast LLM that classifies queries and determines required tools.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)
from langchain_core.messages import HumanMessage, SystemMessage
from ..llm_factory import LLMFactory


TOOL_SETS = {
    "device_lookup": ["resolve_device", "list_devices"],
    "recall_search": ["resolve_device", "list_devices", "search_recalls"],
    "event_search": ["resolve_device", "list_devices", "search_events"],
    "geographic": ["resolve_device", "resolve_location", "aggregate_registrations", "search_registrations", "search_events", "search_recalls"],
    "comparison": ["resolve_device", "list_devices", "search_events", "search_recalls"],
    "regulatory": ["resolve_device", "list_devices", "search_classifications", "search_510k"],
    "clearance_510k": ["resolve_device", "list_devices", "search_510k"],
    "pma": ["resolve_device", "list_devices", "search_pma"],
    "manufacturer": ["resolve_device", "resolve_manufacturer", "aggregate_registrations", "list_devices", "search_events", "search_recalls"],
    "registration": ["resolve_device", "search_registrations", "aggregate_registrations"],
    "comprehensive": [
        "resolve_device",
        "list_devices",
        "resolve_manufacturer",
        "resolve_location",
        "search_events",
        "search_recalls",
        "search_510k",
        "search_pma",
        "search_classifications",
        "search_udi",
        "search_registrations",
        "aggregate_registrations",
    ],
}

ROUTER_SYSTEM_PROMPT = """You are a query classifier for FDA medical device database queries.

Your job is to classify the user's question into ONE category and return the required tools.

Categories and their tools:

1. **device_lookup**: Questions about product codes, device definitions, or listing specific devices
   - Tools: resolve_device, list_devices
   - Examples: "What is product code MSH?", "What devices are FXX?", "Show me devices for code QAB"

2. **recall_search**: Questions about recalls, enforcement actions
   - Tools: resolve_device, search_recalls
   - Examples: "Show recalls for surgical masks", "Any recalls for 3M?"

3. **event_search**: Questions about adverse events, safety issues, MAUDE reports
   - Tools: resolve_device, search_events
   - Examples: "Show adverse events for pacemakers", "Safety issues with masks"

4. **geographic**: Questions about devices by country/region, manufacturer locations, country rankings
   - Tools: resolve_device, resolve_location, aggregate_registrations, search_registrations, search_events, search_recalls
   - Examples: "Which country makes the most masks?", "Devices from China", "Top manufacturers by country", "Where are ventilator manufacturers located?"

5. **comparison**: Comparing multiple devices or manufacturers
   - Tools: resolve_device, search_events, search_recalls
   - Examples: "Compare pacemakers vs defibrillators", "Compare 3M vs Medtronic"

6. **regulatory**: Questions about device class, regulatory pathway, 510k vs PMA
   - Tools: resolve_device, search_classifications, search_510k
   - Examples: "What class is X?", "Does X need 510k?", "Regulatory requirements for Y"

7. **clearance_510k**: Specific questions about 510k clearances
   - Tools: resolve_device, search_510k
   - Examples: "510k clearances for masks", "Recent 510k for X"

8. **pma**: Specific questions about PMA approvals
   - Tools: resolve_device, search_pma
   - Examples: "PMA approvals for X", "Has Y been approved via PMA?"

9. **manufacturer**: Questions about specific manufacturers, top manufacturers, manufacturer rankings
   - Tools: resolve_device, resolve_manufacturer, aggregate_registrations, list_devices, search_events, search_recalls
   - Examples: "Who are the top manufacturers of X?", "What does 3M make?", "Show me Medtronic devices"

10. **registration**: Questions about FDA establishment registrations, facility data
    - Tools: resolve_device, search_registrations, aggregate_registrations
    - Examples: "Where is company X registered?", "Registration data for Y"

11. **comprehensive**: Complex questions needing multiple tool types or unclear intent
    - Tools: All 11 tools
    - Examples: "Tell me everything about X", "Complete analysis of Y"

Respond ONLY with valid JSON:
{
  "category": "device_lookup",
  "reasoning": "Brief explanation of why",
  "confidence": 0.95
}

Be decisive. Choose the MOST specific category that fits. Default to comprehensive only if truly ambiguous.
"""


class QueryRouter:
    """Fast LLM router that classifies queries and determines required tools."""

    def __init__(self, model: str = None, provider: str = "fireworks"):
        """
        Initialize the query router with a fast LLM.

        Args:
            model: Model for classification (defaults to provider's default from LLMFactory)
            provider: LLM provider (default: fireworks)
        """
        self.llm = LLMFactory.create(
            provider=provider,
            model=model,  # None means use LLMFactory.PROVIDER_DEFAULTS
            temperature=0,  # Deterministic classification
        )

    def route(self, query: str) -> list[str]:
        """
        Route a query to the appropriate tool set.

        Args:
            query: User's question

        Returns:
            List of tool names needed to answer the query
        """
        messages = [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(content=f"Query: {query}")
        ]

        response = self.llm.invoke(messages)

        try:
            # Parse JSON response
            result = json.loads(response.content)
            category = result.get("category", "comprehensive")

            # Get tools for this category
            tools = TOOL_SETS.get(category, TOOL_SETS["comprehensive"])

            return tools

        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.warning("Router parsing error: %s. Defaulting to comprehensive tools.", e)
            return TOOL_SETS["comprehensive"]

    async def route_async(self, query: str) -> list[str]:
        """Async version of route()."""
        messages = [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(content=f"Query: {query}")
        ]

        response = await self.llm.ainvoke(messages)

        try:
            result = json.loads(response.content)
            category = result.get("category", "comprehensive")
            tools = TOOL_SETS.get(category, TOOL_SETS["comprehensive"])
            return tools

        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.warning("Router parsing error: %s. Defaulting to comprehensive tools.", e)
            return TOOL_SETS["comprehensive"]

    def get_category_for_query(self, query: str) -> dict:
        """
        Get full routing information including category and reasoning.

        Returns:
            Dict with category, tools, reasoning, and confidence
        """
        messages = [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(content=f"Query: {query}")
        ]

        response = self.llm.invoke(messages)

        try:
            result = json.loads(response.content)
            category = result.get("category", "comprehensive")

            return {
                "category": category,
                "tools": TOOL_SETS.get(category, TOOL_SETS["comprehensive"]),
                "reasoning": result.get("reasoning", ""),
                "confidence": result.get("confidence", 0.5),
            }

        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            return {
                "category": "comprehensive",
                "tools": TOOL_SETS["comprehensive"],
                "reasoning": f"Parsing error: {e}",
                "confidence": 0.0,
            }
