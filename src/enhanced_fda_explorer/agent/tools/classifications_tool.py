"""
Classifications Tool - Search FDA device classification database.
"""
from typing import Type, Optional
from collections import Counter
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import requests
import re


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

    _api_key: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key

    def _run(self, query: str, limit: int = 50) -> str:
        try:
            url = "https://api.fda.gov/device/classification.json"

            if re.match(r'^[A-Z]{3}$', query.upper()):
                search = f'product_code:"{query.upper()}"'
            elif re.match(r'^\d+\.\d+$', query):
                search = f'regulation_number:"{query}"'
            else:
                search = f'device_name:"{query}"'

            params = {
                "search": search,
                "limit": min(limit, 100)
            }
            if self._api_key:
                params["api_key"] = self._api_key

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            return self._format_results(query, data)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return f"No classifications found for '{query}'."
            return f"FDA API error: {str(e)}"
        except Exception as e:
            return f"Error searching classifications: {str(e)}"

    def _format_results(self, query: str, data: dict) -> str:
        results = data.get("results", [])
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        if not results:
            return f"No classifications found for '{query}'."

        lines = [f"Found {total} device classifications for '{query}':\n"]

        class_counts = Counter()
        submission_types = Counter()

        for classification in results:
            device_class = classification.get("device_class", "Unknown")
            class_counts[f"Class {device_class}"] += 1

            sub_type = classification.get("submission_type_id", "Unknown")
            submission_types[sub_type] += 1

        lines.append("DEVICE CLASSES:")
        for cls, count in sorted(class_counts.items()):
            risk_level = ""
            if cls == "Class 1":
                risk_level = " (Low risk - general controls)"
            elif cls == "Class 2":
                risk_level = " (Moderate risk - special controls)"
            elif cls == "Class 3":
                risk_level = " (High risk - PMA required)"
            lines.append(f"  {cls}: {count}{risk_level}")

        lines.append("\nSUBMISSION TYPES:")
        type_names = {
            "1": "510(k) Required",
            "2": "510(k) Exempt",
            "3": "PMA Required",
            "4": "Transitional",
            "5": "Not Classified",
            "7": "HDE Required"
        }
        for sub_type, count in submission_types.most_common():
            type_name = type_names.get(str(sub_type), sub_type)
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
        return self._run(query, limit)
