"""
510(k) Clearances Tool - Search FDA 510(k) premarket notifications.
"""
from typing import Type, Optional
from collections import Counter
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ...openfda_client import OpenFDAClient


class Search510kInput(BaseModel):
    query: str = Field(default="", description="Device name, applicant/company name, or K number")
    product_codes: list[str] = Field(default_factory=list, description="FDA product codes to search for (e.g., ['FXX', 'MSH']). Use this for precise searches after resolving device names.")
    date_from: str = Field(default="", description="Start date in YYYYMMDD format")
    date_to: str = Field(default="", description="End date in YYYYMMDD format")
    limit: int = Field(default=100, description="Maximum number of results")


class Search510kTool(BaseTool):
    name: str = "search_510k"
    description: str = """Search FDA 510(k) premarket notifications (clearances).

    Parameters:
    - product_codes: List of FDA product codes (e.g., ['FXX', 'MSH']). ALWAYS use this when you have product codes from resolve_device.
    - query: Device name, company name, or K number (fallback for text search)

    IMPORTANT: If you called resolve_device and got product codes, pass them to product_codes parameter for precise results.

    510(k) clearances demonstrate substantial equivalence to a predicate device.
    Use this to find cleared devices, clearance dates, applicants, and predicate devices.

    Examples:
    - BEST: After resolving "mask" -> FXX, MSH: search_510k(product_codes=["FXX", "MSH"])
    - By K number: search_510k(query="K201234")
    - By company: search_510k(query="Medtronic")"""
    args_schema: Type[BaseModel] = Search510kInput

    _client: OpenFDAClient
    _api_key: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key
        self._client = OpenFDAClient(api_key=api_key)

    def _build_search(self, query: str, product_codes: list[str], date_from: str, date_to: str) -> str:
        search_parts = []

        if product_codes:
            code_queries = [f'product_code:"{code}"' for code in product_codes]
            search_parts.append(f'({" OR ".join(code_queries)})')
        elif query:
            if query.upper().startswith("K") and len(query) >= 6:
                search_parts.append(f'k_number:"{query.upper()}"')
            else:
                search_parts.append(f'(device_name:"{query}" OR applicant:"{query}")')

        if date_from and date_to:
            search_parts.append(f'decision_date:[{date_from} TO {date_to}]')
        elif date_from:
            search_parts.append(f'decision_date:[{date_from} TO *]')
        elif date_to:
            search_parts.append(f'decision_date:[* TO {date_to}]')

        if not search_parts:
            raise ValueError("Must provide either product_codes or query parameter.")

        return " AND ".join(search_parts)

    def _run(self, query: str = "", product_codes: list[str] = None, date_from: str = "", date_to: str = "", limit: int = 100) -> str:
        try:
            search = self._build_search(query, product_codes or [], date_from, date_to)
            data = self._client.get(
                "device/510k.json",
                params={"search": search, "limit": min(limit, 100)},
                sort="decision_date:desc"
            )
            return self._format_results(query, data)
        except ValueError as e:
            return str(e)
        except Exception as e:
            if "404" in str(e) or "No results" in str(e):
                return f"No 510(k) clearances found for '{query}'."
            return f"Error searching 510(k) clearances: {str(e)}"

    def _format_results(self, query: str, data: dict) -> str:
        results = data.get("results", []) or []
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        if not results:
            return f"No 510(k) clearances found for '{query}'."

        lines = [f"Found {total} 510(k) clearances for '{query}' (showing {len(results)}):\n"]

        applicants = Counter()
        decisions = Counter()
        product_codes_counter = Counter()

        for clearance in results:
            applicant = clearance.get("applicant", "Unknown")
            applicants[applicant] += 1

            decision = clearance.get("decision_description", clearance.get("decision_code", "Unknown"))
            decisions[decision] += 1

            openfda = clearance.get("openfda", {})
            for code in openfda.get("device_name", []):
                product_codes_counter[code] += 1

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

    async def _arun(self, query: str = "", product_codes: list[str] = None, date_from: str = "", date_to: str = "", limit: int = 100) -> str:
        try:
            search = self._build_search(query, product_codes or [], date_from, date_to)
            data = await self._client.aget(
                "device/510k.json",
                params={"search": search, "limit": min(limit, 100)},
                sort="decision_date:desc"
            )
            return self._format_results(query, data)
        except ValueError as e:
            return str(e)
        except Exception as e:
            if "404" in str(e) or "No results" in str(e):
                return f"No 510(k) clearances found for '{query}'."
            return f"Error searching 510(k) clearances: {str(e)}"
