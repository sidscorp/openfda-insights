"""
Registrations Tool - Search FDA establishment registrations with location data.
"""
import asyncio
from typing import Type, Optional, Callable, Dict, Any
from collections import Counter
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ...openfda_client import OpenFDAClient, HybridAggregationResult
from ...models.responses import RegistrationSearchResult, RegistrationRecord, AggregationCount

REGISTRATIONS_SERVER_FIELDS = ["registration.iso_country_code", "registration.state_code"]
REGISTRATIONS_CLIENT_EXTRACTORS: Dict[str, Callable[[Dict[str, Any]], Optional[str]]] = {
    "country": lambda r: (r.get("registration") or {}).get("iso_country_code"),
    "state": lambda r: (r.get("registration") or {}).get("state_code"),
}


class SearchRegistrationsInput(BaseModel):
    query: str = Field(description="Company name, product name, or product code to search")
    limit: int = Field(default=100, description="Maximum number of results")


class SearchRegistrationsTool(BaseTool):
    name: str = "search_registrations"
    description: str = """Search FDA establishment registrations to find manufacturer locations.
    Returns company addresses including city, state/province, and country.
    Use this to find WHERE manufacturers are located geographically."""
    args_schema: Type[BaseModel] = SearchRegistrationsInput

    _client: OpenFDAClient
    _api_key: Optional[str] = None
    _last_structured_result: Optional[RegistrationSearchResult] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key
        self._client = OpenFDAClient(api_key=api_key)

    def get_last_structured_result(self) -> Optional[RegistrationSearchResult]:
        return self._last_structured_result

    def _to_structured(
        self,
        query: str,
        data: dict,
        hybrid_result: Optional[HybridAggregationResult] = None,
    ) -> RegistrationSearchResult:
        results = data.get("results", []) or []
        total = hybrid_result.total_available if hybrid_result else data.get("meta", {}).get("results", {}).get("total", 0)
        raw_aggs = hybrid_result.aggregations if hybrid_result else {}

        records = []
        for r in results:
            reg = r.get("registration", {})
            proprietary_names = []
            for prod in r.get("products", []):
                openfda = prod.get("openfda", {})
                device_name = openfda.get("device_name", "")
                if device_name and device_name not in proprietary_names:
                    proprietary_names.append(device_name)

            records.append(RegistrationRecord(
                registration_number=reg.get("registration_number"),
                name=reg.get("name", "Unknown"),
                city=reg.get("city"),
                state_code=reg.get("state_code"),
                country_code=reg.get("iso_country_code", "US"),
                address_line_1=reg.get("address_line_1"),
                postal_code=reg.get("zip_code"),
                proprietary_names=proprietary_names[:5],
            ))

        aggregations = {}
        for field, items in raw_aggs.items():
            aggregations[field] = [AggregationCount(term=item["term"], count=item["count"]) for item in items]

        return RegistrationSearchResult(
            query=query,
            total_found=total,
            records=records,
            aggregations=aggregations,
        )

    def _build_search(self, query: str) -> str:
        return f'registration.name:"{query}" OR proprietary_name:"{query}" OR products.openfda.device_name:"{query}"'

    def _run(self, query: str, limit: int = 100) -> str:
        return asyncio.run(self._arun(query, limit))

    def _format_results(
        self,
        query: str,
        data: dict,
        hybrid_result: Optional[HybridAggregationResult] = None,
    ) -> str:
        results = data.get("results", []) or []
        total = hybrid_result.total_available if hybrid_result else data.get("meta", {}).get("results", {}).get("total", 0)
        aggregations = hybrid_result.aggregations if hybrid_result else {}

        if not results:
            return f"No registrations found for '{query}'."

        agg_label = hybrid_result.get_label() if hybrid_result else "sample only"
        lines = [f"Found {total} registrations for '{query}'. Statistics from {agg_label}. Showing {len(results)} results:\n"]

        country_key = next(
            (k for k in ["registration.iso_country_code", "country"] if k in aggregations),
            None,
        )
        if country_key:
            lines.append(f"LOCATIONS BY COUNTRY ({agg_label}):")
            for item in aggregations[country_key][:10]:
                country_name = self._get_country_name(item["term"])
                lines.append(f"  {country_name} ({item['term']}): {item['count']} establishments")
        else:
            country_counts: Counter = Counter()
            for result in results:
                reg = result.get("registration", {})
                country = reg.get("iso_country_code", "US")
                country_counts[country] += 1
            lines.append("LOCATIONS BY COUNTRY (sample only):")
            for country, count in country_counts.most_common(10):
                country_name = self._get_country_name(country)
                lines.append(f"  {country_name} ({country}): {count} establishments")

        state_key = next(
            (k for k in ["registration.state_code", "state"] if k in aggregations),
            None,
        )
        if state_key:
            state_items = [item for item in aggregations[state_key][:10] if item["term"]]
            if state_items:
                lines.append(f"\nTOP US STATES ({agg_label}):")
                for item in state_items:
                    lines.append(f"  {item['term']}: {item['count']} establishments")
        else:
            state_counts: Counter = Counter()
            for result in results:
                reg = result.get("registration", {})
                state = reg.get("state_code", "")
                if state:
                    state_counts[state] += 1
            if state_counts:
                lines.append("\nTOP US STATES (sample only):")
                for state, count in state_counts.most_common(10):
                    lines.append(f"  {state}: {count} establishments")

        establishments = {}
        for result in results:
            reg = result.get("registration", {})
            name = reg.get("name", "Unknown")
            city = reg.get("city", "")
            state = reg.get("state_code", "")
            country = reg.get("iso_country_code", "US")
            address = reg.get("address_line_1", "")
            zip_code = reg.get("zip_code", "")

            if name not in establishments:
                establishments[name] = {
                    "address": address,
                    "city": city,
                    "state": state,
                    "country": country,
                    "zip": zip_code,
                    "products": []
                }

            for prod in result.get("products", []):
                openfda = prod.get("openfda", {})
                device_name = openfda.get("device_name", "")
                if device_name and device_name not in establishments[name]["products"]:
                    establishments[name]["products"].append(device_name)

        lines.append(f"\nESTABLISHMENT DETAILS ({len(establishments)} unique in sample):")
        for name, info in list(establishments.items())[:15]:
            location_parts = []
            if info["city"]:
                location_parts.append(info["city"])
            if info["state"]:
                location_parts.append(info["state"])
            if info["country"]:
                location_parts.append(info["country"])
            location = ", ".join(location_parts) if location_parts else "Location unknown"

            lines.append(f"  • {name}")
            lines.append(f"    Location: {location}")
            if info["products"]:
                prod_list = ", ".join(info["products"][:3])
                if len(info["products"]) > 3:
                    prod_list += f" (+{len(info['products']) - 3} more)"
                lines.append(f"    Products: {prod_list}")

        return "\n".join(lines)

    def _get_country_name(self, code: str) -> str:
        countries = {
            "US": "United States",
            "CN": "China",
            "DE": "Germany",
            "JP": "Japan",
            "GB": "United Kingdom",
            "FR": "France",
            "CA": "Canada",
            "MX": "Mexico",
            "KR": "South Korea",
            "TW": "Taiwan",
            "IT": "Italy",
            "NL": "Netherlands",
            "CH": "Switzerland",
            "AU": "Australia",
            "IN": "India",
            "IE": "Ireland",
            "BE": "Belgium",
            "IL": "Israel",
            "DK": "Denmark",
            "SE": "Sweden",
        }
        return countries.get(code, code)

    async def _arun(self, query: str, limit: int = 100) -> str:
        """Async version using httpx for non-blocking HTTP calls with hybrid aggregation."""
        try:
            search = self._build_search(query)
            endpoint = "device/registrationlisting.json"

            hybrid_result = await self._client.aget_hybrid_aggregations(
                endpoint=endpoint,
                search=search,
                server_count_fields=REGISTRATIONS_SERVER_FIELDS,
                client_field_extractors=REGISTRATIONS_CLIENT_EXTRACTORS,
                max_client_records=5000,
            )

            data = await self._client.aget(
                endpoint,
                params={"search": search, "limit": min(limit, 100)}
            )

            self._last_structured_result = self._to_structured(query, data, hybrid_result)
            return self._format_results(query, data, hybrid_result)
        except Exception as e:
            self._last_structured_result = None
            if "404" in str(e) or "No results" in str(e):
                return f"No registrations found for '{query}'."
            return f"Error searching registrations: {str(e)}"
