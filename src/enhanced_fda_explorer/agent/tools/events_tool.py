"""
Events Tool - Search FDA adverse event reports (MAUDE database).
"""
from typing import Type, Optional
from collections import Counter
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import requests
import re


class SearchEventsInput(BaseModel):
    query: str = Field(description="Device name, product code (e.g., FXX), or company name")
    date_from: str = Field(default="", description="Start date in YYYYMMDD format")
    date_to: str = Field(default="", description="End date in YYYYMMDD format")
    limit: int = Field(default=100, description="Maximum number of results")


class SearchEventsTool(BaseTool):
    name: str = "search_events"
    description: str = """Search FDA adverse event reports (MAUDE database).
    Use this to find reported problems, injuries, malfunctions, or deaths associated with medical devices.
    Can search by device name, FDA product code (like FXX, MSH), or manufacturer name.
    Returns event types, outcomes, and device problem descriptions."""
    args_schema: Type[BaseModel] = SearchEventsInput

    _api_key: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key

    def _run(self, query: str, date_from: str = "", date_to: str = "", limit: int = 100) -> str:
        try:
            url = "https://api.fda.gov/device/event.json"
            search_parts = []

            if re.match(r'^[A-Z]{3}$', query.upper()):
                search_parts.append(f'device.device_report_product_code:"{query.upper()}"')
            else:
                search_parts.append(f'(device.brand_name:"{query}" OR device.generic_name:"{query}" OR device.manufacturer_d_name:"{query}")')

            if date_from and date_to:
                search_parts.append(f'date_received:[{date_from} TO {date_to}]')
            elif date_from:
                search_parts.append(f'date_received:[{date_from} TO *]')
            elif date_to:
                search_parts.append(f'date_received:[* TO {date_to}]')

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

    async def _arun(self, query: str, date_from: str = "", date_to: str = "", limit: int = 100) -> str:
        return self._run(query, date_from, date_to, limit)
