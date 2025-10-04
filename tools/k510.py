"""
510(k) clearance endpoint tool (k510_search).

Searches premarket notification (510(k)) clearances.
Fields: k_number, applicant, device_name, product_code, decision_date, clearance statement.
"""
import argparse
import json
import sys
from typing import Optional

from pydantic import BaseModel, Field

from tools.base import OpenFDAClient, OpenFDAResponse


class K510SearchParams(BaseModel):
    """Parameters for 510(k) search."""

    k_number: Optional[str] = Field(None, description="510(k) number (e.g., K123456)")
    applicant: Optional[str] = Field(None, description="Applicant/sponsor name")
    device_name: Optional[str] = Field(None, description="Device trade name")
    product_code: Optional[str] = Field(None, description="3-letter device product code")
    decision_date_start: Optional[str] = Field(None, description="Decision date start (YYYYMMDD)")
    decision_date_end: Optional[str] = Field(None, description="Decision date end (YYYYMMDD)")
    limit: int = Field(100, ge=1, le=1000, description="Max results (1-1000)")
    skip: int = Field(0, ge=0, description="Pagination offset")


def k510_search(params: K510SearchParams, api_key: Optional[str] = None) -> OpenFDAResponse:
    """
    Search 510(k) clearances.

    Example:
        >>> params = K510SearchParams(applicant="Medtronic", decision_date_start="20200101")
        >>> result = k510_search(params)
        >>> print(len(result.results))

    Args:
        params: Typed 510(k) search parameters
        api_key: Optional openFDA API key

    Returns:
        OpenFDAResponse with 510(k) records
    """
    client = OpenFDAClient(api_key=api_key)

    filters = []
    if params.k_number:
        filters.append(f"k_number:{params.k_number}")
    if params.applicant:
        filters.append(f'applicant:"{params.applicant}"')
    if params.device_name:
        filters.append(f'device_name:"{params.device_name}"')
    if params.product_code:
        filters.append(f"product_code:{params.product_code}")
    if params.decision_date_start and params.decision_date_end:
        filters.append(
            f"decision_date:[{params.decision_date_start} TO {params.decision_date_end}]"
        )

    search_query = " AND ".join(filters) if filters else None

    return client.query(
        endpoint="510k",
        search=search_query,
        limit=params.limit,
        skip=params.skip,
    )


def main():
    """CLI for k510_search tool."""
    parser = argparse.ArgumentParser(
        description="Search FDA 510(k) clearances",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.k510 --k-number K123456
  python -m tools.k510 --applicant Medtronic --decision-date-start 20200101
        """,
    )
    parser.add_argument("--k-number", help="510(k) number (e.g., K123456)")
    parser.add_argument("--applicant", help="Applicant/sponsor name")
    parser.add_argument("--device-name", help="Device trade name")
    parser.add_argument("--product-code", help="3-letter device product code")
    parser.add_argument("--decision-date-start", help="Decision date start (YYYYMMDD)")
    parser.add_argument("--decision-date-end", help="Decision date end (YYYYMMDD)")
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--skip", type=int, default=0, help="Pagination offset (default: 0)")
    parser.add_argument("--api-key", help="openFDA API key")
    parser.add_argument("--config", help="Path to config file (unused, reserved)")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )

    args = parser.parse_args()

    params = K510SearchParams(
        k_number=args.k_number,
        applicant=args.applicant,
        device_name=args.device_name,
        product_code=args.product_code,
        decision_date_start=args.decision_date_start,
        decision_date_end=args.decision_date_end,
        limit=args.limit,
        skip=args.skip,
    )

    result = k510_search(params, api_key=args.api_key)

    if result.error:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
