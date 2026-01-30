"""
Input detector - Identifies the type of user input using regex patterns.
"""
import re
import logging
from enum import Enum
from typing import Optional
from pathlib import Path

from .models import (
    EntityType,
    IdentifierType,
    IdentifyResponse,
    LookupCandidate,
)
from ..tools.device_resolver import DeviceResolver
from ..openfda_client import OpenFDAClient
from ..services.classification_cache import ClassificationCache

logger = logging.getLogger(__name__)


class InputType(Enum):
    """Types of input patterns."""
    PRODUCT_CODE = "product_code"      # 3 letters, e.g., FXX
    PRIMARY_DI = "primary_di"          # 14 digits
    FEI_NUMBER = "fei_number"          # 7-10 digits
    K_NUMBER = "k_number"              # K + 6 digits
    PMA_NUMBER = "pma_number"          # P + 6 digits
    GENERIC_TEXT = "generic_text"      # Anything else


class InputDetector:
    """Detects input type and resolves to entity candidates."""

    # Regex patterns for different input types
    PATTERNS = {
        InputType.PRODUCT_CODE: r"^[A-Za-z]{3}$",
        InputType.PRIMARY_DI: r"^\d{14}$",
        InputType.FEI_NUMBER: r"^\d{7,10}$",
        InputType.K_NUMBER: r"^[Kk]\d{6}$",
        InputType.PMA_NUMBER: r"^[Pp]\d{6}$",
    }

    def __init__(self, db_path: Optional[str] = None):
        """Initialize detector with optional GUDID database path."""
        if db_path is None:
            db_path = str(Path(__file__).parent.parent.parent.parent / "data" / "gudid.db")
        self.db_path = db_path
        self._resolver: Optional[DeviceResolver] = None
        self._client = OpenFDAClient()

    @property
    def resolver(self) -> DeviceResolver:
        """Lazy-load the device resolver."""
        if self._resolver is None:
            self._resolver = DeviceResolver(self.db_path)
            self._resolver.connect()
        return self._resolver

    def detect_type(self, input_str: str) -> InputType:
        """Detect the type of input based on patterns."""
        input_str = input_str.strip()

        for input_type, pattern in self.PATTERNS.items():
            if re.match(pattern, input_str):
                return input_type

        return InputType.GENERIC_TEXT

    async def identify(self, input_str: str) -> IdentifyResponse:
        """
        Identify the input and return candidates or direct match.

        For specific identifiers (product codes, DIs, K-numbers), returns
        a direct match. For generic text, searches and returns candidates.
        """
        input_str = input_str.strip()
        input_type = self.detect_type(input_str)

        if input_type == InputType.PRODUCT_CODE:
            return await self._handle_product_code(input_str.upper())

        elif input_type == InputType.PRIMARY_DI:
            return self._handle_primary_di(input_str)

        elif input_type == InputType.FEI_NUMBER:
            return await self._handle_fei_number(input_str)

        elif input_type == InputType.K_NUMBER:
            return await self._handle_k_number(input_str.upper())

        elif input_type == InputType.PMA_NUMBER:
            return await self._handle_pma_number(input_str.upper())

        else:
            return await self._handle_generic_text(input_str)

    async def _handle_product_code(self, code: str) -> IdentifyResponse:
        """Handle product code input - direct match to device."""
        # Verify it exists by checking classification
        device_class = ClassificationCache.get_device_class(code)

        # Also try to get product code name from classification API
        try:
            data = await self._client.aget(
                "device/classification.json",
                params={"search": f'product_code:"{code}"', "limit": 1}
            )
            results = data.get("results", [])
            if results:
                name = results[0].get("device_name", code)
                return IdentifyResponse(
                    input=code,
                    needs_disambiguation=False,
                    entity_type=EntityType.DEVICE,
                    identifier=code,
                    identifier_type=IdentifierType.PRODUCT_CODE,
                )
        except Exception as e:
            logger.warning(f"Error fetching classification for {code}: {e}")

        # Even if we can't verify, treat 3-letter codes as product codes
        return IdentifyResponse(
            input=code,
            needs_disambiguation=False,
            entity_type=EntityType.DEVICE,
            identifier=code,
            identifier_type=IdentifierType.PRODUCT_CODE,
        )

    def _handle_primary_di(self, di: str) -> IdentifyResponse:
        """Handle primary DI input - direct match to device."""
        return IdentifyResponse(
            input=di,
            needs_disambiguation=False,
            entity_type=EntityType.DEVICE,
            identifier=di,
            identifier_type=IdentifierType.PRIMARY_DI,
        )

    async def _handle_fei_number(self, fei: str) -> IdentifyResponse:
        """Handle FEI/registration number - direct match to manufacturer."""
        return IdentifyResponse(
            input=fei,
            needs_disambiguation=False,
            entity_type=EntityType.MANUFACTURER,
            identifier=fei,
            identifier_type=IdentifierType.FEI_NUMBER,
        )

    async def _handle_k_number(self, k_number: str) -> IdentifyResponse:
        """Handle K-number - look up the 510(k) and return device info."""
        try:
            data = await self._client.aget(
                "device/510k.json",
                params={"search": f'k_number:"{k_number}"', "limit": 1}
            )
            results = data.get("results", [])
            if results:
                clearance = results[0]
                product_code = clearance.get("product_code", "")
                if product_code:
                    return IdentifyResponse(
                        input=k_number,
                        needs_disambiguation=False,
                        entity_type=EntityType.DEVICE,
                        identifier=product_code,
                        identifier_type=IdentifierType.PRODUCT_CODE,
                    )
        except Exception as e:
            logger.warning(f"Error looking up K-number {k_number}: {e}")

        # Return as-is if we can't resolve
        return IdentifyResponse(
            input=k_number,
            needs_disambiguation=False,
            entity_type=EntityType.DEVICE,
            identifier=k_number,
            identifier_type=IdentifierType.K_NUMBER,
        )

    async def _handle_pma_number(self, pma_number: str) -> IdentifyResponse:
        """Handle PMA number - look up and return device info."""
        try:
            data = await self._client.aget(
                "device/pma.json",
                params={"search": f'pma_number:"{pma_number}"', "limit": 1}
            )
            results = data.get("results", [])
            if results:
                approval = results[0]
                product_code = approval.get("product_code", "")
                if product_code:
                    return IdentifyResponse(
                        input=pma_number,
                        needs_disambiguation=False,
                        entity_type=EntityType.DEVICE,
                        identifier=product_code,
                        identifier_type=IdentifierType.PRODUCT_CODE,
                    )
        except Exception as e:
            logger.warning(f"Error looking up PMA {pma_number}: {e}")

        # Return as-is if we can't resolve
        return IdentifyResponse(
            input=pma_number,
            needs_disambiguation=False,
            entity_type=EntityType.DEVICE,
            identifier=pma_number,
            identifier_type=IdentifierType.PMA_NUMBER,
        )

    async def _handle_generic_text(self, query: str) -> IdentifyResponse:
        """Handle generic text - search for device and manufacturer candidates."""
        candidates: list[LookupCandidate] = []

        # Search for product codes using GUDID resolver
        try:
            result = self.resolver.get_product_codes_fast(query, min_devices=2, limit=100)
            product_codes = result.get("product_codes", [])

            for pc in product_codes:
                # Look up device class from cache for grouping in disambiguation UI
                device_class = ClassificationCache.get_device_class(pc["code"])
                candidates.append(LookupCandidate(
                    entity_type=EntityType.DEVICE,
                    identifier=pc["code"],
                    identifier_type=IdentifierType.PRODUCT_CODE,
                    display_name=f"{pc['code']}: {pc['name']}",
                    description=pc.get("name"),
                    device_count=pc.get("device_count"),
                    device_class=device_class,
                ))

        except Exception as e:
            logger.warning(f"Error searching GUDID product codes for '{query}': {e}")

        # Search for companies by name directly in GUDID
        try:
            if self.resolver.conn:
                company_results = self.resolver.conn.execute("""
                    SELECT company_name, COUNT(*) as device_count
                    FROM devices
                    WHERE company_name ILIKE ?
                    GROUP BY company_name
                    ORDER BY device_count DESC
                    LIMIT 100
                """, [f"%{query}%"]).fetchall()

                for row in company_results:
                    candidates.append(LookupCandidate(
                        entity_type=EntityType.MANUFACTURER,
                        identifier=row[0],
                        identifier_type=IdentifierType.COMPANY_NAME,
                        display_name=row[0],
                        description=f"{row[1]:,} registered devices",
                        device_count=row[1],
                    ))
        except Exception as e:
            logger.warning(f"Error searching GUDID companies for '{query}': {e}")

        # If no GUDID results, try OpenFDA classification search
        if not candidates:
            try:
                data = await self._client.aget(
                    "device/classification.json",
                    params={"search": f'device_name:"{query}"', "limit": 10}
                )
                results = data.get("results", [])
                seen_codes = set()
                for r in results:
                    code = r.get("product_code", "")
                    if code and code not in seen_codes:
                        seen_codes.add(code)
                        # Get device class from result or fall back to cache
                        device_class = r.get("device_class") or ClassificationCache.get_device_class(code)
                        candidates.append(LookupCandidate(
                            entity_type=EntityType.DEVICE,
                            identifier=code,
                            identifier_type=IdentifierType.PRODUCT_CODE,
                            display_name=f"{code}: {r.get('device_name', '')}",
                            description=r.get("device_name"),
                            device_class=device_class,
                        ))
            except Exception as e:
                logger.warning(f"Error searching classifications for '{query}': {e}")

        # Determine if we need disambiguation
        if len(candidates) == 0:
            # No matches found
            return IdentifyResponse(
                input=query,
                needs_disambiguation=True,
                candidates=[],
            )
        elif len(candidates) == 1:
            # Single match - no disambiguation needed
            c = candidates[0]
            return IdentifyResponse(
                input=query,
                needs_disambiguation=False,
                entity_type=c.entity_type,
                identifier=c.identifier,
                identifier_type=c.identifier_type,
            )
        else:
            # Multiple matches - needs disambiguation
            return IdentifyResponse(
                input=query,
                needs_disambiguation=True,
                candidates=candidates,
            )

    def close(self):
        """Close database connections."""
        if self._resolver:
            self._resolver.close()
