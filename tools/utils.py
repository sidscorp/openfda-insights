"""
Agent utility tools: probe_count, paginate, field_explorer, freshness, answer_assessor.

Rationale: Prevent the agent from guessing field names, enable fast disambiguation via count,
enforce pagination caps, and verify answer sufficiency deterministically.
"""
import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from tools.base import OpenFDAClient, OpenFDAResponse


# ============================================================================
# probe_count: Fast disambiguation via count aggregation
# ============================================================================


class ProbeCountParams(BaseModel):
    """Parameters for count probe."""

    endpoint: str = Field(
        description="Endpoint name: registrationlisting, classification, 510k, pma, enforcement, event, udi"
    )
    field: str = Field(description="Field to count by (e.g., 'device_class', 'product_code')")
    search: Optional[str] = Field(None, description="Optional search filter")
    limit: int = Field(100, ge=1, le=1000, description="Max count buckets (1-1000)")


def probe_count(params: ProbeCountParams, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Perform count aggregation on a field for fast disambiguation.

    Example:
        >>> params = ProbeCountParams(endpoint="classification", field="device_class")
        >>> result = probe_count(params)
        >>> print(result["results"])

    Args:
        params: Typed count parameters
        api_key: Optional openFDA API key

    Returns:
        Dict with count buckets: {"results": [{"term": "...", "count": N}, ...]}
    """
    client = OpenFDAClient(api_key=api_key)

    resp = client.query(
        endpoint=params.endpoint,
        search=params.search,
        count=params.field,
        limit=params.limit,
    )

    if resp.error:
        return {"error": resp.error, "results": []}

    return {"results": resp.results, "meta": resp.meta}


# ============================================================================
# paginate: Safe pagination wrapper with cap enforcement
# ============================================================================


class PaginateParams(BaseModel):
    """Parameters for safe pagination."""

    endpoint: str = Field(
        description="Endpoint name: registrationlisting, classification, 510k, pma, enforcement, event, udi"
    )
    search: Optional[str] = Field(None, description="Lucene search query")
    max_records: int = Field(1000, ge=1, le=5000, description="Total records cap (1-5000)")
    page_size: int = Field(100, ge=1, le=1000, description="Records per page (1-1000)")


def paginate(params: PaginateParams, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch up to max_records results across multiple pages.

    Example:
        >>> params = PaginateParams(endpoint="510k", search="applicant:Medtronic", max_records=500)
        >>> results = paginate(params)
        >>> print(len(results))

    Args:
        params: Typed pagination parameters
        api_key: Optional openFDA API key

    Returns:
        List of all fetched records (up to max_records)
    """
    client = OpenFDAClient(api_key=api_key)
    all_results = []
    skip = 0

    while len(all_results) < params.max_records:
        batch_size = min(params.page_size, params.max_records - len(all_results))
        resp = client.query(
            endpoint=params.endpoint,
            search=params.search,
            limit=batch_size,
            skip=skip,
        )

        if resp.error or not resp.results:
            break

        all_results.extend(resp.results)
        skip += batch_size

        # Stop if we got fewer results than requested (end of data)
        if len(resp.results) < batch_size:
            break

    return all_results


# ============================================================================
# field_explorer: Return searchable field names per endpoint
# ============================================================================

# Cached field mappings (derived from openFDA docs)
ENDPOINT_FIELDS = {
    "registrationlisting": [
        "proprietary_name",
        "establishment_type",
        "registration.fei_number",
        "registration.address.city",
        "registration.address.state_code",
        "registration.address.iso_country_code",
        "registration.registration_date",
        "products.product_code",
        "products.created_date",
    ],
    "classification": [
        "product_code",
        "device_name",
        "device_class",
        "regulation_number",
        "medical_specialty_description",
        "definition",
    ],
    "510k": [
        "k_number",
        "applicant",
        "device_name",
        "product_code",
        "decision_date",
        "clearance_type",
        "decision_description",
    ],
    "pma": [
        "pma_number",
        "supplement_number",
        "applicant",
        "trade_name",
        "product_code",
        "decision_date",
        "advisory_committee",
    ],
    "enforcement": [
        "recall_number",
        "classification",
        "product_description",
        "recalling_firm",
        "product_code",
        "event_date_initiated",
        "reason_for_recall",
    ],
    "event": [
        "report_number",
        "event_type",
        "date_received",
        "device.generic_name",
        "device.brand_name",
        "device.openfda.device_class",
        "patient.sequence_number_outcome",
    ],
    "udi": [
        "identifiers.id",
        "brand_name",
        "version_or_model_number",
        "company_name",
        "product_codes.code",
        "gmdn_terms.name",
    ],
}


def field_explorer(endpoint: str) -> List[str]:
    """
    Return searchable field names for a given endpoint.

    Example:
        >>> fields = field_explorer("classification")
        >>> print(fields)

    Args:
        endpoint: Endpoint name

    Returns:
        List of searchable field names
    """
    return ENDPOINT_FIELDS.get(endpoint, [])


# ============================================================================
# freshness: Return metadata URL for last-updated info
# ============================================================================


def freshness(endpoint: str) -> str:
    """
    Return the metadata URL for an endpoint's last-updated timestamp.

    Example:
        >>> url = freshness("510k")
        >>> print(url)

    Args:
        endpoint: Endpoint name

    Returns:
        URL to metadata page
    """
    base = "https://api.fda.gov/device"
    return f"{base}/{endpoint}.json?limit=1"


# ============================================================================
# answer_assessor: Deterministic checks for answer sufficiency
# ============================================================================


class AnswerAssessorParams(BaseModel):
    """Parameters for answer assessment."""

    question: str = Field(description="Original user question")
    search_query: Optional[str] = Field(None, description="Search query used")
    result_count: int = Field(description="Number of results returned")
    date_filter_present: bool = Field(
        False, description="True if date range filter was applied"
    )
    class_filter_present: bool = Field(
        False, description="True if device/recall class filter was applied"
    )


class AnswerAssessment(BaseModel):
    """Assessment result."""

    sufficient: bool = Field(description="True if answer meets requirements")
    reason: str = Field(description="Explanation of assessment")


def answer_assessor(params: AnswerAssessorParams) -> AnswerAssessment:
    """
    Deterministically assess if query results satisfy the question.

    Rules:
    1. If question mentions time period (e.g., "since 2023"), date_filter_present must be True
    2. If question mentions class (e.g., "Class I"), class_filter_present must be True
    3. result_count must be > 0 for data questions (not for "how many" questions)
    4. If no results and filters were applied, still sufficient (legitimate empty result)

    Example:
        >>> params = AnswerAssessorParams(
        ...     question="How many Class I recalls since 2023?",
        ...     search_query="classification:'Class I' AND event_date_initiated:[20230101 TO 20251231]",
        ...     result_count=42,
        ...     date_filter_present=True,
        ...     class_filter_present=True
        ... )
        >>> assessment = answer_assessor(params)
        >>> print(assessment.sufficient)

    Args:
        params: Typed assessment parameters

    Returns:
        AnswerAssessment with sufficiency determination
    """
    q_lower = params.question.lower()

    # Check for time constraints
    time_keywords = ["since", "after", "before", "in 2023", "in 2024", "recent", "last year"]
    needs_date_filter = any(kw in q_lower for kw in time_keywords)
    if needs_date_filter and not params.date_filter_present:
        return AnswerAssessment(
            sufficient=False,
            reason="Question mentions time period but no date filter was applied",
        )

    # Check for class constraints
    class_keywords = ["class i", "class ii", "class iii", "class 1", "class 2", "class 3"]
    needs_class_filter = any(kw in q_lower for kw in class_keywords)
    if needs_class_filter and not params.class_filter_present:
        return AnswerAssessment(
            sufficient=False,
            reason="Question mentions device/recall class but no class filter was applied",
        )

    # Check result count (allow zero if filters were properly applied)
    is_count_question = any(kw in q_lower for kw in ["how many", "count", "number of"])
    if params.result_count == 0 and not is_count_question:
        if params.search_query:
            # Legitimate empty result with filters
            return AnswerAssessment(
                sufficient=True,
                reason="No results found, but filters were correctly applied",
            )
        else:
            return AnswerAssessment(
                sufficient=False,
                reason="No results and no filters applied",
            )

    return AnswerAssessment(sufficient=True, reason="All requirements met")


# ============================================================================
# CLI entry points
# ============================================================================


def main():
    """CLI dispatcher for utility tools."""
    parser = argparse.ArgumentParser(
        description="Agent utility tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["probe_count", "paginate", "field_explorer", "freshness", "answer_assessor"],
        help="Utility command to run",
    )
    parser.add_argument("--endpoint", help="Endpoint name")
    parser.add_argument("--field", help="Field name (for probe_count)")
    parser.add_argument("--search", help="Search query")
    parser.add_argument("--limit", type=int, default=100, help="Limit")
    parser.add_argument("--max-records", type=int, default=1000, help="Max records (for paginate)")
    parser.add_argument("--page-size", type=int, default=100, help="Page size (for paginate)")
    parser.add_argument("--question", help="Question (for answer_assessor)")
    parser.add_argument("--result-count", type=int, default=0, help="Result count")
    parser.add_argument("--date-filter-present", action="store_true")
    parser.add_argument("--class-filter-present", action="store_true")
    parser.add_argument("--api-key", help="openFDA API key")
    parser.add_argument("--config", help="Path to config file (unused, reserved)")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )

    args = parser.parse_args()

    if args.command == "probe_count":
        if not args.endpoint or not args.field:
            print("Error: --endpoint and --field required for probe_count", file=sys.stderr)
            sys.exit(1)
        params = ProbeCountParams(
            endpoint=args.endpoint, field=args.field, search=args.search, limit=args.limit
        )
        result = probe_count(params, api_key=args.api_key)
        print(json.dumps(result, indent=2))

    elif args.command == "paginate":
        if not args.endpoint:
            print("Error: --endpoint required for paginate", file=sys.stderr)
            sys.exit(1)
        params = PaginateParams(
            endpoint=args.endpoint,
            search=args.search,
            max_records=args.max_records,
            page_size=args.page_size,
        )
        result = paginate(params, api_key=args.api_key)
        print(json.dumps(result, indent=2))

    elif args.command == "field_explorer":
        if not args.endpoint:
            print("Error: --endpoint required for field_explorer", file=sys.stderr)
            sys.exit(1)
        result = field_explorer(args.endpoint)
        print(json.dumps(result, indent=2))

    elif args.command == "freshness":
        if not args.endpoint:
            print("Error: --endpoint required for freshness", file=sys.stderr)
            sys.exit(1)
        result = freshness(args.endpoint)
        print(result)

    elif args.command == "answer_assessor":
        if not args.question:
            print("Error: --question required for answer_assessor", file=sys.stderr)
            sys.exit(1)
        params = AnswerAssessorParams(
            question=args.question,
            search_query=args.search,
            result_count=args.result_count,
            date_filter_present=args.date_filter_present,
            class_filter_present=args.class_filter_present,
        )
        result = answer_assessor(params)
        print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
