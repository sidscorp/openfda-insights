"""
Enforcement (recalls) endpoint tool (recall_search).

Searches device enforcement reports (recalls).
Fields: recall_number, classification (I/II/III), product_description, firm_name, event_date_initiated.
"""
import argparse
import json
import sys
from typing import Optional

from pydantic import BaseModel, Field

from tools.base import OpenFDAClient, OpenFDAResponse


class RecallSearchParams(BaseModel):
    """Parameters for enforcement/recall search."""

    recall_number: Optional[str] = Field(None, description="Recall number")
    classification: Optional[str] = Field(
        None, description="Recall classification: 'Class I', 'Class II', or 'Class III'"
    )
    product_description: Optional[str] = Field(None, description="Product description (partial)")
    firm_name: Optional[str] = Field(None, description="Recalling firm name")
    product_code: Optional[str] = Field(None, description="3-letter device product code")
    event_date_start: Optional[str] = Field(None, description="Event initiation date start (YYYYMMDD)")
    event_date_end: Optional[str] = Field(None, description="Event initiation date end (YYYYMMDD)")
    limit: int = Field(100, ge=1, le=1000, description="Max results (1-1000)")
    skip: int = Field(0, ge=0, description="Pagination offset")


def recall_search(params: RecallSearchParams, api_key: Optional[str] = None) -> OpenFDAResponse:
    """
    Search device recall enforcement reports.

    Example:
        >>> params = RecallSearchParams(classification="Class I", event_date_start="20230101")
        >>> result = recall_search(params)
        >>> print(result.meta["results"]["total"])

    Args:
        params: Typed recall search parameters
        api_key: Optional openFDA API key

    Returns:
        OpenFDAResponse with recall records
    """
    client = OpenFDAClient(api_key=api_key)

    filters = []
    if params.recall_number:
        filters.append(f"recall_number:{params.recall_number}")
    if params.classification:
        filters.append(f'classification:"{params.classification}"')
    if params.product_description:
        filters.append(f'product_description:"{params.product_description}"')
    if params.firm_name:
        filters.append(f'recalling_firm:"{params.firm_name}"')
    if params.product_code:
        filters.append(f"product_code:{params.product_code}")
    if params.event_date_start and params.event_date_end:
        filters.append(
            f"recall_initiation_date:[{params.event_date_start} TO {params.event_date_end}]"
        )

    search_query = " AND ".join(filters) if filters else None

    return client.query(
        endpoint="enforcement",
        search=search_query,
        limit=params.limit,
        skip=params.skip,
    )


def main():
    """CLI for recall_search tool."""
    parser = argparse.ArgumentParser(
        description="Search FDA device recall enforcement reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.recall --classification "Class I" --event-date-start 20230101
  python -m tools.recall --firm-name Medtronic --product-code LZG
        """,
    )
    parser.add_argument("--recall-number", help="Recall number")
    parser.add_argument(
        "--classification",
        choices=["Class I", "Class II", "Class III"],
        help="Recall classification",
    )
    parser.add_argument("--product-description", help="Product description (partial)")
    parser.add_argument("--firm-name", help="Recalling firm name")
    parser.add_argument("--product-code", help="3-letter device product code")
    parser.add_argument("--event-date-start", help="Event initiation date start (YYYYMMDD)")
    parser.add_argument("--event-date-end", help="Event initiation date end (YYYYMMDD)")
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--skip", type=int, default=0, help="Pagination offset (default: 0)")
    parser.add_argument("--api-key", help="openFDA API key")
    parser.add_argument("--config", help="Path to config file (unused, reserved)")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )

    args = parser.parse_args()

    params = RecallSearchParams(
        recall_number=args.recall_number,
        classification=args.classification,
        product_description=args.product_description,
        firm_name=args.firm_name,
        product_code=args.product_code,
        event_date_start=args.event_date_start,
        event_date_end=args.event_date_end,
        limit=args.limit,
        skip=args.skip,
    )

    result = recall_search(params, api_key=args.api_key)

    if result.error:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
