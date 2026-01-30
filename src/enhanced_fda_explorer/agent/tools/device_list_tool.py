"""
Device List Tool - Query specific devices from GUDID by product code.
"""
import re
import asyncio
import logging
from typing import Type, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ...tools.device_resolver import DeviceResolver
from ...config import get_config
from ...models.responses import DeviceListResult, DeviceListRecord
from ...services.classification_cache import ClassificationCache

logger = logging.getLogger("fda_agent.device_list")


class DeviceListInput(BaseModel):
    product_code: str = Field(description="FDA 3-letter product code (e.g., 'MSH', 'DXN')")
    limit: int = Field(default=25, description="Maximum devices to return (default 25)")


class DeviceListTool(BaseTool):
    name: str = "list_devices"
    description: str = """REQUIRED when user provides a 3-letter FDA product code and wants information about it.
    Returns: device category name, device class, total count, and actual device records (brand names, manufacturers, models, UDIs).

    USE THIS TOOL when the user mentions a 3-letter product code like MSH, LYZ, FXX, QAB, DXN, etc.
    Examples that REQUIRE this tool:
    - "What devices are MSH?" → list_devices(product_code="MSH")
    - "What is product code LYZ?" → list_devices(product_code="LYZ")
    - "Tell me about FXX" → list_devices(product_code="FXX")
    - "What types of devices are QAB?" → list_devices(product_code="QAB")

    DO NOT use resolve_device when user already has a product code - use list_devices instead."""
    args_schema: Type[BaseModel] = DeviceListInput

    _db_path: str = ""
    _resolver: Optional[DeviceResolver] = None
    _last_structured_result: Optional[DeviceListResult] = None

    def __init__(self, db_path: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        config = get_config()
        self._db_path = db_path or config.gudid_db_path
        self._resolver = DeviceResolver(self._db_path)

    def get_last_structured_result(self) -> Optional[DeviceListResult]:
        return self._last_structured_result

    def _run(self, product_code: str, limit: int = 25) -> str:
        try:
            product_code = product_code.strip().upper()
            if not re.match(r'^[A-Z]{3}$', product_code):
                return f"Invalid product code '{product_code}'. Must be a 3-letter code like 'MSH' or 'DXN'."

            if not self._resolver.conn:
                self._resolver.connect()

            devices_sql = """
                SELECT DISTINCT
                    d.brand_name,
                    d.company_name,
                    d.version_model_number,
                    d.primary_di,
                    d.device_description,
                    pc.product_code
                FROM devices d
                JOIN product_codes pc ON d.public_device_record_key = pc.device_key
                WHERE pc.product_code = ?
                ORDER BY d.company_name, d.brand_name
                LIMIT ?
            """
            device_rows = self._resolver.conn.execute(devices_sql, [product_code, limit]).fetchall()

            count_sql = """
                SELECT COUNT(DISTINCT d.public_device_record_key)
                FROM devices d
                JOIN product_codes pc ON d.public_device_record_key = pc.device_key
                WHERE pc.product_code = ?
            """
            total_count = self._resolver.conn.execute(count_sql, [product_code]).fetchone()[0]

            name_sql = """
                SELECT DISTINCT product_code_name
                FROM product_codes
                WHERE product_code = ?
                LIMIT 1
            """
            name_row = self._resolver.conn.execute(name_sql, [product_code]).fetchone()
            product_code_name = name_row[0] if name_row else None

            device_class = ClassificationCache.get_device_class(product_code)

            records = []
            for row in device_rows:
                records.append(DeviceListRecord(
                    brand_name=row[0] or "N/A",
                    company_name=row[1] or "N/A",
                    version_model_number=row[2],
                    primary_di=row[3],
                    device_description=row[4],
                    product_codes=[row[5]] if row[5] else []
                ))

            self._last_structured_result = DeviceListResult(
                query=product_code,
                product_code=product_code,
                product_code_name=product_code_name,
                device_class=device_class,
                total_found=total_count,
                records=records
            )

            return self._format_results()

        except Exception as e:
            self._last_structured_result = None
            logger.error(f"Error listing devices for {product_code}: {e}")
            return f"Error listing devices: {str(e)}"

    def _format_results(self) -> str:
        result = self._last_structured_result
        if not result:
            return "No results available."

        lines = [
            f"Product Code: {result.product_code}",
            f"Name: {result.product_code_name or 'Unknown'}",
            f"Device Class: {result.device_class or 'Unknown'}",
            f"Total Devices: {result.total_found}",
            f"Showing: {len(result.records)} devices",
            ""
        ]

        for i, device in enumerate(result.records[:10], 1):
            lines.append(f"{i}. {device.brand_name}")
            lines.append(f"   Company: {device.company_name}")
            if device.version_model_number:
                lines.append(f"   Model: {device.version_model_number}")
            if device.primary_di:
                lines.append(f"   DI: {device.primary_di}")
            lines.append("")

        if len(result.records) > 10:
            lines.append(f"... and {len(result.records) - 10} more (see data table)")

        return "\n".join(lines)

    async def _arun(self, product_code: str, limit: int = 25) -> str:
        return await asyncio.to_thread(self._run, product_code, limit)
