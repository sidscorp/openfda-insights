"""
MAUDE (adverse event) endpoint tool (maude_search).

Searches device adverse event reports from MAUDE database.
Fields: report_number, device_name, brand_name, event_type, date_received, patient_problem.
"""
import argparse
import json
import sys
from typing import Optional

from pydantic import BaseModel, Field

from tools.base import OpenFDAClient, OpenFDAResponse


class MAUDESearchParams(BaseModel):
    """Parameters for MAUDE adverse event search."""

    report_number: Optional[str] = Field(None, description="Report/MDR number")
    device_name: Optional[str] = Field(None, description="Device generic name")
    brand_name: Optional[str] = Field(None, description="Device brand/trade name")
    product_code: Optional[str] = Field(None, description="3-letter device product code")
    event_type: Optional[str] = Field(
        None, description="Event type (e.g., 'Malfunction', 'Injury', 'Death')"
    )
    date_received_start: Optional[str] = Field(None, description="Date received start (YYYYMMDD)")
    date_received_end: Optional[str] = Field(None, description="Date received end (YYYYMMDD)")
    limit: int = Field(100, ge=1, le=1000, description="Max results (1-1000)")
    skip: int = Field(0, ge=0, description="Pagination offset")


def maude_search(params: MAUDESearchParams, api_key: Optional[str] = None) -> OpenFDAResponse:
    """
    Search MAUDE device adverse event reports.

    Example:
        >>> params = MAUDESearchParams(event_type="Death", date_received_start="20230101")
        >>> result = maude_search(params)
        >>> print(len(result.results))

    Args:
        params: Typed MAUDE search parameters
        api_key: Optional openFDA API key

    Returns:
        OpenFDAResponse with adverse event records
    """
    client = OpenFDAClient(api_key=api_key)

    filters = []
    if params.report_number:
        filters.append(f"report_number:{params.report_number}")
    if params.device_name:
        filters.append(f'device.generic_name:"{params.device_name}"')
    if params.brand_name:
        filters.append(f'device.brand_name:"{params.brand_name}"')
    if params.product_code:
        filters.append(f"device.openfda.device_class:{params.product_code}")
    if params.event_type:
        filters.append(f'event_type:"{params.event_type}"')
    if params.date_received_start and params.date_received_end:
        filters.append(
            f"date_received:[{params.date_received_start} TO {params.date_received_end}]"
        )

    search_query = " AND ".join(filters) if filters else None

    return client.query(
        endpoint="event",
        search=search_query,
        limit=params.limit,
        skip=params.skip,
    )


def main():
    """CLI for maude_search tool."""
    parser = argparse.ArgumentParser(
        description="Search MAUDE device adverse event reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.maude --event-type Death --date-received-start 20230101
  python -m tools.maude --brand-name "Pacemaker" --product-code LWP
        """,
    )
    parser.add_argument("--report-number", help="Report/MDR number")
    parser.add_argument("--device-name", help="Device generic name")
    parser.add_argument("--brand-name", help="Device brand/trade name")
    parser.add_argument("--product-code", help="3-letter device product code")
    parser.add_argument("--event-type", help="Event type (e.g., Malfunction, Injury, Death)")
    parser.add_argument("--date-received-start", help="Date received start (YYYYMMDD)")
    parser.add_argument("--date-received-end", help="Date received end (YYYYMMDD)")
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--skip", type=int, default=0, help="Pagination offset (default: 0)")
    parser.add_argument("--api-key", help="openFDA API key")
    parser.add_argument("--config", help="Path to config file (unused, reserved)")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )

    args = parser.parse_args()

    params = MAUDESearchParams(
        report_number=args.report_number,
        device_name=args.device_name,
        brand_name=args.brand_name,
        product_code=args.product_code,
        event_type=args.event_type,
        date_received_start=args.date_received_start,
        date_received_end=args.date_received_end,
        limit=args.limit,
        skip=args.skip,
    )

    result = maude_search(params, api_key=args.api_key)

    if result.error:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
