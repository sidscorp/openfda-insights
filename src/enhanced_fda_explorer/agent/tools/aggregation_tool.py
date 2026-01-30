"""
Aggregated registrations tool - country and product-code rollups from OpenFDA registrations.
Uses count endpoints (no per-record looping).
"""
import json
from typing import Type, Optional, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, validator

from ...openfda_client import OpenFDAClient


class AggregateRegistrationsInput(BaseModel):
    query: Optional[str] = Field(
        default=None,
        description="Device term to filter registrations (e.g., 'mask', 'respirator').",
    )
    product_codes: Optional[list[str]] = Field(
        default=None,
        description="Optional list of product codes to pivot by country.",
    )
    max_countries: int = Field(
        default=20,
        description="Maximum countries to display for each rollup.",
    )
    include_establishments: bool = Field(
        default=False,
        description="If true, include sample establishment locations for the main query.",
    )
    max_establishments: int = Field(
        default=25,
        description="Maximum establishments to list when include_establishments is true.",
    )

    @validator("product_codes", pre=True)
    def parse_product_codes(cls, v: Any) -> Optional[list[str]]:
        if v is None:
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            return [v]
        return v


class AggregateRegistrationsTool(BaseTool):
    name: str = "aggregate_registrations"
    description: str = """Get manufacturer establishment counts BY COUNTRY for a device type.
**USE THIS TOOL** for geographic manufacturer questions:
- "Which country manufactures the most X?" → aggregate_registrations(query="X")
- "Where are X manufacturers located?"
- "Top countries for X manufacturing"
- "Manufacturers by country for X"

Returns: Country-level counts (e.g., CN: 1657, US: 741) from FDA registration data.
Can include sample establishment locations when include_establishments=true."""
    args_schema: Type[BaseModel] = AggregateRegistrationsInput

    _client: OpenFDAClient
    _last_structured_result: Optional[dict] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._client = OpenFDAClient(api_key=api_key)

    def get_last_structured_result(self) -> Optional[dict]:
        return self._last_structured_result

    def _run(
        self,
        query: Optional[str] = None,
        product_codes: Optional[list[str]] = None,
        max_countries: int = 20,
        include_establishments: bool = False,
        max_establishments: int = 25,
    ) -> str:
        self._last_structured_result = None
        
        if not query and not product_codes:
            return "Provide a query (e.g., 'mask') or product_codes to aggregate."

        search_base = ""
        if query:
            # Match proprietary name or device name fields.
            search_base = f"(proprietary_name:{query} OR products.openfda.device_name:{query})"

        lines: list[str] = []
        structured_data = {
            "query": query,
            "product_codes": product_codes,
            "aggregations": [],
            "records": [],
            "total_establishments": 0,
            "countries_count": 0,
        }

        # Country rollup for the query as a whole.
        primary_counts = []
        if search_base:
            country_counts = self._count("registration.iso_country_code", search_base)
            primary_counts = country_counts
            structured_data["aggregations"].append({
                "type": "query_country_counts",
                "filter": query,
                "counts": country_counts
            })
            structured_data["total_establishments"] = sum(c['count'] for c in country_counts) if country_counts else 0
            structured_data["countries_count"] = len(country_counts) if country_counts else 0
            structured_data["records"] = [{"country": c['term'], "count": c['count']} for c in country_counts[:max_countries]]
            lines.append(f"Country counts for '{query}' registrations:")
            if country_counts:
                for c in country_counts[:max_countries]:
                    lines.append(f"  {c['term']}: {c['count']}")
            else:
                lines.append("  No countries found for this query.")
            lines.append("")

        # Per-product-code country rollups.
        if product_codes:
            all_code_counts = []
            for code in product_codes:
                search = search_base
                if search:
                    search = f"{search} AND products.product_code:{code}"
                else:
                    search = f"products.product_code:{code}"

                country_counts = self._count("registration.iso_country_code", search)
                all_code_counts.extend(country_counts)
                structured_data["aggregations"].append({
                    "type": "product_code_country_counts",
                    "filter": code,
                    "counts": country_counts
                })
                lines.append(f"Country counts for product code {code}:")
                if country_counts:
                    for c in country_counts[:max_countries]:
                        lines.append(f"  {c['term']}: {c['count']}")
                else:
                    lines.append("  No countries found for this product code.")
                lines.append("")

            if not search_base and all_code_counts:
                structured_data["total_establishments"] = sum(c['count'] for c in all_code_counts)
                structured_data["countries_count"] = len(set(c['term'] for c in all_code_counts))
                country_totals = {}
                for c in all_code_counts:
                    country_totals[c['term']] = country_totals.get(c['term'], 0) + c['count']
                sorted_countries = sorted(country_totals.items(), key=lambda x: x[1], reverse=True)
                structured_data["records"] = [{"country": k, "count": v} for k, v in sorted_countries[:max_countries]]

        if include_establishments and search_base:
            lines.append(f"Sample establishments for '{query}' (first {max_establishments} results):")
            establishments = self._fetch_establishments(search_base, max_establishments)
            structured_data["establishments"] = establishments
            if establishments:
                for est in establishments:
                    loc = ", ".join(part for part in [est.get("city"), est.get("state"), est.get("country")] if part)
                    loc = loc or "Location unknown"
                    lines.append(f"  • {est.get('name','Unknown')} - {loc}")
            else:
                lines.append("  No establishments found in sample.")

        if not lines:
            return "No aggregation results."

        self._last_structured_result = structured_data
        return "\n".join(lines).rstrip()

    def _count(self, field: str, search: str) -> list[dict]:
        data = self._client.get(
            "device/registrationlisting.json",
            params={"search": search, "count": field},
        )
        return data.get("results", [])

    def _fetch_establishments(self, search: str, limit: int) -> list[dict]:
        data = self._client.get(
            "device/registrationlisting.json",
            params={"search": search, "limit": max(1, min(limit, 100))},
        )
        return self._parse_establishments(data, limit)

    def _parse_establishments(self, data: dict, limit: int) -> list[dict]:
        results = data.get("results", [])
        establishments: list[dict] = []
        seen = set()
        for r in results:
            reg = r.get("registration", {}) if isinstance(r, dict) else {}
            name = reg.get("name", "Unknown")
            if name in seen:
                continue
            seen.add(name)
            establishments.append(
                {
                    "name": name,
                    "city": reg.get("city", ""),
                    "state": reg.get("state_code", ""),
                    "country": reg.get("iso_country_code", ""),
                }
            )
            if len(establishments) >= limit:
                break
        return establishments

    async def _count_async(self, field: str, search: str) -> list[dict]:
        data = await self._client.aget(
            "device/registrationlisting.json",
            params={"search": search, "count": field},
        )
        return data.get("results", [])

    async def _fetch_establishments_async(self, search: str, limit: int) -> list[dict]:
        data = await self._client.aget(
            "device/registrationlisting.json",
            params={"search": search, "limit": max(1, min(limit, 100))},
        )
        return self._parse_establishments(data, limit)

    async def _arun(
        self,
        query: Optional[str] = None,
        product_codes: Optional[list[str]] = None,
        max_countries: int = 20,
        include_establishments: bool = False,
        max_establishments: int = 25,
    ) -> str:
        self._last_structured_result = None

        if not query and not product_codes:
            return "Provide a query (e.g., 'mask') or product_codes to aggregate."

        search_base = ""
        if query:
            search_base = f"(proprietary_name:{query} OR products.openfda.device_name:{query})"

        lines: list[str] = []
        structured_data = {
            "query": query,
            "product_codes": product_codes,
            "aggregations": []
        }

        if search_base:
            country_counts = await self._count_async("registration.iso_country_code", search_base)
            structured_data["aggregations"].append({
                "type": "query_country_counts",
                "filter": query,
                "counts": country_counts
            })
            lines.append(f"Country counts for '{query}' registrations:")
            if country_counts:
                for c in country_counts[:max_countries]:
                    lines.append(f"  {c['term']}: {c['count']}")
            else:
                lines.append("  No countries found for this query.")
            lines.append("")

        if product_codes:
            for code in product_codes:
                search = search_base
                if search:
                    search = f"{search} AND products.product_code:{code}"
                else:
                    search = f"products.product_code:{code}"

                country_counts = await self._count_async("registration.iso_country_code", search)
                structured_data["aggregations"].append({
                    "type": "product_code_country_counts",
                    "filter": code,
                    "counts": country_counts
                })
                lines.append(f"Country counts for product code {code}:")
                if country_counts:
                    for c in country_counts[:max_countries]:
                        lines.append(f"  {c['term']}: {c['count']}")
                else:
                    lines.append("  No countries found for this product code.")
                lines.append("")

        if include_establishments and search_base:
            lines.append(f"Sample establishments for '{query}' (first {max_establishments} results):")
            establishments = await self._fetch_establishments_async(search_base, max_establishments)
            structured_data["establishments"] = establishments
            if establishments:
                for est in establishments:
                    loc = ", ".join(part for part in [est.get("city"), est.get("state"), est.get("country")] if part)
                    loc = loc or "Location unknown"
                    lines.append(f"  • {est.get('name','Unknown')} - {loc}")
            else:
                lines.append("  No establishments found in sample.")

        if not lines:
            return "No aggregation results."

        self._last_structured_result = structured_data
        return "\n".join(lines).rstrip()
