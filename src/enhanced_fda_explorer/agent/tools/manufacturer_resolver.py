"""
Manufacturer Resolver Tool - Resolve company names to exact FDA firm names.
"""
import logging
import os
from pathlib import Path
from typing import Type, Optional
import asyncio
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ...tools.device_resolver import DeviceResolver
from ...config import get_config
from ...models.responses import ManufacturerInfo
from ...services.semantic_expander import SemanticExpander

logger = logging.getLogger("fda_agent.manufacturer_resolver")


class ManufacturerResolverInput(BaseModel):
    query: str = Field(description="Company or manufacturer name to search for (e.g., '3M', 'Medtronic', 'Johnson')")
    limit: int = Field(default=100, description="Maximum number of results")


class ManufacturerResolverTool(BaseTool):
    name: str = "resolve_manufacturer"
    description: str = """Resolve company/manufacturer names to exact FDA firm names.
    Use this to find the exact company name variations used in FDA databases before searching recalls or events by manufacturer.
    For example, '3M' may appear as '3M Company', '3M COMPANY', '3M Health Care', etc.
    Supports semantic expansion: 'J&J' will also find 'Johnson & Johnson' variants."""
    args_schema: Type[BaseModel] = ManufacturerResolverInput

    _db_path: str = ""
    _resolver: Optional[DeviceResolver] = None
    _semantic_expander: Optional[SemanticExpander] = None
    _last_structured_result: Optional[list[ManufacturerInfo]] = None

    def __init__(self, db_path: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        config = get_config()
        self._db_path = db_path or config.gudid_db_path
        self._resolver = DeviceResolver(self._db_path)
        self._init_semantic_expander(config)

    def _init_semantic_expander(self, config):
        """Initialize semantic expander if embeddings and API key are available."""
        if not config.semantic_enabled:
            return

        embeddings_dir = Path(config.semantic_embeddings_dir or "").resolve()
        api_key = os.getenv("AI_API_KEY") or os.getenv("OPENROUTER_API_KEY")

        if not embeddings_dir.exists() or not api_key:
            return

        try:
            self._semantic_expander = SemanticExpander(
                embeddings_dir=embeddings_dir,
                api_key=api_key,
                manufacturer_threshold=config.semantic_manufacturer_threshold,
                cache_size=config.semantic_cache_size,
                cache_ttl=config.semantic_cache_ttl,
            )
            logger.info("Manufacturer semantic expansion enabled")
        except Exception as e:
            logger.warning(f"Failed to initialize semantic expander: {e}")

    def get_last_structured_result(self) -> Optional[list[ManufacturerInfo]]:
        return self._last_structured_result

    def _run(self, query: str, limit: int = 100) -> str:
        try:
            if not self._resolver.conn:
                self._resolver.connect()

            search_terms = [query]
            semantic_matches = []

            if self._semantic_expander:
                try:
                    expansion = self._semantic_expander.expand_manufacturer_query(query)
                    if expansion.semantic_matches:
                        semantic_matches = expansion.semantic_matches[:5]
                        for match in semantic_matches:
                            if match.text.lower() not in [t.lower() for t in search_terms]:
                                search_terms.append(match.text)
                        logger.info(f"Expanded '{query}' to {len(search_terms)} manufacturer terms")
                except Exception as e:
                    logger.warning(f"Manufacturer semantic expansion failed: {e}")

            all_results = []
            for term in search_terms:
                sql = """
                    SELECT company_name, COUNT(*) as device_count
                    FROM devices
                    WHERE LOWER(company_name) LIKE ?
                    GROUP BY company_name
                    ORDER BY device_count DESC
                    LIMIT ?
                """
                results = self._resolver.conn.execute(sql, [f"%{term.lower()}%", limit]).fetchall()
                all_results.extend(results)

            seen = set()
            unique_results = []
            for row in all_results:
                if row[0] not in seen:
                    seen.add(row[0])
                    unique_results.append(row)

            unique_results.sort(key=lambda x: x[1], reverse=True)
            unique_results = unique_results[:limit]

            if not unique_results:
                self._last_structured_result = []
                return f"No manufacturers found matching '{query}'."

            company_groups = {}
            for row in unique_results:
                name = row[0]
                count = row[1]
                name_lower = name.lower().strip()
                base_name = name_lower.split(',')[0].split('inc')[0].split('llc')[0].strip()

                if base_name not in company_groups:
                    company_groups[base_name] = {"names": [], "total_count": 0}
                company_groups[base_name]["names"].append(name)
                company_groups[base_name]["total_count"] += count

            self._last_structured_result = []
            lines = [f"Found {len(unique_results)} manufacturer name variations matching '{query}':\n"]

            if len(search_terms) > 1:
                lines.append(f"SEMANTIC EXPANSION: Searched {len(search_terms)} terms:")
                for term in search_terms[:4]:
                    lines.append(f"  - {term}")
                lines.append("")

            sorted_groups = sorted(company_groups.items(), key=lambda x: x[1]["total_count"], reverse=True)

            for base_name, info in sorted_groups[:20]:
                primary_name = info["names"][0]
                total = info["total_count"]
                variations = info["names"]

                self._last_structured_result.append(ManufacturerInfo(
                    name=primary_name,
                    device_count=total,
                    variations=variations
                ))

                lines.append(f"• {primary_name} ({total} devices)")
                if len(variations) > 1:
                    lines.append(f"  Variations: {', '.join(variations[1:5])}")
                    if len(variations) > 5:
                        lines.append(f"  ... and {len(variations) - 5} more variations")

            lines.append(f"\nTotal: {sum(r[1] for r in unique_results)} devices across {len(unique_results)} name variations")
            lines.append("\nUse exact names from above when searching recalls or events by manufacturer.")

            return "\n".join(lines)

        except Exception as e:
            self._last_structured_result = None
            return f"Error resolving manufacturer: {str(e)}"

    async def _arun(self, query: str, limit: int = 100) -> str:
        return await asyncio.to_thread(self._run, query, limit)
