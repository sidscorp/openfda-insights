"""
510(k) Clearances Tool - Search FDA 510(k) premarket notifications.
"""
from typing import Type, Optional
from collections import Counter
import time
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import requests
import httpx


class Search510kInput(BaseModel):
    query: str = Field(description="Device name, applicant/company name, or K number")
    date_from: str = Field(default="", description="Start date in YYYYMMDD format")
    date_to: str = Field(default="", description="End date in YYYYMMDD format")
    limit: int = Field(default=100, description="Maximum number of results")


class Search510kTool(BaseTool):
    name: str = "search_510k"
    description: str = """Search FDA 510(k) premarket notifications (clearances).
    510(k) clearances demonstrate substantial equivalence to a predicate device.
    Use this to find cleared devices, clearance dates, applicants, and predicate devices.
    Can search by device name, company name, or K number (e.g., K201234)."""
    args_schema: Type[BaseModel] = Search510kInput

    _api_key: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key

    def _run(self, query: str, date_from: str = "", date_to: str = "", limit: int = 100) -> str:
        try:
            url = "https://api.fda.gov/device/510k.json"

            if query.upper().startswith("K") and len(query) >= 6:
                search_parts = [f'k_number:"{query.upper()}"']
            else:
                search_parts = [f'(device_name:"{query}" OR applicant:"{query}")']

            if date_from and date_to:
                search_parts.append(f'decision_date:[{date_from} TO {date_to}]')
            elif date_from:
                search_parts.append(f'decision_date:[{date_from} TO *]')
            elif date_to:
                search_parts.append(f'decision_date:[* TO {date_to}]')

            search = " AND ".join(search_parts)

            params = {
                "search": search,
                "limit": min(limit, 100),
                "sort": "decision_date:desc"
            }
            if self._api_key:
                params["api_key"] = self._api_key

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            return self._format_results(query, data)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return f"No 510(k) clearances found for '{query}'."
            return f"FDA API error: {str(e)}"
        except Exception as e:
            return f"Error searching 510(k) clearances: {str(e)}"

    def _format_results(self, query: str, data: dict) -> str:
        results = data.get("results", []) or []
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        if not results:
            return f"No 510(k) clearances found for '{query}'."

        lines = [f"Found {total} 510(k) clearances for '{query}' (showing {len(results)}):\n"]

        applicants = Counter()
        decisions = Counter()
        product_codes = Counter()

        for clearance in results:
            applicant = clearance.get("applicant", "Unknown")
            applicants[applicant] += 1

            decision = clearance.get("decision_description", clearance.get("decision_code", "Unknown"))
            decisions[decision] += 1

            openfda = clearance.get("openfda", {})
            for code in openfda.get("device_name", []):
                product_codes[code] += 1

        lines.append("DECISION OUTCOMES:")
        for decision, count in decisions.most_common():
            lines.append(f"  {decision}: {count}")

        if len(applicants) > 1:
            lines.append("\nTOP APPLICANTS:")
            for applicant, count in applicants.most_common(5):
                lines.append(f"  {applicant}: {count}")

        lines.append("\nRECENT CLEARANCES:")
        for i, clearance in enumerate(results[:5], 1):
            k_number = clearance.get("k_number", "Unknown")
            date = clearance.get("decision_date", "Unknown")
            applicant = clearance.get("applicant", "Unknown")
            device_name = clearance.get("device_name", "Unknown")[:50]
            decision = clearance.get("decision_description", clearance.get("decision_code", ""))

            lines.append(f"  {i}. {k_number} - {date}")
            lines.append(f"     Device: {device_name}")
            lines.append(f"     Applicant: {applicant}")
            lines.append(f"     Decision: {decision}")

        return "\n".join(lines)

    async def _arun(self, query: str, date_from: str = "", date_to: str = "", limit: int = 100) -> str:
        """Async version using httpx for non-blocking HTTP calls."""
        start_time = time.time()
        try:
            url = "https://api.fda.gov/device/510k.json"

            if query.upper().startswith("K") and len(query) >= 6:
                search_parts = [f'k_number:"{query.upper()}"']
            else:
                search_parts = [f'(device_name:"{query}" OR applicant:"{query}")']

            if date_from and date_to:
                search_parts.append(f'decision_date:[{date_from} TO {date_to}]')
            elif date_from:
                search_parts.append(f'decision_date:[{date_from} TO *]')
            elif date_to:
                search_parts.append(f'decision_date:[* TO {date_to}]')

            search = " AND ".join(search_parts)

            params = {
                "search": search,
                "limit": min(limit, 100),
                "sort": "decision_date:desc"
            }
            if self._api_key:
                params["api_key"] = self._api_key

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            elapsed_ms = (time.time() - start_time) * 1000
            result = self._format_results(query, data)
            return f"{result}\n\n[Query completed in {elapsed_ms:.0f}ms]"

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return f"No 510(k) clearances found for '{query}'."
            return f"FDA API error: {str(e)}"
        except Exception as e:
            return f"Error searching 510(k) clearances: {str(e)}"
