"""
PMA (Premarket Approval) endpoint tool (pma_search).

Searches premarket approval records and supplements.
Fields: pma_number, supplement_number, applicant, product_code, decision_date, trade_name.
"""
import argparse
import json
import sys
from typing import Optional

from pydantic import BaseModel, Field

from tools.base import OpenFDAClient, OpenFDAResponse


class PMASearchParams(BaseModel):
    """Parameters for PMA search."""

    pma_number: Optional[str] = Field(None, description="PMA number (e.g., P123456)")
    supplement_number: Optional[str] = Field(None, description="Supplement number (e.g., S001)")
    applicant: Optional[str] = Field(None, description="Applicant/sponsor name")
    trade_name: Optional[str] = Field(None, description="Device trade name")
    product_code: Optional[str] = Field(None, description="3-letter device product code")
    decision_date_start: Optional[str] = Field(None, description="Decision date start (YYYYMMDD)")
    decision_date_end: Optional[str] = Field(None, description="Decision date end (YYYYMMDD)")
    limit: int = Field(100, ge=1, le=1000, description="Max results (1-1000)")
    skip: int = Field(0, ge=0, description="Pagination offset")


def pma_search(params: PMASearchParams, api_key: Optional[str] = None) -> OpenFDAResponse:
    """
    Search PMA (Premarket Approval) records.

    Example:
        >>> params = PMASearchParams(pma_number="P123456")
        >>> result = pma_search(params)
        >>> print(result.results[0]["decision_date"])

    Args:
        params: Typed PMA search parameters
        api_key: Optional openFDA API key

    Returns:
        OpenFDAResponse with PMA records
    """
    client = OpenFDAClient(api_key=api_key)

    filters = []
    if params.pma_number:
        filters.append(f"pma_number:{params.pma_number}")
    if params.supplement_number:
        filters.append(f"supplement_number:{params.supplement_number}")
    if params.applicant:
        filters.append(f'applicant:"{params.applicant}"')
    if params.trade_name:
        filters.append(f'trade_name:"{params.trade_name}"')
    if params.product_code:
        filters.append(f"product_code:{params.product_code}")
    if params.decision_date_start and params.decision_date_end:
        filters.append(
            f"decision_date:[{params.decision_date_start} TO {params.decision_date_end}]"
        )

    search_query = " AND ".join(filters) if filters else None

    return client.query(
        endpoint="pma",
        search=search_query,
        limit=params.limit,
        skip=params.skip,
    )


def main():
    """CLI for pma_search tool."""
    parser = argparse.ArgumentParser(
        description="Search FDA PMA (Premarket Approval) records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.pma --pma-number P123456
  python -m tools.pma --applicant "Abbott" --decision-date-start 20200101
        """,
    )
    parser.add_argument("--pma-number", help="PMA number (e.g., P123456)")
    parser.add_argument("--supplement-number", help="Supplement number (e.g., S001)")
    parser.add_argument("--applicant", help="Applicant/sponsor name")
    parser.add_argument("--trade-name", help="Device trade name")
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

    params = PMASearchParams(
        pma_number=args.pma_number,
        supplement_number=args.supplement_number,
        applicant=args.applicant,
        trade_name=args.trade_name,
        product_code=args.product_code,
        decision_date_start=args.decision_date_start,
        decision_date_end=args.decision_date_end,
        limit=args.limit,
        skip=args.skip,
    )

    result = pma_search(params, api_key=args.api_key)

    if result.error:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
