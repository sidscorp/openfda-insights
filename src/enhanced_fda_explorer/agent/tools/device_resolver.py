"""
Device Resolver Tool - GUDID database lookup for device identification.
"""
from typing import Type, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import json

from ...tools.device_resolver import DeviceResolver
from ...config import get_config


class DeviceResolverInput(BaseModel):
    query: str = Field(description="Device name, brand, company, or product code to search for")
    limit: int = Field(default=100, description="Maximum number of results to return")


class DeviceResolverTool(BaseTool):
    name: str = "resolve_device"
    description: str = """Look up medical devices in the GUDID database by name, brand, company, or product code.
    Returns product codes, GMDN terms, manufacturer info, and device identifiers.
    Use this FIRST to identify devices and get FDA product codes before searching other databases."""
    args_schema: Type[BaseModel] = DeviceResolverInput

    _db_path: str = ""
    _resolver: Optional[DeviceResolver] = None

    def __init__(self, db_path: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        config = get_config()
        self._db_path = db_path or config.gudid_db_path
        self._resolver = DeviceResolver(self._db_path)

    def _run(self, query: str, limit: int = 100) -> str:
        try:
            if isinstance(query, str) and query.startswith('{'):
                params = json.loads(query)
                query = params.get('query', '')
                limit = params.get('limit', 100)

            if not self._resolver.conn:
                self._resolver.connect()

            response = self._resolver.resolve(query, limit=limit, fuzzy=True)
            return self._format_results(query, response)

        except Exception as e:
            return f"Error resolving device: {str(e)}"

    def _format_results(self, query: str, response) -> str:
        if response.total_matches == 0:
            return f"No devices found matching '{query}'."

        lines = [f"Found {response.total_matches} devices matching '{query}':\n"]

        product_code_info = {}
        company_counts = {}
        match_type_counts = {}

        for match in response.matches:
            for pc in match.device.product_codes:
                if pc.product_code not in product_code_info:
                    product_code_info[pc.product_code] = {
                        "name": pc.product_code_name,
                        "count": 0
                    }
                product_code_info[pc.product_code]["count"] += 1

            if match.device.company_name:
                company_counts[match.device.company_name] = company_counts.get(match.device.company_name, 0) + 1

            match_type_counts[match.match_type.value] = match_type_counts.get(match.match_type.value, 0) + 1

        lines.append("HOW MATCHES WERE FOUND:")
        match_type_labels = {
            "exact_brand": "Exact brand name match",
            "exact_company": "Exact company name match",
            "exact_product_code": "Exact product code match",
            "fuzzy_brand": "Brand name contains query",
            "fuzzy_description": "Device description contains query",
            "fuzzy_gmdn_name": "GMDN term contains query",
            "fuzzy_company": "Company name contains query",
            "fuzzy_product_code_name": "Product code name contains query",
        }
        for match_type, count in sorted(match_type_counts.items(), key=lambda x: x[1], reverse=True):
            label = match_type_labels.get(match_type, match_type)
            lines.append(f"  {label}: {count} matches")

        if product_code_info:
            lines.append(f"\nPRODUCT CODES FOUND ({len(product_code_info)} unique codes):")
            sorted_codes = sorted(product_code_info.items(), key=lambda x: x[1]["count"], reverse=True)
            for code, info in sorted_codes:
                lines.append(f"  {code}: {info['name']} ({info['count']} devices)")

        if company_counts:
            lines.append("\nTOP MANUFACTURERS:")
            sorted_companies = sorted(company_counts.items(), key=lambda x: x[1], reverse=True)
            for company, count in sorted_companies[:5]:
                lines.append(f"  {company}: {count} devices")

        lines.append("\nDETAILED MATCH EXAMPLES:")
        for i, match in enumerate(response.matches[:8], 1):
            device_name = match.device.brand_name or "N/A"
            if len(device_name) > 50:
                device_name = device_name[:47] + "..."

            description = match.device.device_description or "N/A"
            if len(description) > 80:
                description = description[:77] + "..."

            company = match.device.company_name or "Unknown"
            codes = ", ".join(match.device.get_product_codes()[:3]) or "N/A"

            match_field_display = {
                "brand_name": "Brand Name",
                "device_description": "Device Description",
                "company_name": "Company Name",
                "gmdn_pt_name": "GMDN Term",
                "product_code_name": "Product Code Name",
                "product_code": "Product Code",
                "primary_di": "Device Identifier",
            }.get(match.match_field, match.match_field)

            match_value = match.match_value
            if len(match_value) > 80:
                match_value = match_value[:77] + "..."

            lines.append(f"  {i}. Brand: {device_name}")
            lines.append(f"     Description: {description}")
            lines.append(f"     Company: {company}")
            lines.append(f"     Product Codes: {codes}")
            lines.append(f"     >>> Matched on: {match_field_display}")
            lines.append(f"     >>> Matched text: \"{match_value}\"")
            lines.append(f"     >>> Confidence: {match.confidence:.0%}")
            lines.append("")

        return "\n".join(lines)

    async def _arun(self, query: str, limit: int = 100) -> str:
        return self._run(query, limit)
