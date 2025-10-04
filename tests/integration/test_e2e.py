"""
End-to-end integration tests for FDA Agent.

Tests routing accuracy, parameter extraction, and assessor logic.
Rationale: CEO resolution #6 - minimal integration tests with dry-run mode.
"""
import os

import pytest

# Skip tests if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set - skipping integration tests",
)


@pytest.mark.parametrize(
    "question,expected_endpoint",
    [
        ("List Class II devices", "classification"),
        ("510k clearances from Medtronic since 2023", "510k"),
        ("Show PMA approvals in 2024", "pma"),
        ("Any Class I recalls for syringes", "recall"),
        ("Adverse events for pacemakers", "maude"),
        ("Find device UDI 00819320201234", "udi"),
        ("Show establishments in Minnesota", "rl_search"),
    ],
)
def test_routing_accuracy(question, expected_endpoint):
    """Test that router selects correct endpoint for various questions."""
    from agent.graph import FDAAgent

    agent = FDAAgent()
    result = agent.query(question, dry_run=False)  # Will still call API but we only check routing

    # Check that selected endpoint matches expected
    assert result["selected_endpoint"] == expected_endpoint, (
        f"Expected {expected_endpoint}, got {result['selected_endpoint']} "
        f"for question: {question}"
    )


@pytest.mark.parametrize(
    "question,expected_filter",
    [
        ("Show me Class II devices", "device_class"),
        ("Find 510k clearances since 2023", "date"),
        ("Any Class I recalls", "recall_class"),
    ],
)
def test_parameter_extraction(question, expected_filter):
    """Test that extractor properly extracts filters from questions."""
    from agent.graph import FDAAgent

    agent = FDAAgent()
    result = agent.query(question)

    extracted = result.get("extracted_params", {})

    if expected_filter == "device_class":
        assert extracted.get("device_class") is not None, f"Missing device_class for: {question}"
    elif expected_filter == "date":
        assert (
            extracted.get("date_start") or extracted.get("date_end")
        ), f"Missing date filters for: {question}"
    elif expected_filter == "recall_class":
        assert extracted.get("recall_class") is not None, f"Missing recall_class for: {question}"


def test_assessor_validates_missing_class_filter():
    """Test that assessor catches missing class filter when question mentions class."""
    from agent.extractor import ParameterExtractor, ExtractedParams, extracted_params_to_query_string
    from langchain_anthropic import ChatAnthropic
    from tools.utils import AnswerAssessorParams, answer_assessor

    # Simulate missing class filter
    llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)
    extractor = ParameterExtractor(llm)

    # Force extraction to miss the class filter (simulate error)
    question = "Show me Class I recalls"
    extracted = ExtractedParams(recall_class=None)  # Missing!

    params_str = extracted_params_to_query_string(extracted)

    assessment = answer_assessor(
        AnswerAssessorParams(
            question=question,
            search_query=params_str,
            result_count=10,
            date_filter_present=False,
            class_filter_present=False,  # Should trigger insufficient
        )
    )

    assert not assessment.sufficient, "Assessor should catch missing class filter"
    assert "class" in assessment.reason.lower(), f"Reason should mention class: {assessment.reason}"


def test_assessor_accepts_zero_results_with_filters():
    """Test that assessor accepts zero results if proper filters were applied."""
    from tools.utils import AnswerAssessorParams, answer_assessor

    assessment = answer_assessor(
        AnswerAssessorParams(
            question="Show me Class III recalls from XYZ Corp in 1999",
            search_query="recall_class:Class III AND firm_name:XYZ AND date:[19990101 TO 19991231]",
            result_count=0,
            date_filter_present=True,
            class_filter_present=True,
        )
    )

    # Should accept - filters were correctly applied, just no matches
    assert assessment.sufficient, f"Should accept zero results with filters: {assessment.reason}"
