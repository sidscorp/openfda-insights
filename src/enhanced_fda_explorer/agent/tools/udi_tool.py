"""
UDI Tool - Search FDA Unique Device Identification database.
"""
from typing import Type, Optional
from collections import Counter
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import requests


class SearchUDIInput(BaseModel):
    query: str = Field(description="Device brand name, company name, or device identifier (DI)")
    limit: int = Field(default=50, description="Maximum number of results")


class SearchUDITool(BaseTool):
    name: str = "search_udi"
    description: str = """Search FDA Unique Device Identification (UDI) database.
    Returns device identifiers, labeler/manufacturer info, device characteristics,
    MRI safety information, and storage requirements.
    Use this to find specific device models and their identification information."""
    args_schema: Type[BaseModel] = SearchUDIInput

    _api_key: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._api_key = api_key

    def _run(self, query: str, limit: int = 50) -> str:
        try:
            url = "https://api.fda.gov/device/udi.json"

            search = f'(brand_name:"{query}" OR company_name:"{query}" OR version_or_model_number:"{query}")'

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
                return f"No UDI records found for '{query}'."
            return f"FDA API error: {str(e)}"
        except Exception as e:
            return f"Error searching UDI database: {str(e)}"

    def _format_results(self, query: str, data: dict) -> str:
        results = data.get("results", [])
        total = data.get("meta", {}).get("results", {}).get("total", 0)

        if not results:
            return f"No UDI records found for '{query}'."

        lines = [f"Found {total} UDI records for '{query}' (showing {len(results)}):\n"]

        companies = Counter()
        mri_safety = Counter()
        sterile = Counter()
        single_use = Counter()

        for device in results:
            company = device.get("company_name", "Unknown")
            companies[company] += 1

            mri = device.get("mri_safety", "Not specified")
            mri_safety[mri] += 1

            is_sterile = device.get("is_sterile", False)
            sterile["Sterile" if is_sterile else "Non-sterile"] += 1

            is_single = device.get("is_single_use", None)
            if is_single is not None:
                single_use["Single-use" if is_single else "Reusable"] += 1

        if len(companies) > 1:
            lines.append("MANUFACTURERS:")
            for company, count in companies.most_common(5):
                lines.append(f"  {company}: {count} devices")

        lines.append("\nMRI SAFETY:")
        for safety, count in mri_safety.most_common():
            lines.append(f"  {safety}: {count}")

        lines.append("\nDEVICE CHARACTERISTICS:")
        for char, count in sterile.most_common():
            lines.append(f"  {char}: {count}")
        for char, count in single_use.most_common():
            lines.append(f"  {char}: {count}")

        lines.append("\nDEVICE DETAILS:")
        for i, device in enumerate(results[:5], 1):
            brand = device.get("brand_name", "Unknown")[:40]
            company = device.get("company_name", "Unknown")[:30]
            model = device.get("version_or_model_number", "N/A")[:30]
            mri = device.get("mri_safety", "Not specified")
            description = device.get("device_description", "")[:80]

            identifiers = device.get("identifiers", [])
            di = "N/A"
            if identifiers:
                for ident in identifiers:
                    if ident.get("id_type") == "Primary":
                        di = ident.get("id", "N/A")
                        break

            lines.append(f"  {i}. {brand}")
            lines.append(f"     Model: {model}")
            lines.append(f"     Company: {company}")
            lines.append(f"     DI: {di}")
            lines.append(f"     MRI Safety: {mri}")
            if description:
                lines.append(f"     Description: {description}...")

        return "\n".join(lines)

    async def _arun(self, query: str, limit: int = 50) -> str:
        return self._run(query, limit)
