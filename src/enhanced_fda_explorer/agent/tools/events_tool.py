"""
Events Tool - Search FDA adverse event reports (MAUDE database).
"""
from typing import Type, Optional
from collections import Counter
import time
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import requests
import httpx
import re


COUNTRY_CODES = {
    "united states": "US", "usa": "US", "us": "US", "america": "US",
    "china": "CN", "chinese": "CN", "prc": "CN",
    "germany": "DE", "german": "DE",
    "japan": "JP", "japanese": "JP",
    "united kingdom": "GB", "uk": "GB", "britain": "GB", "british": "GB",
    "france": "FR", "french": "FR",
    "canada": "CA", "canadian": "CA",
    "mexico": "MX", "mexican": "MX",
    "south korea": "KR", "korea": "KR", "korean": "KR",
    "taiwan": "TW", "taiwanese": "TW",
    "italy": "IT", "italian": "IT",
    "netherlands": "NL", "dutch": "NL",
    "switzerland": "CH", "swiss": "CH",
    "australia": "AU", "australian": "AU",
    "india": "IN", "indian": "IN",
    "ireland": "IE", "irish": "IE",
    "israel": "IL", "israeli": "IL",
    "sweden": "SE", "swedish": "SE",
    "denmark": "DK", "danish": "DK",
    "belgium": "BE", "belgian": "BE",
    "spain": "ES", "spanish": "ES",
    "brazil": "BR", "brazilian": "BR",
}


class SearchEventsInput(BaseModel):
    query: str = Field(default="", description="Device name or company name (can be empty if using country or product_code)")
    date_from: str = Field(default="", description="Start date in YYYYMMDD format")
    date_to: str = Field(default="", description="End date in YYYYMMDD format")
    limit: int = Field(default=100, description="Maximum number of results")
    country: str = Field(default="", description="Filter by manufacturer's country (e.g., 'China', 'Germany', 'US')")
    product_code: str = Field(default="", description="FDA product code (e.g., 'FXX' for surgical masks)")


