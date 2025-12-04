"""
Device Resolver Tool - GUDID database lookup for device identification.
"""
from typing import Type, Optional, Callable
import logging
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import json
import time

from ...tools.device_resolver import DeviceResolver
from ...config import get_config
from ...models.responses import (
    ResolvedEntities, ProductCodeInfo, ManufacturerInfo, DeviceInfo
)

logger = logging.getLogger("fda_agent.device_resolver")


class DeviceResolverInput(BaseModel):
    query: str = Field(description="Device name, brand, company, or product code to search for")
    limit: int = Field(default=500, description="Maximum number of results to return")


class DeviceResolverTool(BaseTool):
    name: str = "resolve_device"
    description: str = """Look up medical devices in the GUDID database by name, brand, company, or product code.
    Returns product codes, GMDN terms, manufacturer info, and device identifiers.
    Use this FIRST to identify devices and get FDA product codes before searching other databases."""
    args_schema: Type[BaseModel] = DeviceResolverInput

    _db_path: str = ""
    _resolver: Optional[DeviceResolver] = None
    _last_structured_result: Optional[ResolvedEntities] = None
    _progress_callback: Optional[Callable[[str], None]] = None

    def __init__(self, db_path: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        config = get_config()
        self._db_path = db_path or config.gudid_db_path
        self._resolver = DeviceResolver(self._db_path)

    def set_progress_callback(self, callback: Optional[Callable[[str], None]]):
        """Set a callback to receive progress updates during resolution."""
        self._progress_callback = callback

    def get_last_structured_result(self) -> Optional[ResolvedEntities]:
        return self._last_structured_result

    def _emit_progress(self, step: str, count: int):
        """Emit progress update via callback and logger."""
        msg = f"Searching {step}... ({count} matches so far)"
        logger.info(msg)
        if self._progress_callback:
            self._progress_callback(msg)

    def _run(self, query: str, limit: int = 500) -> str:
        try:
            if isinstance(query, str) and query.startswith('{'):
                params = json.loads(query)
                query = params.get('query', '')
                limit = params.get('limit', 100)

            if not self._resolver.conn:
                self._resolver.connect()

            start_time = time.time()
            response = self._resolver.resolve(query, limit=limit, fuzzy=True, progress_callback=self._emit_progress)
            execution_time = (time.time() - start_time) * 1000

            self._last_structured_result = self._to_structured(query, response, execution_time)
            return self._format_results(query, response)

        except Exception as e:
            self._last_structured_result = None
            return f"Error resolving device: {str(e)}"

    def _to_structured(self, query: str, response, execution_time: float) -> ResolvedEntities:
        product_code_info = {}
        company_counts = {}

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

        # Only include product codes with >= 2 devices
        product_codes = [
            ProductCodeInfo(
                code=code,
                name=info["name"],
                device_count=info["count"]
            )
            for code, info in sorted(product_code_info.items(), key=lambda x: x[1]["count"], reverse=True)
            if info["count"] >= 2
        ]

        manufacturers = [
            ManufacturerInfo(name=name, device_count=count)
            for name, count in sorted(company_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        devices = [
            DeviceInfo(
                brand_name=m.device.brand_name or "",
                company_name=m.device.company_name or "",
                device_description=m.device.device_description,
                product_codes=m.device.get_product_codes(),
                primary_di=m.device.primary_di,
                confidence=m.confidence,
                match_field=m.match_field
            )
            for m in response.matches[:100]
        ]

        return ResolvedEntities(
            query=query,
            product_codes=product_codes,
            manufacturers=manufacturers,
            devices=devices,
            total_devices_matched=response.total_matches,
            resolution_time_ms=execution_time
        )

    def _format_results(self, query: str, response) -> str:
        if response.total_matches == 0:
            return f"No devices found matching '{query}'."

        time_str = f" (searched in {response.execution_time_ms:.0f}ms)" if response.execution_time_ms else ""
        lines = [f"Found {response.total_matches} devices matching '{query}'{time_str}:\n"]

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
            # Filter to only show product codes with >= 2 devices
            sorted_codes = sorted(product_code_info.items(), key=lambda x: x[1]["count"], reverse=True)
            filtered_codes = [(code, info) for code, info in sorted_codes if info["count"] >= 2]

            if filtered_codes:
                lines.append(f"\nPRODUCT CODES FOUND ({len(filtered_codes)} codes with 2+ devices):")
                for code, info in filtered_codes:
                    lines.append(f"  {code}: {info['name']} ({info['count']} devices)")
            else:
                lines.append(f"\nNo product codes found with 2+ matching devices.")

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

    async def _arun(self, query: str, limit: int = 500) -> str:
        return self._run(query, limit)
