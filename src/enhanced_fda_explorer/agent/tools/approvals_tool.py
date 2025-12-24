"""
PMA Approvals Tool - Search FDA Premarket Approval (PMA) database.
"""
import asyncio
from typing import Type, Optional, Callable, Dict, Any
from collections import Counter
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ...openfda_client import OpenFDAClient, HybridAggregationResult

PMA_SERVER_FIELDS = ["advisory_committee_description.exact", "decision_code.exact"]
PMA_CLIENT_EXTRACTORS: Dict[str, Callable[[Dict[str, Any]], Optional[str]]] = {
    "decision_code": lambda p: p.get("decision_code"),
    "advisory_committee": lambda p: p.get("advisory_committee_description"),
    "applicant": lambda p: p.get("applicant"),
}


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

    _client: OpenFDAClient
    _api_key: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key
        self._client = OpenFDAClient(api_key=api_key)

    def _build_search(self, query: str, date_from: str, date_to: str) -> str:
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

        return " AND ".join(search_parts)

    def _run(self, query: str, date_from: str = "", date_to: str = "", limit: int = 100) -> str:
        return asyncio.run(self._arun(query, date_from, date_to, limit))

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
            return f"No PMA approvals found for '{query}'."

        agg_label = hybrid_result.get_label() if hybrid_result else "sample only"
        lines = [f"Found {total} PMA records for '{query}'. Statistics from {agg_label}. Showing {len(results)} most recent:\n"]

        decision_codes = {
            "APPR": "Approved",
            "APCM": "Approved with Conditions",
            "DENY": "Denied",
            "WTDR": "Withdrawn"
        }

        decision_key = next(
            (k for k in ["decision_code.exact", "decision_code"] if k in aggregations),
            None,
        )
        if decision_key:
            lines.append(f"DECISION TYPES ({agg_label}):")
            for item in aggregations[decision_key]:
                desc = decision_codes.get(item["term"], item["term"])
                lines.append(f"  {desc}: {item['count']}")
        else:
            decisions: Counter = Counter()
            for pma in results:
                decision = pma.get("decision_code", "Unknown")
                decisions[decision] += 1
            lines.append("DECISION TYPES (sample only):")
            for decision, count in decisions.most_common():
                desc = decision_codes.get(decision, decision)
                lines.append(f"  {desc}: {count}")

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

        supplements = 0
        for pma in results:
            supplements += len(pma.get("supplements", []))
        if supplements > 0:
            lines.append(f"\nTotal supplements filed (sample): {supplements}")

        applicant_key = "applicant" if "applicant" in aggregations else None
        if applicant_key:
            applicant_items = aggregations[applicant_key][:5]
            if len(applicant_items) > 1:
                lines.append(f"\nTOP APPLICANTS ({agg_label}):")
                for item in applicant_items:
                    lines.append(f"  {item['term']}: {item['count']}")
        else:
            applicants: Counter = Counter()
            for pma in results:
                applicant = pma.get("applicant", "Unknown")
                applicants[applicant] += 1
            if len(applicants) > 1:
                lines.append("\nTOP APPLICANTS (sample):")
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
        """Async version using httpx for non-blocking HTTP calls with hybrid aggregation."""
        try:
            search = self._build_search(query, date_from, date_to)
            endpoint = "device/pma.json"

            hybrid_result = await self._client.aget_hybrid_aggregations(
                endpoint=endpoint,
                search=search,
                server_count_fields=PMA_SERVER_FIELDS,
                client_field_extractors=PMA_CLIENT_EXTRACTORS,
                max_client_records=5000,
            )

            data = await self._client.aget(
                endpoint,
                params={"search": search, "limit": min(limit, 100)},
                sort="decision_date:desc"
            )

            return self._format_results(query, data, hybrid_result)
        except Exception as e:
            if "404" in str(e) or "No results" in str(e):
                return f"No PMA approvals found for '{query}'."
            return f"Error searching PMA approvals: {str(e)}"
