"""
Tests for agent routing accuracy.

PRD requirement (Phase 3, line 125): Routing accuracy ≥ 0.9
"""
import os

import pytest

# Skip tests if no Anthropic API key
pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set"
)

# Test questions with expected tool routing
ROUTING_TEST_CASES = [
    {
        "question": "Show me Class II devices",
        "expected_tool": "classify",
        "category": "classification",
    },
    {
        "question": "Find 510k clearances from 2023",
        "expected_tool": "k510_search",
        "category": "510k",
    },
    {
        "question": "What PMA approvals happened last year?",
        "expected_tool": "pma_search",
        "category": "pma",
    },
    {
        "question": "Show me Class I recalls since 2023",
        "expected_tool": "recall_search",
        "category": "enforcement",
    },
    {
        "question": "Find adverse events for pacemakers",
        "expected_tool": "maude_search",
        "category": "event",
    },
    {
        "question": "Search for UDI with brand name Medtronic",
        "expected_tool": "udi_search",
        "category": "udi",
    },
    {
        "question": "Find establishments in California",
        "expected_tool": "rl_search",
        "category": "registrationlisting",
    },
    {
        "question": "How many Class II devices are there?",
        "expected_tool": "probe_count",
        "category": "classification",
    },
]


@pytest.fixture(scope="module")
def agent():
    """Initialize agent once for all tests."""
    from agent.graph import FDAAgent

    return FDAAgent()


def test_agent_initialization(agent):
    """Test that agent initializes successfully."""
    assert agent.llm is not None
    assert agent.retriever is not None
    assert agent.graph is not None


@pytest.mark.parametrize("test_case", ROUTING_TEST_CASES)
def test_routing_accuracy(agent, test_case):
    """
    Test that router selects correct tool for each question.

    Note: This test may take time and cost $ due to LLM calls.
    """
    # Create initial state
    from agent.state import AgentState

    initial_state = AgentState(question=test_case["question"])

    # Run router node only
    routed_state = agent._router_node(initial_state)

    # Check if expected tool was selected
    assert (
        len(routed_state.selected_tools) > 0
    ), f"No tools selected for: {test_case['question']}"

    selected = routed_state.selected_tools[0]
    assert (
        test_case["expected_tool"] in selected or selected in test_case["expected_tool"]
    ), f"Expected '{test_case['expected_tool']}' but got '{selected}' for: {test_case['question']}"


@pytest.mark.slow
def test_routing_aggregate_accuracy(agent):
    """
    Aggregate routing test: ≥90% of questions should route correctly.

    PRD requirement: routing accuracy ≥ 0.9
    """
    from agent.state import AgentState

    correct = 0
    total = len(ROUTING_TEST_CASES)

    for test_case in ROUTING_TEST_CASES:
        initial_state = AgentState(question=test_case["question"])
        routed_state = agent._router_node(initial_state)

        if routed_state.selected_tools:
            selected = routed_state.selected_tools[0]
            if (
                test_case["expected_tool"] in selected
                or selected in test_case["expected_tool"]
            ):
                correct += 1

    accuracy = correct / total
    assert accuracy >= 0.9, f"Routing accuracy {accuracy:.2%} below threshold 90% ({correct}/{total})"


@pytest.mark.slow
def test_end_to_end_query(agent):
    """Test full agent execution on a simple question."""
    result = agent.query("Show me 5 Class II devices")

    # Should return results
    assert result["answer"]
    assert "provenance" in result
    assert result["provenance"]["endpoint"]

    # Should have made tool calls
    assert len(result["tool_calls"]) > 0
