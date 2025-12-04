"""
PMA Approvals Tool - Search FDA Premarket Approval (PMA) database.
"""
from typing import Type, Optional
from collections import Counter
import time
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import requests
import httpx


class SearchPMAInput(BaseModel):
    query: str = Field(description="Device trade name, generic name, applicant, or PMA number")
    date_from: str = Field(default="", description="Start date in YYYYMMDD format")
    date_to: str = Field(default="", description="End date in YYYYMMDD format")
    limit: int = Field(default=100, description="Maximum number of results")


class SearchPMATool(BaseTool):
    name: str = "search_pma"
    description: str = """Search FDA Premarket Approval (PMA) database.
    PMA is the most stringent FDA regulatory pathway for Class III high-risk devices.
    Requires clinical trial data to demonstrate safety and effectiveness.
    Use this to find approved high-risk devices, approval dates, and clinical study requirements."""
    args_schema: Type[BaseModel] = SearchPMAInput

    _api_key: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key

    def _run(self, query: str, date_from: str = "", date_to: str = "", limit: int = 100) -> str:
        try:
            url = "https://api.fda.gov/device/pma.json"

            if query.upper().startswith("P") and len(query) >= 6:
                search_parts = [f'pma_number:"{query.upper()}"']
            else:
                search_parts = [f'(trade_name:"{query}" OR generic_name:"{query}" OR applicant:"{query}")']

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
                return f"No PMA approvals found for '{query}'."
            return f"FDA API error: {str(e)}"
        except Exception as e:
            return f"Error searching PMA approvals: {str(e)}"

    def _format_results(self, query: str, data: dict) -> str:
        results = data.get("results", [])
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        if not results:
            return f"No PMA approvals found for '{query}'."

        lines = [f"Found {total} PMA records for '{query}' (showing {len(results)}):\n"]

        applicants = Counter()
        decisions = Counter()
        supplements = 0

        for pma in results:
            applicant = pma.get("applicant", "Unknown")
            applicants[applicant] += 1

            decision = pma.get("decision_code", "Unknown")
            decisions[decision] += 1

            supplements += len(pma.get("supplements", []))

        lines.append("DECISION TYPES:")
        for decision, count in decisions.most_common():
            desc = {
                "APPR": "Approved",
                "APCM": "Approved with Conditions",
                "DENY": "Denied",
                "WTDR": "Withdrawn"
            }.get(decision, decision)
            lines.append(f"  {desc}: {count}")

        if supplements > 0:
            lines.append(f"\nTotal supplements filed: {supplements}")

        if len(applicants) > 1:
            lines.append("\nTOP APPLICANTS:")
            for applicant, count in applicants.most_common(5):
                lines.append(f"  {applicant}: {count}")

        lines.append("\nRECENT PMA RECORDS:")
        for i, pma in enumerate(results[:5], 1):
            pma_number = pma.get("pma_number", "Unknown")
            date = pma.get("decision_date", "Unknown")
            applicant = pma.get("applicant", "Unknown")
            trade_name = pma.get("trade_name", "Unknown")[:40]
            generic_name = pma.get("generic_name", "")[:40]
            decision = pma.get("decision_code", "")
            num_supplements = len(pma.get("supplements", []))

            lines.append(f"  {i}. {pma_number} - {date} ({decision})")
            lines.append(f"     Trade Name: {trade_name}")
            if generic_name:
                lines.append(f"     Generic: {generic_name}")
            lines.append(f"     Applicant: {applicant}")
            if num_supplements:
                lines.append(f"     Supplements: {num_supplements}")

        return "\n".join(lines)

    async def _arun(self, query: str, date_from: str = "", date_to: str = "", limit: int = 100) -> str:
        """Async version using httpx for non-blocking HTTP calls."""
        start_time = time.time()
        try:
            url = "https://api.fda.gov/device/pma.json"

            if query.upper().startswith("P") and len(query) >= 6:
                search_parts = [f'pma_number:"{query.upper()}"']
            else:
                search_parts = [f'(trade_name:"{query}" OR generic_name:"{query}" OR applicant:"{query}")']

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
                return f"No PMA approvals found for '{query}'."
            return f"FDA API error: {str(e)}"
        except Exception as e:
            return f"Error searching PMA approvals: {str(e)}"
