"""
Registration & Listing endpoint tool (rl_search).

Searches FDA establishment registrations and device listings.
Fields: firm name, FEI, city, state, country, product codes, registration dates.
"""
import argparse
import json
import sys
from typing import Optional

from pydantic import BaseModel, Field

from tools.base import OpenFDAClient, OpenFDAResponse


class RLSearchParams(BaseModel):
    """Parameters for Registration & Listing search."""

    firm_name: Optional[str] = Field(None, description="Firm/establishment name (partial match)")
    fei_number: Optional[str] = Field(None, description="Facility Establishment Identifier")
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, description="US state code (e.g., 'CA')")
    country: Optional[str] = Field(None, description="Country code (e.g., 'US')")
    product_code: Optional[str] = Field(None, description="3-letter device product code")
    registration_date_start: Optional[str] = Field(
        None, description="Registration date range start (YYYYMMDD)"
    )
    registration_date_end: Optional[str] = Field(
        None, description="Registration date range end (YYYYMMDD)"
    )
    limit: int = Field(100, ge=1, le=1000, description="Max results (1-1000)")
    skip: int = Field(0, ge=0, description="Pagination offset")


def rl_search(params: RLSearchParams, api_key: Optional[str] = None) -> OpenFDAResponse:
    """
    Search FDA device registrations and listings.

    Example:
        >>> params = RLSearchParams(firm_name="Medtronic", state="CA", limit=10)
        >>> result = rl_search(params)
        >>> print(result.meta["results"]["total"])

    Args:
        params: Typed search parameters
        api_key: Optional openFDA API key

    Returns:
        OpenFDAResponse with establishments/devices
    """
    client = OpenFDAClient(api_key=api_key)

    # Build Lucene query
    filters = []
    if params.firm_name:
        filters.append(f'proprietary_name:"{params.firm_name}"')
    if params.fei_number:
        filters.append(f"registration.fei_number:{params.fei_number}")
    if params.city:
        filters.append(f'registration.address.city:"{params.city}"')
    if params.state:
        filters.append(f"registration.address.state_code:{params.state}")
    if params.country:
        filters.append(f"registration.address.iso_country_code:{params.country}")
    if params.product_code:
        filters.append(f"products.product_code:{params.product_code}")
    if params.registration_date_start and params.registration_date_end:
        filters.append(
            f"registration.registration_date:[{params.registration_date_start} TO {params.registration_date_end}]"
        )

    search_query = " AND ".join(filters) if filters else None

    return client.query(
        endpoint="registrationlisting",
        search=search_query,
        limit=params.limit,
        skip=params.skip,
    )


def main():
    """CLI for rl_search tool."""
    parser = argparse.ArgumentParser(
        description="Search FDA device registrations and listings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.registration_listing --firm-name Medtronic --limit 5
  python -m tools.registration_listing --state CA --product-code LZG
        """,
    )
    parser.add_argument("--firm-name", help="Firm/establishment name")
    parser.add_argument("--fei-number", help="Facility Establishment Identifier")
    parser.add_argument("--city", help="City name")
    parser.add_argument("--state", help="US state code (e.g., CA)")
    parser.add_argument("--country", help="Country code (e.g., US)")
    parser.add_argument("--product-code", help="3-letter device product code")
    parser.add_argument("--registration-date-start", help="Start date (YYYYMMDD)")
    parser.add_argument("--registration-date-end", help="End date (YYYYMMDD)")
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--skip", type=int, default=0, help="Pagination offset (default: 0)")
    parser.add_argument("--api-key", help="openFDA API key")
    parser.add_argument("--config", help="Path to config file (unused, reserved)")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )

    args = parser.parse_args()

    params = RLSearchParams(
        firm_name=args.firm_name,
        fei_number=args.fei_number,
        city=args.city,
        state=args.state,
        country=args.country,
        product_code=args.product_code,
        registration_date_start=args.registration_date_start,
        registration_date_end=args.registration_date_end,
        limit=args.limit,
        skip=args.skip,
    )

    result = rl_search(params, api_key=args.api_key)

    if result.error:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
