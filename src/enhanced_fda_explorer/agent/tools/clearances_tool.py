"""
510(k) Clearances Tool - Search FDA 510(k) premarket notifications.
"""
import asyncio
import json
from typing import Type, Optional, Callable, Dict, Any
from collections import Counter
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, validator

from ...openfda_client import OpenFDAClient, HybridAggregationResult

CLEARANCES_SERVER_FIELDS = ["advisory_committee_description.exact", "decision.exact"]
CLEARANCES_CLIENT_EXTRACTORS: Dict[str, Callable[[Dict[str, Any]], Optional[str]]] = {
    "decision": lambda c: c.get("decision_description") or c.get("decision_code"),
    "advisory_committee": lambda c: c.get("advisory_committee_description"),
    "applicant": lambda c: c.get("applicant"),
}


class Search510kInput(BaseModel):
    query: str = Field(default="", description="Device name, applicant/company name, or K number")
    product_codes: list[str] = Field(default_factory=list, description="FDA product codes to search for (e.g., ['FXX', 'MSH']). Use this for precise searches after resolving device names.")
    date_from: str = Field(default="", description="Start date in YYYYMMDD format")
    date_to: str = Field(default="", description="End date in YYYYMMDD format")
    limit: int = Field(default=100, description="Maximum number of results")

    @validator("product_codes", pre=True)
    def parse_product_codes(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            return [v] if v else []
        return v


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
        return asyncio.run(self._arun(query, product_codes, date_from, date_to, limit))

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
            return f"No 510(k) clearances found for '{query}'."

        agg_label = hybrid_result.get_label() if hybrid_result else "sample only"
        lines = [f"Found {total} 510(k) clearances for '{query}'. Statistics from {agg_label}. Showing {len(results)} most recent:\n"]

        decision_key = next(
            (k for k in ["decision.exact", "decision"] if k in aggregations),
            None,
        )
        if decision_key:
            lines.append(f"DECISION OUTCOMES ({agg_label}):")
            for item in aggregations[decision_key][:10]:
                lines.append(f"  {item['term']}: {item['count']}")
        else:
            decisions: Counter = Counter()
            for clearance in results:
                decision = clearance.get("decision_description", clearance.get("decision_code", "Unknown"))
                decisions[decision] += 1
            lines.append("DECISION OUTCOMES (sample only):")
            for decision, count in decisions.most_common():
                lines.append(f"  {decision}: {count}")

        committee_key = next(
            (k for k in ["advisory_committee_description.exact", "advisory_committee"] if k in aggregations),
            None,
        )
        if committee_key:
            committee_items = aggregations[committee_key][:5]
            if committee_items:
                lines.append(f"\nADVISORY COMMITTEES ({agg_label}):")
                for item in committee_items:
                    lines.append(f"  {item['term']}: {item['count']}")

        applicant_key = "applicant" if "applicant" in aggregations else None
        if applicant_key:
            applicant_items = aggregations[applicant_key][:5]
            if len(applicant_items) > 1:
                lines.append(f"\nTOP APPLICANTS ({agg_label}):")
                for item in applicant_items:
                    lines.append(f"  {item['term']}: {item['count']}")
        else:
            applicants: Counter = Counter()
            for clearance in results:
                applicant = clearance.get("applicant", "Unknown")
                applicants[applicant] += 1
            if len(applicants) > 1:
                lines.append("\nTOP APPLICANTS (sample):")
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
        """Async version using httpx for non-blocking HTTP calls with hybrid aggregation."""
        try:
            search = self._build_search(query, product_codes or [], date_from, date_to)
            endpoint = "device/510k.json"

            hybrid_result = await self._client.aget_hybrid_aggregations(
                endpoint=endpoint,
                search=search,
                server_count_fields=CLEARANCES_SERVER_FIELDS,
                client_field_extractors=CLEARANCES_CLIENT_EXTRACTORS,
                max_client_records=5000,
            )

            data = await self._client.aget(
                endpoint,
                params={"search": search, "limit": min(limit, 100)},
                sort="decision_date:desc"
            )

            return self._format_results(query, data, hybrid_result)
        except ValueError as e:
            return str(e)
        except Exception as e:
            if "404" in str(e) or "No results" in str(e):
                return f"No 510(k) clearances found for '{query}'."
            return f"Error searching 510(k) clearances: {str(e)}"
