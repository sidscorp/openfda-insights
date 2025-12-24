"""
Classifications Tool - Search FDA device classification database.
"""
import asyncio
from typing import Type, Optional, Callable, Dict, Any
from collections import Counter
import re
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ...openfda_client import OpenFDAClient, HybridAggregationResult

CLASSIFICATION_SERVER_FIELDS = ["medical_specialty_description.exact", "device_class.exact"]
CLASSIFICATION_CLIENT_EXTRACTORS: Dict[str, Callable[[Dict[str, Any]], Optional[str]]] = {
    "device_class": lambda c: c.get("device_class"),
    "medical_specialty": lambda c: (c.get("openfda") or {}).get("medical_specialty_description", [""])[0] if isinstance((c.get("openfda") or {}).get("medical_specialty_description"), list) else (c.get("openfda") or {}).get("medical_specialty_description"),
    "submission_type": lambda c: c.get("submission_type_id"),
}


class SearchClassificationsInput(BaseModel):
    query: str = Field(description="Device name, product code (e.g., FXX), or regulation number")
    limit: int = Field(default=50, description="Maximum number of results")


class SearchClassificationsTool(BaseTool):
    name: str = "search_classifications"
    description: str = """Search FDA device classification database.
    Returns device class (I, II, or III), product codes, regulation numbers, and submission requirements.
    Class I: Low risk, general controls. Class II: Moderate risk, special controls.
    Class III: High risk, requires PMA approval.
    Use this to understand regulatory requirements for device types."""
    args_schema: Type[BaseModel] = SearchClassificationsInput

    _client: OpenFDAClient
    _api_key: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key
        self._client = OpenFDAClient(api_key=api_key)

    def _build_search(self, query: str) -> str:
        if re.match(r'^[A-Z]{3}$', query.upper()):
            return f'product_code:"{query.upper()}"'
        elif re.match(r'^\d+\.\d+$', query):
            return f'regulation_number:"{query}"'
        else:
            return f'device_name:"{query}"'

    def _run(self, query: str, limit: int = 50) -> str:
        return asyncio.run(self._arun(query, limit))

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
            return f"No classifications found for '{query}'."

        agg_label = hybrid_result.get_label() if hybrid_result else "sample only"
        lines = [f"Found {total} device classifications for '{query}'. Statistics from {agg_label}. Showing {len(results)} results:\n"]

        class_key = next(
            (k for k in ["device_class.exact", "device_class"] if k in aggregations),
            None,
        )
        if class_key:
            lines.append(f"DEVICE CLASSES ({agg_label}):")
            for item in aggregations[class_key]:
                cls = f"Class {item['term']}"
                count = item['count']
                risk_level = ""
                if item['term'] == "1":
                    risk_level = " (Low risk - general controls)"
                elif item['term'] == "2":
                    risk_level = " (Moderate risk - special controls)"
                elif item['term'] == "3":
                    risk_level = " (High risk - PMA required)"
                lines.append(f"  {cls}: {count}{risk_level}")
        else:
            class_counts: Counter = Counter()
            for classification in results:
                device_class = classification.get("device_class", "Unknown")
                class_counts[f"Class {device_class}"] += 1
            lines.append("DEVICE CLASSES (sample only):")
            for cls, count in sorted(class_counts.items()):
                risk_level = ""
                if cls == "Class 1":
                    risk_level = " (Low risk - general controls)"
                elif cls == "Class 2":
                    risk_level = " (Moderate risk - special controls)"
                elif cls == "Class 3":
                    risk_level = " (High risk - PMA required)"
                lines.append(f"  {cls}: {count}{risk_level}")

        specialty_key = next(
            (k for k in ["medical_specialty_description.exact", "medical_specialty"] if k in aggregations),
            None,
        )
        if specialty_key:
            specialty_items = aggregations[specialty_key][:5]
            if specialty_items:
                lines.append(f"\nMEDICAL SPECIALTIES ({agg_label}):")
                for item in specialty_items:
                    lines.append(f"  {item['term']}: {item['count']}")

        submission_key = "submission_type" if "submission_type" in aggregations else None
        type_names = {
            "1": "510(k) Required",
            "2": "510(k) Exempt",
            "3": "PMA Required",
            "4": "Transitional",
            "5": "Not Classified",
            "7": "HDE Required"
        }
        if submission_key:
            lines.append(f"\nSUBMISSION TYPES ({agg_label}):")
            for item in aggregations[submission_key][:10]:
                type_name = type_names.get(str(item['term']), str(item['term']))
                lines.append(f"  {type_name}: {item['count']}")
        else:
            submission_types: Counter = Counter()
            for classification in results:
                sub_type = classification.get("submission_type_id", "Unknown")
                submission_types[sub_type] += 1
            lines.append("\nSUBMISSION TYPES (sample):")
            for sub_type, count in submission_types.most_common():
                type_name = type_names.get(str(sub_type), str(sub_type))
                lines.append(f"  {type_name}: {count}")

        lines.append("\nCLASSIFICATION DETAILS:")
        for i, classification in enumerate(results[:5], 1):
            device_name = classification.get("device_name", "Unknown")[:50]
            device_class = classification.get("device_class", "?")
            product_code = classification.get("product_code", "N/A")
            regulation = classification.get("regulation_number", "N/A")
            definition = classification.get("definition", "")[:100]

            openfda = classification.get("openfda", {})
            specialty = openfda.get("medical_specialty_description", ["N/A"])
            if isinstance(specialty, list):
                specialty = specialty[0] if specialty else "N/A"

            lines.append(f"  {i}. {device_name}")
            lines.append(f"     Class: {device_class} | Product Code: {product_code}")
            lines.append(f"     Regulation: {regulation}")
            lines.append(f"     Specialty: {specialty}")
            if definition:
                lines.append(f"     Definition: {definition}...")

        return "\n".join(lines)

    async def _arun(self, query: str, limit: int = 50) -> str:
        """Async version using httpx for non-blocking HTTP calls with hybrid aggregation."""
        try:
            search = self._build_search(query)
            endpoint = "device/classification.json"

            hybrid_result = await self._client.aget_hybrid_aggregations(
                endpoint=endpoint,
                search=search,
                server_count_fields=CLASSIFICATION_SERVER_FIELDS,
                client_field_extractors=CLASSIFICATION_CLIENT_EXTRACTORS,
                max_client_records=5000,
            )

            data = await self._client.aget(
                endpoint,
                params={"search": search, "limit": min(limit, 100)}
            )

            return self._format_results(query, data, hybrid_result)
        except Exception as e:
            if "404" in str(e) or "No results" in str(e):
                return f"No classifications found for '{query}'."
            return f"Error searching classifications: {str(e)}"