class SearchEventsTool(BaseTool):
    name: str = "search_events"
    description: str = """Search FDA adverse event reports (MAUDE database).

    Parameters:
    - query: Device name or manufacturer name (can be empty if using country/product_code)
    - country: Filter by manufacturer's country (e.g., 'China', 'Germany')
    - product_code: FDA product code (e.g., 'FXX' for surgical masks)

    Examples:
    - Events for masks: search_events(product_code="FXX")
    - Events from China: search_events(country="China")
    - Mask events from China: search_events(product_code="FXX", country="China")
    - Events for a company: search_events(query="Medtronic")

    Returns event types (Death, Injury, Malfunction), outcomes, and device problems."""
    args_schema: Type[BaseModel] = SearchEventsInput

    _api_key: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key

    def _normalize_country(self, country: str) -> str:
        country_lower = country.lower().strip()
        if country_lower in COUNTRY_CODES:
            return COUNTRY_CODES[country_lower]
        if len(country) == 2:
            return country.upper()
        return country

    def _run(self, query: str = "", date_from: str = "", date_to: str = "", limit: int = 100, country: str = "", product_code: str = "") -> str:
        try:
            url = "https://api.fda.gov/device/event.json"
            search_parts = []

            if product_code:
                search_parts.append(f'device.device_report_product_code:"{product_code.upper()}"')
            elif query:
                if re.match(r'^[A-Z]{3}$', query.upper()):
                    search_parts.append(f'device.device_report_product_code:"{query.upper()}"')
                else:
                    search_parts.append(f'(device.brand_name:"{query}" OR device.generic_name:"{query}" OR device.manufacturer_d_name:"{query}")')

            if country:
                country_code = self._normalize_country(country)
                search_parts.append(f'device.manufacturer_d_country:"{country_code}"')

            if date_from and date_to:
                search_parts.append(f'date_received:[{date_from} TO {date_to}]')
            elif date_from:
                search_parts.append(f'date_received:[{date_from} TO *]')
            elif date_to:
                search_parts.append(f'date_received:[* TO {date_to}]')

            if not search_parts:
                return "Error: Must provide query, country, or product_code parameter."

            search = " AND ".join(search_parts)

            params = {
                "search": search,
                "limit": min(limit, 100),
                "sort": "date_received:desc"
            }
            if self._api_key:
                params["api_key"] = self._api_key

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            return self._format_results(query, data)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return f"No adverse events found for '{query}'."
            return f"FDA API error: {str(e)}"
        except Exception as e:
            return f"Error searching events: {str(e)}"

    def _format_results(self, query: str, data: dict) -> str:
        results = data.get("results", [])
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        if not results:
            return f"No adverse events found for '{query}'."

        lines = [f"Found {total} adverse events for '{query}' (showing {len(results)}):\n"]

        event_types = Counter()
        outcomes = Counter()
        problems = Counter()

        for event in results:
            event_type = event.get("event_type", "Unknown")
            event_types[event_type] += 1

            for patient in event.get("patient", []):
                outcome = patient.get("patient_problems", ["Unknown"])
                if isinstance(outcome, list):
                    for o in outcome:
                        outcomes[o] += 1

            for device in event.get("device", []):
                for problem in device.get("device_problem_text", []):
                    if problem:
                        problems[problem[:50]] += 1

        lines.append("EVENT TYPES:")
        for etype, count in event_types.most_common(5):
            lines.append(f"  {etype}: {count}")

        if outcomes:
            lines.append("\nPATIENT OUTCOMES:")
            for outcome, count in outcomes.most_common(5):
                lines.append(f"  {outcome}: {count}")

        if problems:
            lines.append("\nDEVICE PROBLEMS:")
            for problem, count in problems.most_common(5):
                lines.append(f"  {problem}: {count}")

        lines.append("\nRECENT EVENTS:")
        for i, event in enumerate(results[:3], 1):
            date = event.get("date_received", "Unknown")
            event_type = event.get("event_type", "Unknown")
            devices = event.get("device", [])
            device_name = devices[0].get("brand_name", "Unknown") if devices else "Unknown"
            mfr = devices[0].get("manufacturer_d_name", "Unknown") if devices else "Unknown"

            lines.append(f"  {i}. Date: {date}, Type: {event_type}")
            lines.append(f"     Device: {device_name[:50]}")
            lines.append(f"     Manufacturer: {mfr[:40]}")

        return "\n".join(lines)

    async def _arun(self, query: str = "", date_from: str = "", date_to: str = "", limit: int = 100, country: str = "", product_code: str = "") -> str:
        """Async version using httpx for non-blocking HTTP calls."""
        start_time = time.time()
        try:
            url = "https://api.fda.gov/device/event.json"
            search_parts = []

            if product_code:
                search_parts.append(f'device.device_report_product_code:"{product_code.upper()}"')
            elif query:
                if re.match(r'^[A-Z]{3}$', query.upper()):
                    search_parts.append(f'device.device_report_product_code:"{query.upper()}"')
                else:
                    search_parts.append(f'(device.brand_name:"{query}" OR device.generic_name:"{query}" OR device.manufacturer_d_name:"{query}")')

            if country:
                country_code = self._normalize_country(country)
                search_parts.append(f'device.manufacturer_d_country:"{country_code}"')

            if date_from and date_to:
                search_parts.append(f'date_received:[{date_from} TO {date_to}]')
            elif date_from:
                search_parts.append(f'date_received:[{date_from} TO *]')
            elif date_to:
                search_parts.append(f'date_received:[* TO {date_to}]')

            if not search_parts:
                return "Error: Must provide query, country, or product_code parameter."

            search = " AND ".join(search_parts)

            params = {
                "search": search,
                "limit": min(limit, 100),
                "sort": "date_received:desc"
            }
            if self._api_key:
                params["api_key"] = self._api_key

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            elapsed_ms = (time.time() - start_time) * 1000
            search_desc = product_code or query or country
            result = self._format_results(search_desc, data)
            return f"{result}\n\n[Query completed in {elapsed_ms:.0f}ms]"

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                search_desc = product_code or query or country
                return f"No adverse events found for '{search_desc}'."
            return f"FDA API error: {str(e)}"
        except Exception as e:
            return f"Error searching events: {str(e)}"
