"""
Device report generator - Creates comprehensive device reports.
"""
import asyncio
import logging
from typing import Optional
from collections import Counter
from pathlib import Path

from .models import (
    IdentifierType,
    DeviceReportResponse,
    ClassificationSection,
    EventsSection,
    EventTypeCounts,
    RecallsSection,
    RecallClassCounts,
    ClearancesSection,
    UDISection,
    MRISafetyCounts,
    ManufacturerSummary,
)
from ..openfda_client import OpenFDAClient
from ..tools.device_resolver import DeviceResolver
from ..services.classification_cache import ClassificationCache

logger = logging.getLogger(__name__)


class DeviceReportGenerator:
    """Generates comprehensive device reports."""

    def __init__(self, db_path: Optional[str] = None):
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

    async def generate(
        self,
        identifier: str,
        identifier_type: IdentifierType,
    ) -> DeviceReportResponse:
        """Generate a comprehensive device report."""
        # Determine the product code to use for searches
        product_code = None
        product_code_name = None

        if identifier_type == IdentifierType.PRODUCT_CODE:
            product_code = identifier.upper()
        elif identifier_type == IdentifierType.PRIMARY_DI:
            # Look up the product code from GUDID
            product_code = await self._get_product_code_from_di(identifier)

        # Fetch all sections concurrently
        tasks = [
            self._get_classification(product_code),
            self._get_events(product_code),
            self._get_recalls(product_code),
            self._get_clearances(product_code),
            self._get_udi(product_code),
            self._get_top_manufacturers(product_code),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        classification = results[0] if not isinstance(results[0], Exception) else None
        events = results[1] if not isinstance(results[1], Exception) else None
        recalls = results[2] if not isinstance(results[2], Exception) else None
        clearances = results[3] if not isinstance(results[3], Exception) else None
        udi = results[4] if not isinstance(results[4], Exception) else None
        top_manufacturers = results[5] if not isinstance(results[5], Exception) else []

        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Error fetching section {i}: {result}")

        # Get product code name from classification
        if classification:
            product_code_name = classification.device_name

        return DeviceReportResponse(
            identifier=identifier,
            identifier_type=identifier_type,
            product_code=product_code,
            product_code_name=product_code_name,
            classification=classification,
            events=events,
            recalls=recalls,
            clearances=clearances,
            udi=udi,
            top_manufacturers=top_manufacturers,
        )

    async def _get_product_code_from_di(self, di: str) -> Optional[str]:
        """Look up product code from primary DI in GUDID."""
        try:
            data = await self._client.aget(
                "device/udi.json",
                params={"search": f'identifiers.id:"{di}"', "limit": 1}
            )
            results = data.get("results", [])
            if results:
                # Get product code from openfda section
                openfda = results[0].get("openfda", {})
                codes = openfda.get("product_code", [])
                if codes:
                    return codes[0]
        except Exception as e:
            logger.warning(f"Error looking up DI {di}: {e}")
        return None

    async def _get_classification(self, product_code: Optional[str]) -> Optional[ClassificationSection]:
        """Get device classification information."""
        if not product_code:
            return None

        try:
            data = await self._client.aget(
                "device/classification.json",
                params={"search": f'product_code:"{product_code}"', "limit": 1}
            )
            results = data.get("results", [])
            if not results:
                return None

            c = results[0]
            openfda = c.get("openfda", {})
            specialty = openfda.get("medical_specialty_description", [""])[0] if isinstance(
                openfda.get("medical_specialty_description"), list
            ) else openfda.get("medical_specialty_description", "")

            # Map submission type
            submission_types = {
                "1": "510(k) Required",
                "2": "510(k) Exempt",
                "3": "PMA Required",
                "4": "Transitional",
                "5": "Not Classified",
                "7": "HDE Required"
            }
            sub_type = c.get("submission_type_id", "")
            submission_type = submission_types.get(str(sub_type), str(sub_type))

            return ClassificationSection(
                device_class=c.get("device_class"),
                device_name=c.get("device_name"),
                regulation_number=c.get("regulation_number"),
                submission_type=submission_type,
                definition=c.get("definition"),
                medical_specialty=specialty,
            )
        except Exception as e:
            logger.warning(f"Error fetching classification for {product_code}: {e}")
            return None

    async def _get_events(self, product_code: Optional[str]) -> Optional[EventsSection]:
        """Get adverse events summary."""
        if not product_code:
            return None

        try:
            search = f'device.device_report_product_code:"{product_code}"'

            # Get total count and aggregations
            count_tasks = [
                self._client.aget_count("device/event.json", search, "event_type.exact", limit=10),
                self._client.aget_count("device/event.json", search, "device.manufacturer_d_name.exact", limit=10),
            ]
            counts = await asyncio.gather(*count_tasks, return_exceptions=True)

            event_type_counts = counts[0] if not isinstance(counts[0], Exception) else []
            manufacturer_counts = counts[1] if not isinstance(counts[1], Exception) else []

            # Parse event type counts
            type_counts = EventTypeCounts()
            total = 0
            for item in event_type_counts:
                term = item.get("term", "").lower()
                count = item.get("count", 0)
                total += count
                if "death" in term:
                    type_counts.death = count
                elif "injury" in term:
                    type_counts.injury = count
                elif "malfunction" in term:
                    type_counts.malfunction = count
                else:
                    type_counts.other += count

            # Get recent events
            data = await self._client.aget(
                "device/event.json",
                params={"search": search, "limit": 5},
                sort="date_received:desc"
            )
            results = data.get("results", [])

            recent_events = []
            for event in results[:5]:
                devices = event.get("device", [])
                device_info = devices[0] if devices else {}
                date_raw = event.get("date_received", "")
                date_fmt = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}" if len(date_raw) == 8 else date_raw
                recent_events.append({
                    "event_date": date_fmt,
                    "event_type": event.get("event_type", ""),
                    "device_name": device_info.get("brand_name") or device_info.get("generic_name", ""),
                    "manufacturer": device_info.get("manufacturer_d_name", ""),
                    "report_number": event.get("mdr_report_key", ""),
                })

            return EventsSection(
                total_count=total,
                event_type_counts=type_counts,
                top_manufacturers=[
                    {"name": item["term"], "count": item["count"]}
                    for item in manufacturer_counts[:5]
                ],
                recent_events=recent_events,
            )
        except Exception as e:
            logger.warning(f"Error fetching events for {product_code}: {e}")
            return None

    async def _get_recalls(self, product_code: Optional[str]) -> Optional[RecallsSection]:
        """Get recalls summary."""
        if not product_code:
            return None

        try:
            # Use device/recall endpoint for product code searches
            search = f'product_code:"{product_code}"'

            # Get total and aggregations from enforcement endpoint
            enforcement_search = f'product_code:"{product_code}"'
            count_tasks = [
                self._client.aget_count("device/enforcement.json", enforcement_search, "classification.exact", limit=10),
                self._client.aget_count("device/enforcement.json", enforcement_search, "status.exact", limit=10),
            ]
            counts = await asyncio.gather(*count_tasks, return_exceptions=True)

            class_counts_raw = counts[0] if not isinstance(counts[0], Exception) else []
            status_counts_raw = counts[1] if not isinstance(counts[1], Exception) else []

            # Parse class counts
            class_counts = RecallClassCounts()
            total = 0
            for item in class_counts_raw:
                term = item.get("term", "")
                count = item.get("count", 0)
                total += count
                if term == "Class I":
                    class_counts.class_i = count
                elif term == "Class II":
                    class_counts.class_ii = count
                elif term == "Class III":
                    class_counts.class_iii = count

            # Status counts
            status_counts = {item["term"]: item["count"] for item in status_counts_raw}

            # Get recent recalls
            data = await self._client.aget(
                "device/enforcement.json",
                params={"search": enforcement_search, "limit": 5},
                sort="recall_initiation_date:desc"
            )
            results = data.get("results", [])

            recent_recalls = []
            for recall in results[:5]:
                date_raw = recall.get("recall_initiation_date", "")
                date = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}" if len(date_raw) == 8 else date_raw
                cls = recall.get("classification", "")
                recent_recalls.append({
                    "date": date,
                    "class": cls.replace("Class ", "") if cls else "",
                    "status": recall.get("status", ""),
                    "reason": recall.get("reason_for_recall", "")[:150],
                    "product": recall.get("product_description", "")[:100],
                })

            return RecallsSection(
                total_count=total,
                class_counts=class_counts,
                status_counts=status_counts,
                recent_recalls=recent_recalls,
            )
        except Exception as e:
            logger.warning(f"Error fetching recalls for {product_code}: {e}")
            return None

    async def _get_clearances(self, product_code: Optional[str]) -> Optional[ClearancesSection]:
        """Get 510(k) clearances summary."""
        if not product_code:
            return None

        try:
            search = f'product_code:"{product_code}"'

            # Get total and top applicants
            applicant_counts = await self._client.aget_count(
                "device/510k.json", search, "applicant.exact", limit=10
            )

            total = sum(item.get("count", 0) for item in applicant_counts)

            # Get recent clearances
            data = await self._client.aget(
                "device/510k.json",
                params={"search": search, "limit": 5},
                sort="decision_date:desc"
            )
            results = data.get("results", [])

            recent_clearances = []
            for clearance in results[:5]:
                recent_clearances.append({
                    "k_number": clearance.get("k_number", ""),
                    "date": clearance.get("decision_date", ""),
                    "device_name": clearance.get("device_name", "")[:50],
                    "applicant": clearance.get("applicant", ""),
                    "decision": clearance.get("decision_description", ""),
                })

            return ClearancesSection(
                total_count=total,
                top_applicants=[
                    {"name": item["term"], "count": item["count"]}
                    for item in applicant_counts[:5]
                ],
                recent_clearances=recent_clearances,
            )
        except Exception as e:
            logger.warning(f"Error fetching clearances for {product_code}: {e}")
            return None

    async def _get_udi(self, product_code: Optional[str]) -> Optional[UDISection]:
        """Get UDI database summary."""
        if not product_code:
            return None

        try:
            # Search UDI by product code (via openfda field)
            search = f'products.product_code:"{product_code}"'

            data = await self._client.aget(
                "device/udi.json",
                params={"search": search, "limit": 100}
            )
            results = data.get("results", [])
            total = data.get("meta", {}).get("results", {}).get("total", len(results))

            if not results:
                return None

            # Aggregate MRI safety, sterile, single-use
            mri_counts = MRISafetyCounts()
            sterile_count = 0
            single_use_count = 0

            for device in results:
                mri = device.get("mri_safety", "")
                if mri:
                    mri_lower = mri.lower()
                    if "safe" in mri_lower and "conditional" not in mri_lower and "unsafe" not in mri_lower:
                        mri_counts.mr_safe += 1
                    elif "conditional" in mri_lower:
                        mri_counts.mr_conditional += 1
                    elif "unsafe" in mri_lower:
                        mri_counts.mr_unsafe += 1
                    else:
                        mri_counts.not_specified += 1
                else:
                    mri_counts.not_specified += 1

                if device.get("is_sterile"):
                    sterile_count += 1
                if device.get("is_single_use"):
                    single_use_count += 1

            # Sample devices
            sample_devices = []
            for device in results[:5]:
                identifiers = device.get("identifiers", [])
                primary_di = None
                for ident in identifiers:
                    if ident.get("id_type") == "Primary":
                        primary_di = ident.get("id")
                        break

                sample_devices.append({
                    "brand_name": device.get("brand_name", ""),
                    "company_name": device.get("company_name", ""),
                    "model": device.get("version_or_model_number", ""),
                    "primary_di": primary_di,
                    "mri_safety": device.get("mri_safety", ""),
                })

            return UDISection(
                total_count=total,
                mri_safety=mri_counts,
                sterile_count=sterile_count,
                single_use_count=single_use_count,
                sample_devices=sample_devices,
            )
        except Exception as e:
            logger.warning(f"Error fetching UDI for {product_code}: {e}")
            return None

    async def _get_top_manufacturers(self, product_code: Optional[str]) -> list[ManufacturerSummary]:
        """Get top manufacturers for this device type from GUDID."""
        if not product_code:
            return []

        try:
            # Use the resolver to get companies for this product code
            result = self.resolver.get_product_codes_fast(product_code, min_devices=1, limit=1)
            companies = result.get("companies", [])

            return [
                ManufacturerSummary(name=c["name"], device_count=c["device_count"])
                for c in companies[:10]
            ]
        except Exception as e:
            logger.warning(f"Error fetching manufacturers for {product_code}: {e}")
            return []

    def close(self):
        """Close database connections."""
        if self._resolver:
            self._resolver.close()
