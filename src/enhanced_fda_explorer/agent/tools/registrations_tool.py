"""
Registrations Tool - Search FDA establishment registrations with location data.
"""
from typing import Type, Optional
from collections import Counter
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ...openfda_client import OpenFDAClient


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

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key
        self._client = OpenFDAClient(api_key=api_key)

    def _build_search(self, query: str) -> str:
        return f'registration.name:"{query}" OR proprietary_name:"{query}" OR products.openfda.device_name:"{query}"'

    def _run(self, query: str, limit: int = 100) -> str:
        try:
            search = self._build_search(query)
            data = self._client.get(
                "device/registrationlisting.json",
                params={"search": search, "limit": min(limit, 100)}
            )
            return self._format_results(query, data)
        except Exception as e:
            if "404" in str(e) or "No results" in str(e):
                return f"No registrations found for '{query}'."
            return f"Error searching registrations: {str(e)}"

    def _format_results(self, query: str, data: dict) -> str:
        results = data.get("results", []) or []
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        if not results:
            return f"No registrations found for '{query}'."

        lines = [f"Found {total} registrations for '{query}' (showing {len(results)}):\n"]

        country_counts = Counter()
        state_counts = Counter()
        establishments = {}

        for result in results:
            reg = result.get("registration", {})
            name = reg.get("name", "Unknown")
            city = reg.get("city", "")
            state = reg.get("state_code", "")
            country = reg.get("iso_country_code", "US")
            address = reg.get("address_line_1", "")
            zip_code = reg.get("zip_code", "")

            country_counts[country] += 1
            if state:
                state_counts[state] += 1

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

        lines.append("LOCATIONS BY COUNTRY:")
        for country, count in country_counts.most_common(10):
            country_name = self._get_country_name(country)
            lines.append(f"  {country_name} ({country}): {count} establishments")

        if state_counts:
            lines.append("\nTOP US STATES:")
            for state, count in state_counts.most_common(10):
                lines.append(f"  {state}: {count} establishments")

        lines.append(f"\nESTABLISHMENT DETAILS ({len(establishments)} unique):")
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
        try:
            search = self._build_search(query)
            data = await self._client.aget(
                "device/registrationlisting.json",
                params={"search": search, "limit": min(limit, 100)}
            )
            return self._format_results(query, data)
        except Exception as e:
            if "404" in str(e) or "No results" in str(e):
                return f"No registrations found for '{query}'."
            return f"Error searching registrations: {str(e)}"
