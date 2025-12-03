"""
Recalls Tool - Search FDA device recalls.
"""
from typing import Type, Optional
from collections import Counter
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import requests


class SearchRecallsInput(BaseModel):
    query: str = Field(description="Device name, product code, or company name")
    date_from: str = Field(default="", description="Start date in YYYYMMDD format")
    date_to: str = Field(default="", description="End date in YYYYMMDD format")
    limit: int = Field(default=100, description="Maximum number of results")


class SearchRecallsTool(BaseTool):
    name: str = "search_recalls"
    description: str = """Search FDA device recalls.
    Use this to find recalled medical devices, recall classifications (Class I, II, III),
    and reasons for recalls. Can search by device name, product description, or company.
    Class I recalls are the most serious (risk of death or serious injury)."""
    args_schema: Type[BaseModel] = SearchRecallsInput

    _api_key: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key

    def _run(self, query: str, date_from: str = "", date_to: str = "", limit: int = 100) -> str:
        try:
            url = "https://api.fda.gov/device/recall.json"
            search_parts = [f'(product_description:"{query}" OR recalling_firm:"{query}")']

            if date_from and date_to:
                search_parts.append(f'event_date_initiated:[{date_from} TO {date_to}]')
            elif date_from:
                search_parts.append(f'event_date_initiated:[{date_from} TO *]')
            elif date_to:
                search_parts.append(f'event_date_initiated:[* TO {date_to}]')

            search = " AND ".join(search_parts)

            params = {
                "search": search,
                "limit": min(limit, 100),
                "sort": "event_date_initiated:desc"
            }
            if self._api_key:
                params["api_key"] = self._api_key

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            return self._format_results(query, data)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return f"No recalls found for '{query}'."
            return f"FDA API error: {str(e)}"
        except Exception as e:
            return f"Error searching recalls: {str(e)}"

    def _format_results(self, query: str, data: dict) -> str:
        results = data.get("results", [])
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        if not results:
            return f"No recalls found for '{query}'."

        lines = [f"Found {total} recalls for '{query}' (showing {len(results)}):\n"]

        class_counts = Counter()
        status_counts = Counter()
        firms = Counter()

        for recall in results:
            recall_class = recall.get("openfda", {}).get("device_class", "Unknown")
            if isinstance(recall_class, list):
                recall_class = recall_class[0] if recall_class else "Unknown"
            class_counts[f"Class {recall_class}"] += 1

            status = recall.get("status", "Unknown")
            status_counts[status] += 1

            firm = recall.get("recalling_firm", "Unknown")
            firms[firm] += 1

        lines.append("RECALL CLASSIFICATIONS:")
        for cls, count in sorted(class_counts.items()):
            severity = ""
            if "I" in cls and "II" not in cls:
                severity = " (most serious - risk of death/injury)"
            elif "II" in cls and "III" not in cls:
                severity = " (moderate risk)"
            elif "III" in cls:
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
        for i, recall in enumerate(results[:5], 1):
            date = recall.get("event_date_initiated", "Unknown")
            firm = recall.get("recalling_firm", "Unknown")
            product = recall.get("product_description", "Unknown")[:60]
            reason = recall.get("reason_for_recall", "Not specified")[:80]

            lines.append(f"  {i}. Date: {date}")
            lines.append(f"     Firm: {firm}")
            lines.append(f"     Product: {product}")
            lines.append(f"     Reason: {reason}")

        return "\n".join(lines)

    async def _arun(self, query: str, date_from: str = "", date_to: str = "", limit: int = 100) -> str:
        return self._run(query, date_from, date_to, limit)
