"""
Recalls Tool - Search FDA device recalls.
"""
from typing import Type, Optional
from collections import Counter
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ...models.responses import RecallSearchResult, RecallRecord
from ...openfda_client import OpenFDAClient


class SearchRecallsInput(BaseModel):
    query: str = Field(default="", description="Device name or manufacturer name to search for in recalls")
    product_codes: list[str] = Field(default_factory=list, description="FDA product codes to search for (e.g., ['FXX', 'MSH']). Use this for precise searches after resolving device names.")
    date_from: str = Field(default="", description="Start date in YYYYMMDD format")
    date_to: str = Field(default="", description="End date in YYYYMMDD format")
    limit: int = Field(default=100, description="Maximum number of results")
    search_field: str = Field(default="both", description="Which field to search: 'product' (device name), 'firm' (manufacturer), or 'both'")
    country: str = Field(default="", description="Filter by recalling firm's country (e.g., 'China', 'Germany', 'United States')")


class SearchRecallsTool(BaseTool):
    name: str = "search_recalls"
    description: str = """Search FDA device recalls by product codes (PREFERRED), product description, firm name, or country.

    Parameters:
    - product_codes: List of FDA product codes (e.g., ['FXX', 'MSH']). ALWAYS use this when you have product codes from resolve_device.
    - query: Device name or manufacturer name (fallback for text search)
    - search_field: 'product', 'firm', or 'both' (default)
    - country: Filter by recalling firm's country (e.g., 'China', 'Germany')

    IMPORTANT: If you called resolve_device and got product codes, pass them to product_codes parameter for precise results.

    Examples:
    - BEST: After resolving "mask" -> FXX, MSH: search_recalls(product_codes=["FXX", "MSH"])
    - By product codes and country: search_recalls(product_codes=["FXX"], country="China")
    - Fallback text search: search_recalls(query="mask", search_field="product")
    - Recalls by firm: search_recalls(query="Medtronic", search_field="firm")

    Class I recalls are the most serious (risk of death or serious injury)."""
    args_schema: Type[BaseModel] = SearchRecallsInput

    _api_key: Optional[str] = None
    _last_structured_result: Optional[RecallSearchResult] = None
    _client: OpenFDAClient

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key
        self._client = OpenFDAClient(api_key=api_key)

    def get_last_structured_result(self) -> Optional[RecallSearchResult]:
        return self._last_structured_result

    def _run(self, query: str = "", product_codes: list[str] = None, date_from: str = "", date_to: str = "", limit: int = 100, search_field: str = "both", country: str = "") -> str:
        try:
            use_recall_endpoint = bool(product_codes)
            search = self._build_search(query, product_codes or [], search_field, country, date_from, date_to, use_recall_endpoint)

            if use_recall_endpoint:
                endpoint = "device/recall.json"
                sort_field = "event_date_initiated:desc"
            else:
                endpoint = "device/enforcement.json"
                sort_field = "recall_initiation_date:desc"

            data = self._client.get_paginated(
                endpoint,
                params={"search": search},
                limit=min(limit, 500),
                sort=sort_field,
            )

            self._last_structured_result = self._to_structured(query, date_from, date_to, data, use_recall_endpoint)
            return self._format_results(query or ",".join(product_codes or []) or country, data, use_recall_endpoint)

        except ValueError as e:
            self._last_structured_result = None
            return f"Error: {e}"
        except Exception as e:
            self._last_structured_result = None
            return f"Error searching recalls: {str(e)}"

    def _to_structured(self, query: str, date_from: str, date_to: str, data: dict, use_recall_endpoint: bool = False) -> RecallSearchResult:
        results = data.get("results", []) or []
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        records = []
        class_counts = Counter()
        status_counts = Counter()
        firm_counts = Counter()

        for r in (results or []):
            if use_recall_endpoint:
                recall_class = "N/A"
                status = r.get("recall_status", "Unknown")
                recall_number = r.get("product_res_number", "")
                event_id = r.get("res_event_number")
                initiation_date = r.get("event_date_initiated", "")
            else:
                recall_class = r.get("classification", "Unknown")
                status = r.get("status", "Unknown")
                recall_number = r.get("recall_number", "")
                event_id = r.get("event_id")
                initiation_date = r.get("recall_initiation_date", "")

            class_counts[recall_class] += 1
            status_counts[status] += 1
            firm_counts[r.get("recalling_firm", "Unknown")] += 1

            records.append(RecallRecord(
                recall_number=recall_number,
                event_id=event_id,
                recalling_firm=r.get("recalling_firm", ""),
                product_description=r.get("product_description", ""),
                reason_for_recall=r.get("reason_for_recall", ""),
                classification=recall_class,
                status=status,
                recall_initiation_date=initiation_date,
                voluntary_mandated=r.get("voluntary_mandated"),
                distribution_pattern=r.get("distribution_pattern")
            ))

        return RecallSearchResult(
            query=query,
            date_from=date_from or None,
            date_to=date_to or None,
            total_found=total,
            records=records,
            class_counts=dict(class_counts),
            status_counts=dict(status_counts),
            firm_counts=dict(firm_counts)
        )

    def _format_results(self, query: str, data: dict, use_recall_endpoint: bool = False) -> str:
        results = data.get("results", []) or []
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        if not results:
            return f"No recalls found for '{query}'."

        lines = [f"Found {total} recalls for '{query}' (showing {len(results)}):\n"]

        class_counts = Counter()
        status_counts = Counter()
        firms = Counter()

        for recall in (results or []):
            if use_recall_endpoint:
                status = recall.get("recall_status", "Unknown")
            else:
                recall_class = recall.get("classification", "Unknown")
                class_counts[recall_class] += 1
                status = recall.get("status", "Unknown")

            status_counts[status] += 1
            firm = recall.get("recalling_firm", "Unknown")
            firms[firm] += 1

        if not use_recall_endpoint:
            lines.append("RECALL CLASSIFICATIONS:")
            for cls, count in sorted(class_counts.items()):
                severity = ""
                if cls == "Class I":
                    severity = " (most serious - risk of death/injury)"
                elif cls == "Class II":
                    severity = " (moderate risk)"
                elif cls == "Class III":
                    severity = " (unlikely to cause adverse health)"
                lines.append(f"  {cls}: {count}{severity}")

        lines.append("\nRECALL STATUS:")
        for status, count in status_counts.most_common():
            lines.append(f"  {status}: {count}")

        if len(firms) > 1:
            lines.append("\nRECALLING FIRMS:")
            for firm, count in firms.most_common(5):
                lines.append(f"  {firm}: {count}")

        lines.append("\nRECENT RECALLS:")
        for i, recall in enumerate((results or [])[:5], 1):
            if use_recall_endpoint:
                date_raw = recall.get("event_date_initiated", "")
                date = date_raw if date_raw else "Unknown"
                recall_class = ""
            else:
                date_raw = recall.get("recall_initiation_date", "")
                date = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}" if len(date_raw) == 8 else date_raw or "Unknown"
                recall_class = recall.get("classification", "")

            firm = recall.get("recalling_firm", "Unknown")
            product = recall.get("product_description", "Unknown")[:60]
            reason = recall.get("reason_for_recall", "Not specified")[:80]

            class_str = f" | {recall_class}" if recall_class else ""
            lines.append(f"  {i}. Date: {date}{class_str}")
            lines.append(f"     Firm: {firm}")
            lines.append(f"     Product: {product}")
            lines.append(f"     Reason: {reason}")

        return "\n".join(lines)

    async def _arun(self, query: str = "", product_codes: list[str] = None, date_from: str = "", date_to: str = "", limit: int = 100, search_field: str = "both", country: str = "") -> str:
        """Async version using httpx for non-blocking HTTP calls."""
        try:
            use_recall_endpoint = bool(product_codes)
            search = self._build_search(query, product_codes or [], search_field, country, date_from, date_to, use_recall_endpoint)

            if use_recall_endpoint:
                endpoint = "device/recall.json"
                sort_field = "event_date_initiated:desc"
            else:
                endpoint = "device/enforcement.json"
                sort_field = "recall_initiation_date:desc"

            data = await self._client.aget_paginated(
                endpoint,
                params={"search": search},
                limit=min(limit, 500),
                sort=sort_field,
            )

            self._last_structured_result = self._to_structured(query, date_from, date_to, data, use_recall_endpoint)
            result = self._format_results(query or ",".join(product_codes or []) or country, data, use_recall_endpoint)
            return result

        except ValueError as e:
            self._last_structured_result = None
            return f"Error: {e}"
        except Exception as e:
            self._last_structured_result = None
            return f"Error searching recalls: {str(e)}"

    def _build_search(
        self,
        query: str,
        product_codes: list[str],
        search_field: str,
        country: str,
        date_from: str,
        date_to: str,
        use_recall_endpoint: bool = False,
    ) -> str:
        search_parts = []

        if product_codes:
            code_queries = [f'product_code:"{code}"' for code in product_codes]
            search_parts.append(f'({" OR ".join(code_queries)})')

        elif query:
            safe_query = query.replace('"', '\\"')
            if search_field == "firm":
                search_parts.append(f'recalling_firm:"{safe_query}"')
            elif search_field == "product":
                search_parts.append(f'product_description:"{safe_query}"')
            else:
                search_parts.append(
                    f'(product_description:"{safe_query}" OR recalling_firm:"{safe_query}")'
                )

        if country and not use_recall_endpoint:
            search_parts.append(f'country:"{country}"')

        if not use_recall_endpoint:
            if date_from and date_to:
                self._validate_date(date_from)
                self._validate_date(date_to)
                search_parts.append(f"recall_initiation_date:[{date_from} TO {date_to}]")
            elif date_from:
                self._validate_date(date_from)
                search_parts.append(f"recall_initiation_date:[{date_from} TO *]")
            elif date_to:
                self._validate_date(date_to)
                search_parts.append(f"recall_initiation_date:[* TO {date_to}]")

        if not search_parts:
            raise ValueError("Must provide either product_codes, query, or country parameter.")

        return " AND ".join(search_parts)

    def _validate_date(self, date_str: str) -> None:
        if date_str and (not date_str.isdigit() or len(date_str) != 8):
            raise ValueError("Dates must be in YYYYMMDD format.")
