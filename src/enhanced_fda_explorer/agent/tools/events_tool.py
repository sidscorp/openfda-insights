"""
Events Tool - Search FDA adverse event reports (MAUDE database).
"""
from typing import Type, Optional
from collections import Counter
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import re

from ...openfda_client import OpenFDAClient
from ...models.responses import EventSearchResult, AdverseEventRecord

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
    query: str = Field(default="", description="Device name or company name (can be empty if using country or product_codes)")
    product_codes: list[str] = Field(default_factory=list, description="FDA product codes to search for (e.g., ['FXX', 'MSH']). Use this for precise searches after resolving device names.")
    date_from: str = Field(default="", description="Start date in YYYYMMDD format")
    date_to: str = Field(default="", description="End date in YYYYMMDD format")
    limit: int = Field(default=100, description="Maximum number of results")
    country: str = Field(default="", description="Filter by manufacturer's country (e.g., 'China', 'Germany', 'US')")


class SearchEventsTool(BaseTool):
    name: str = "search_events"
    description: str = """Search FDA adverse event reports (MAUDE database).

    Parameters:
    - product_codes: List of FDA product codes (e.g., ['FXX', 'MSH']). ALWAYS use this when you have product codes from resolve_device.
    - query: Device name or manufacturer name (fallback for text search)
    - country: Filter by manufacturer's country (e.g., 'China', 'Germany')

    IMPORTANT: If you called resolve_device and got product codes, pass them to product_codes parameter for precise results.

    Examples:
    - BEST: After resolving "mask" -> FXX, MSH: search_events(product_codes=["FXX", "MSH"])
    - By product codes and country: search_events(product_codes=["FXX"], country="China")
    - Events from China: search_events(country="China")
    - Fallback text search: search_events(query="Medtronic")

    Returns event types (Death, Injury, Malfunction), outcomes, and device problems."""
    args_schema: Type[BaseModel] = SearchEventsInput

    _api_key: Optional[str] = None
    _client: OpenFDAClient
    _last_structured_result: Optional[EventSearchResult] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key
        self._client = OpenFDAClient(api_key=api_key)

    def get_last_structured_result(self) -> Optional[EventSearchResult]:
        return self._last_structured_result

    def _normalize_country(self, country: str) -> str:
        country_lower = country.lower().strip()
        if country_lower in COUNTRY_CODES:
            return COUNTRY_CODES[country_lower]
        if len(country) == 2:
            return country.upper()
        return country

    def _run(self, query: str = "", product_codes: list[str] = None, date_from: str = "", date_to: str = "", limit: int = 100, country: str = "") -> str:
        try:
            search = self._build_search(query, product_codes or [], country, date_from, date_to)
            data = self._client.get_paginated(
                "device/event.json",
                params={"search": search},
                limit=min(limit, 500),
                sort="date_received:desc",
            )
            search_desc = query or (", ".join(product_codes) if product_codes else "") or country
            self._last_structured_result = self._to_structured(search_desc, date_from, date_to, data)
            return self._format_results(search_desc, data)

        except ValueError as e:
            self._last_structured_result = None
            return f"Error: {e}"
        except Exception as e:
            self._last_structured_result = None
            return f"Error searching events: {str(e)}"

    def _format_results(self, query: str, data: dict) -> str:
        results = data.get("results", []) or []
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
        # Show all fetched results; upstream pagination already respects the requested limit.
        for i, event in enumerate(results, 1):
            date = event.get("date_received", "Unknown")
            event_type = event.get("event_type", "Unknown")
            devices = event.get("device", [])
            device_name = devices[0].get("brand_name", "Unknown") if devices else "Unknown"
            mfr = devices[0].get("manufacturer_d_name", "Unknown") if devices else "Unknown"

            lines.append(f"  {i}. Date: {date}, Type: {event_type}")
            lines.append(f"     Device: {device_name[:50]}")
            lines.append(f"     Manufacturer: {mfr[:40]}")

        return "\n".join(lines)

    def _to_structured(self, query: str, date_from: str, date_to: str, data: dict) -> EventSearchResult:
        results = data.get("results", []) or []
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        records = []
        event_type_counts = Counter()
        manufacturer_counts = Counter()

        for event in results:
            event_type = event.get("event_type", "Unknown")
            event_type_counts[event_type] += 1

            devices = event.get("device", [])
            brand_name = devices[0].get("brand_name") if devices else None
            manufacturer = devices[0].get("manufacturer_d_name") if devices else None
            product_code = devices[0].get("device_report_product_code") if devices else None

            if manufacturer:
                manufacturer_counts[manufacturer] += 1

            records.append(AdverseEventRecord(
                mdr_report_key=event.get("mdr_report_key"),
                event_type=event_type,
                date_received=event.get("date_received", ""),
                brand_name=brand_name,
                manufacturer_name=manufacturer,
                product_code=product_code,
            ))

        return EventSearchResult(
            query=query,
            date_from=date_from or None,
            date_to=date_to or None,
            total_found=total,
            records=records,
            event_type_counts=dict(event_type_counts),
            manufacturer_counts=dict(manufacturer_counts)
        )

    async def _arun(self, query: str = "", product_codes: list[str] = None, date_from: str = "", date_to: str = "", limit: int = 100, country: str = "") -> str:
        """Async version using httpx for non-blocking HTTP calls."""
        try:
            search = self._build_search(query, product_codes or [], country, date_from, date_to)
            data = await self._client.aget_paginated(
                "device/event.json",
                params={"search": search},
                limit=min(limit, 500),
                sort="date_received:desc",
            )
            search_desc = (", ".join(product_codes) if product_codes else "") or query or country
            self._last_structured_result = self._to_structured(search_desc, date_from, date_to, data)
            return self._format_results(search_desc, data)

        except ValueError as e:
            self._last_structured_result = None
            return f"Error: {e}"
        except Exception as e:
            self._last_structured_result = None
            return f"Error searching events: {str(e)}"

    def _build_search(
        self,
        query: str,
        product_codes: list[str],
        country: str,
        date_from: str,
        date_to: str,
    ) -> str:
        search_parts = []

        # PRIORITY 1: Use product codes for precise matching (if provided)
        if product_codes:
            # Build OR query for multiple product codes
            code_queries = [f'device.device_report_product_code:"{code.upper()}"' for code in product_codes]
            search_parts.append(f'({" OR ".join(code_queries)})')

        # PRIORITY 2: Fallback to text search if no product codes
        elif query:
            # Check if query itself is a 3-letter product code
            if re.match(r"^[A-Z]{3}$", query.upper()):
                search_parts.append(f'device.device_report_product_code:"{query.upper()}"')
            else:
                safe_query = query.replace('"', '\\"')
                search_parts.append(
                    f'(device.brand_name:"{safe_query}" OR device.generic_name:"{safe_query}" OR device.manufacturer_d_name:"{safe_query}")'
                )

        if country:
            country_code = self._normalize_country(country)
            search_parts.append(f'device.manufacturer_d_country:"{country_code}"')

        if date_from and date_to:
            self._validate_date(date_from)
            self._validate_date(date_to)
            search_parts.append(f"date_received:[{date_from} TO {date_to}]")
        elif date_from:
            self._validate_date(date_from)
            search_parts.append(f"date_received:[{date_from} TO *]")
        elif date_to:
            self._validate_date(date_to)
            search_parts.append(f"date_received:[* TO {date_to}]")

        if not search_parts:
            raise ValueError("Must provide query, country, or product_code parameter.")

        return " AND ".join(search_parts)

    def _validate_date(self, date_str: str) -> None:
        if date_str and not re.match(r"^\d{8}$", date_str):
            raise ValueError("Dates must be in YYYYMMDD format.")
