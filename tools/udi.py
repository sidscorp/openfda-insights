"""
UDI/GUDID endpoint tool (udi_search).

Searches Unique Device Identifier (UDI) records from GUDID.
Fields: device_identifier (DI), brand_name, version_model, company_name, gmdn_terms.
"""
import argparse
import json
import sys
from typing import Optional

from pydantic import BaseModel, Field

from tools.base import OpenFDAClient, OpenFDAResponse


class UDISearchParams(BaseModel):
    """Parameters for UDI/GUDID search."""

    device_identifier: Optional[str] = Field(None, description="Device Identifier (DI)")
    brand_name: Optional[str] = Field(None, description="Device brand/trade name")
    version_model: Optional[str] = Field(None, description="Device version/model number")
    company_name: Optional[str] = Field(None, description="Company/manufacturer name")
    product_code: Optional[str] = Field(None, description="3-letter device product code")
    gmdn_term: Optional[str] = Field(None, description="GMDN preferred term")
    limit: int = Field(100, ge=1, le=1000, description="Max results (1-1000)")
    skip: int = Field(0, ge=0, description="Pagination offset")


def udi_search(params: UDISearchParams, api_key: Optional[str] = None) -> OpenFDAResponse:
    """
    Search UDI/GUDID device identifier records.

    Example:
        >>> params = UDISearchParams(brand_name="Pacemaker", company_name="Medtronic")
        >>> result = udi_search(params)
        >>> print(result.results[0]["identifiers"][0]["id"])

    Args:
        params: Typed UDI search parameters
        api_key: Optional openFDA API key

    Returns:
        OpenFDAResponse with UDI records
    """
    client = OpenFDAClient(api_key=api_key)

    filters = []
    if params.device_identifier:
        filters.append(f"identifiers.id:{params.device_identifier}")
    if params.brand_name:
        filters.append(f'brand_name:"{params.brand_name}"')
    if params.version_model:
        filters.append(f'version_or_model_number:"{params.version_model}"')
    if params.company_name:
        filters.append(f'company_name:"{params.company_name}"')
    if params.product_code:
        filters.append(f"product_codes.code:{params.product_code}")
    if params.gmdn_term:
        filters.append(f'gmdn_terms.name:"{params.gmdn_term}"')

    search_query = " AND ".join(filters) if filters else None

    return client.query(
        endpoint="udi",
        search=search_query,
        limit=params.limit,
        skip=params.skip,
    )


def main():
    """CLI for udi_search tool."""
    parser = argparse.ArgumentParser(
        description="Search UDI/GUDID device identifier records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.udi --brand-name "Pacemaker"
  python -m tools.udi --company-name Medtronic --product-code LWP
        """,
    )
    parser.add_argument("--device-identifier", help="Device Identifier (DI)")
    parser.add_argument("--brand-name", help="Device brand/trade name")
    parser.add_argument("--version-model", help="Device version/model number")
    parser.add_argument("--company-name", help="Company/manufacturer name")
    parser.add_argument("--product-code", help="3-letter device product code")
    parser.add_argument("--gmdn-term", help="GMDN preferred term")
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--skip", type=int, default=0, help="Pagination offset (default: 0)")
    parser.add_argument("--api-key", help="openFDA API key")
    parser.add_argument("--config", help="Path to config file (unused, reserved)")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )

    args = parser.parse_args()

    params = UDISearchParams(
        device_identifier=args.device_identifier,
        brand_name=args.brand_name,
        version_model=args.version_model,
        company_name=args.company_name,
        product_code=args.product_code,
        gmdn_term=args.gmdn_term,
        limit=args.limit,
        skip=args.skip,
    )

    result = udi_search(params, api_key=args.api_key)

    if result.error:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
