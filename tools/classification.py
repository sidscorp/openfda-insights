"""
Classification endpoint tool (classify).

Maps product codes to device class, regulation, panel, and definition.
Primary use: resolve product_code → class (I/II/III), CFR, medical specialty.
"""
import argparse
import json
import sys
from typing import Optional

from pydantic import BaseModel, Field

from tools.base import OpenFDAClient, OpenFDAResponse


class ClassifyParams(BaseModel):
    """Parameters for device classification lookup."""

    product_code: Optional[str] = Field(None, description="3-letter device product code")
    device_name: Optional[str] = Field(None, description="Device name (partial match)")
    device_class: Optional[str] = Field(None, description="Device class: 1, 2, or 3")
    regulation_number: Optional[str] = Field(None, description="CFR regulation number (e.g., 880.5100)")
    medical_specialty: Optional[str] = Field(None, description="Medical specialty panel")
    limit: int = Field(100, ge=1, le=1000, description="Max results (1-1000)")
    skip: int = Field(0, ge=0, description="Pagination offset")


def classify(params: ClassifyParams, api_key: Optional[str] = None) -> OpenFDAResponse:
    """
    Look up device classification by product code or other attributes.

    Example:
        >>> params = ClassifyParams(product_code="LZG")
        >>> result = classify(params)
        >>> print(result.results[0]["device_class"])

    Args:
        params: Typed classification parameters
        api_key: Optional openFDA API key

    Returns:
        OpenFDAResponse with classification records
    """
    client = OpenFDAClient(api_key=api_key)

    filters = []
    if params.product_code:
        filters.append(f"product_code:{params.product_code}")
    if params.device_name:
        # Use partial matching for category searches (without quotes)
        # This allows matching "orthopedic" or "implant" within device names
        if " " in params.device_name or any(term in params.device_name.lower() for term in ["orthopedic", "implant", "cardiac", "surgical"]):
            # For multi-word or category terms, use partial matching
            filters.append(f'device_name:{params.device_name}')
        else:
            # For single specific terms, use exact matching
            filters.append(f'device_name:"{params.device_name}"')
    if params.device_class:
        filters.append(f"device_class:{params.device_class}")
    if params.regulation_number:
        filters.append(f"regulation_number:{params.regulation_number}")
    if params.medical_specialty:
        filters.append(f'medical_specialty_description:"{params.medical_specialty}"')

    search_query = " AND ".join(filters) if filters else None

    return client.query(
        endpoint="classification",
        search=search_query,
        limit=params.limit,
        skip=params.skip,
    )


def main():
    """CLI for classify tool."""
    parser = argparse.ArgumentParser(
        description="Look up FDA device classification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.classification --product-code LZG
  python -m tools.classification --device-class 2 --medical-specialty "Cardiovascular"
        """,
    )
    parser.add_argument("--product-code", help="3-letter device product code")
    parser.add_argument("--device-name", help="Device name (partial match)")
    parser.add_argument("--device-class", choices=["1", "2", "3"], help="Device class")
    parser.add_argument("--regulation-number", help="CFR regulation number (e.g., 880.5100)")
    parser.add_argument("--medical-specialty", help="Medical specialty panel")
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--skip", type=int, default=0, help="Pagination offset (default: 0)")
    parser.add_argument("--api-key", help="openFDA API key")
    parser.add_argument("--config", help="Path to config file (unused, reserved)")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )

    args = parser.parse_args()

    params = ClassifyParams(
        product_code=args.product_code,
        device_name=args.device_name,
        device_class=args.device_class,
        regulation_number=args.regulation_number,
        medical_specialty=args.medical_specialty,
        limit=args.limit,
        skip=args.skip,
    )

    result = classify(params, api_key=args.api_key)

    if result.error:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
