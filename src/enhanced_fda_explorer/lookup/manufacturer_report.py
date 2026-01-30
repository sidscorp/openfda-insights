"""
Manufacturer report generator - Creates comprehensive manufacturer reports.
"""
import asyncio
import logging
from typing import Optional
from collections import Counter
from pathlib import Path

from .models import (
    IdentifierType,
    ManufacturerReportResponse,
    CompanyInfoSection,
    LocationsSection,
    LocationRecord,
    PortfolioSection,
    ProductCodeSummary,
    EventsSection,
    EventTypeCounts,
    RecallsSection,
    RecallClassCounts,
    RegulatorySection,
)
from ..openfda_client import OpenFDAClient
from ..tools.device_resolver import DeviceResolver

logger = logging.getLogger(__name__)


COUNTRY_NAMES = {
    "US": "United States",
    "CN": "China",
    "DE": "Germany",
    "JP": "Japan",
    "GB": "United Kingdom",
    "FR": "France",
    "CA": "Canada",
    "MX": "Mexico",
    "KR": "South Korea",
    "TW": "Taiwan",
    "IT": "Italy",
    "NL": "Netherlands",
    "CH": "Switzerland",
    "AU": "Australia",
    "IN": "India",
    "IE": "Ireland",
    "BE": "Belgium",
    "IL": "Israel",
    "DK": "Denmark",
    "SE": "Sweden",
}


class ManufacturerReportGenerator:
    """Generates comprehensive manufacturer reports."""

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
    ) -> ManufacturerReportResponse:
        """Generate a comprehensive manufacturer report."""
        # Determine company name for searches
        company_name = identifier

        if identifier_type == IdentifierType.FEI_NUMBER:
            # Look up company name from registration
            company_name = await self._get_company_name_from_fei(identifier)
            if not company_name:
                company_name = identifier

        # Fetch all sections concurrently
        tasks = [
            self._get_company_info(company_name),
            self._get_locations(company_name),
            self._get_portfolio(company_name),
            self._get_events(company_name),
            self._get_recalls(company_name),
            self._get_regulatory(company_name),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        company_info = results[0] if not isinstance(results[0], Exception) else None
        locations = results[1] if not isinstance(results[1], Exception) else None
        portfolio = results[2] if not isinstance(results[2], Exception) else None
        events = results[3] if not isinstance(results[3], Exception) else None
        recalls = results[4] if not isinstance(results[4], Exception) else None
        regulatory = results[5] if not isinstance(results[5], Exception) else None

        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Error fetching section {i}: {result}")

        return ManufacturerReportResponse(
            identifier=identifier,
            identifier_type=identifier_type,
            company_info=company_info,
            locations=locations,
            portfolio=portfolio,
            events=events,
            recalls=recalls,
            regulatory=regulatory,
        )

    async def _get_company_name_from_fei(self, fei: str) -> Optional[str]:
        """Look up company name from FEI/registration number."""
        try:
            data = await self._client.aget(
                "device/registrationlisting.json",
                params={"search": f'registration.registration_number:"{fei}"', "limit": 1}
            )
            results = data.get("results", [])
            if results:
                reg = results[0].get("registration", {})
                return reg.get("name")
        except Exception as e:
            logger.warning(f"Error looking up FEI {fei}: {e}")
        return None

    async def _get_company_info(self, company_name: str) -> Optional[CompanyInfoSection]:
        """Get company information."""
        try:
            # Get device count from GUDID
            total_devices = 0
            name_variations = []

            # Search GUDID for this company
            if self.resolver.conn:
                try:
                    result = self.resolver.conn.execute("""
                        SELECT company_name, COUNT(*) as device_count
                        FROM devices
                        WHERE company_name ILIKE ?
                        GROUP BY company_name
                        ORDER BY device_count DESC
                        LIMIT 10
                    """, [f"%{company_name}%"]).fetchall()

                    for row in result:
                        name_variations.append(row[0])
                        total_devices += row[1]
                except Exception as e:
                    logger.warning(f"Error querying GUDID for {company_name}: {e}")

            # Fallback to OpenFDA if no GUDID results
            if total_devices == 0:
                data = await self._client.aget(
                    "device/registrationlisting.json",
                    params={"search": f'registration.name:"{company_name}"', "limit": 1}
                )
                total = data.get("meta", {}).get("results", {}).get("total", 0)
                total_devices = total

            return CompanyInfoSection(
                name=company_name,
                name_variations=name_variations[:5],
                total_device_count=total_devices,
            )
        except Exception as e:
            logger.warning(f"Error fetching company info for {company_name}: {e}")
            return None

    async def _get_locations(self, company_name: str) -> Optional[LocationsSection]:
        """Get manufacturer locations."""
        try:
            search = f'registration.name:"{company_name}"'

            # Get country and state aggregations
            count_tasks = [
                self._client.aget_count(
                    "device/registrationlisting.json", search, "registration.iso_country_code", limit=20
                ),
                self._client.aget_count(
                    "device/registrationlisting.json", search, "registration.state_code", limit=20
                ),
            ]
            counts = await asyncio.gather(*count_tasks, return_exceptions=True)

            country_counts_raw = counts[0] if not isinstance(counts[0], Exception) else []
            state_counts_raw = counts[1] if not isinstance(counts[1], Exception) else []

            # Parse counts
            countries = {}
            for item in country_counts_raw:
                code = item.get("term", "")
                name = COUNTRY_NAMES.get(code, code)
                countries[name] = item.get("count", 0)

            us_states = {}
            for item in state_counts_raw:
                state = item.get("term", "")
                if state:
                    us_states[state] = item.get("count", 0)

            total = sum(countries.values())

            # Get sample locations
            data = await self._client.aget(
                "device/registrationlisting.json",
                params={"search": search, "limit": 10}
            )
            results = data.get("results", [])

            locations = []
            seen = set()
            for r in results:
                reg = r.get("registration", {})
                name = reg.get("name", "")
                city = reg.get("city", "")
                key = (name, city)
                if key not in seen:
                    seen.add(key)
                    country_code = reg.get("iso_country_code", "US")
                    locations.append(LocationRecord(
                        name=name,
                        city=city,
                        state=reg.get("state_code"),
                        country=COUNTRY_NAMES.get(country_code, country_code),
                        address=reg.get("address_line_1"),
                    ))

            return LocationsSection(
                total_count=total,
                countries=countries,
                us_states=us_states,
                locations=locations[:10],
            )
        except Exception as e:
            logger.warning(f"Error fetching locations for {company_name}: {e}")
            return None

    async def _get_portfolio(self, company_name: str) -> Optional[PortfolioSection]:
        """Get product portfolio."""
        try:
            product_codes = []

            # Try GUDID first
            if self.resolver.conn:
                try:
                    result = self.resolver.conn.execute("""
                        SELECT pc.product_code, pc.product_code_name, COUNT(DISTINCT d.public_device_record_key) as device_count
                        FROM devices d
                        JOIN product_codes pc ON d.public_device_record_key = pc.device_key
                        WHERE d.company_name ILIKE ?
                        GROUP BY pc.product_code, pc.product_code_name
                        ORDER BY device_count DESC
                        LIMIT 20
                    """, [f"%{company_name}%"]).fetchall()

                    for row in result:
                        product_codes.append(ProductCodeSummary(
                            code=row[0],
                            name=row[1] or "",
                            device_count=row[2],
                        ))
                except Exception as e:
                    logger.warning(f"Error querying GUDID portfolio for {company_name}: {e}")

            # Fallback to OpenFDA registrations
            if not product_codes:
                search = f'registration.name:"{company_name}"'
                data = await self._client.aget(
                    "device/registrationlisting.json",
                    params={"search": search, "limit": 100}
                )
                results = data.get("results", [])

                code_counts: Counter = Counter()
                code_names = {}
                for r in results:
                    for prod in r.get("products", []):
                        openfda = prod.get("openfda", {})
                        codes = openfda.get("product_code", [])
                        names = openfda.get("device_name", [])
                        for i, code in enumerate(codes):
                            code_counts[code] += 1
                            if code not in code_names and i < len(names):
                                code_names[code] = names[i]

                for code, count in code_counts.most_common(20):
                    product_codes.append(ProductCodeSummary(
                        code=code,
                        name=code_names.get(code, ""),
                        device_count=count,
                    ))

            return PortfolioSection(
                total_product_codes=len(product_codes),
                product_codes=product_codes,
            )
        except Exception as e:
            logger.warning(f"Error fetching portfolio for {company_name}: {e}")
            return None

    async def _get_events(self, company_name: str) -> Optional[EventsSection]:
        """Get adverse events for this manufacturer."""
        try:
            search = f'device.manufacturer_d_name:"{company_name}"'

            # Get aggregations
            event_type_counts = await self._client.aget_count(
                "device/event.json", search, "event_type.exact", limit=10
            )

            # Parse counts
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
                    "report_number": event.get("mdr_report_key", ""),
                })

            return EventsSection(
                total_count=total,
                event_type_counts=type_counts,
                top_manufacturers=[],  # Not relevant for manufacturer report
                recent_events=recent_events,
            )
        except Exception as e:
            logger.warning(f"Error fetching events for {company_name}: {e}")
            return None

    async def _get_recalls(self, company_name: str) -> Optional[RecallsSection]:
        """Get recalls for this manufacturer."""
        try:
            search = f'recalling_firm:"{company_name}"'

            # Get aggregations
            count_tasks = [
                self._client.aget_count("device/enforcement.json", search, "classification.exact", limit=10),
                self._client.aget_count("device/enforcement.json", search, "status.exact", limit=10),
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

            status_counts = {item["term"]: item["count"] for item in status_counts_raw}

            # Get recent recalls
            data = await self._client.aget(
                "device/enforcement.json",
                params={"search": search, "limit": 5},
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
                })

            return RecallsSection(
                total_count=total,
                class_counts=class_counts,
                status_counts=status_counts,
                recent_recalls=recent_recalls,
            )
        except Exception as e:
            logger.warning(f"Error fetching recalls for {company_name}: {e}")
            return None

    async def _get_regulatory(self, company_name: str) -> Optional[RegulatorySection]:
        """Get regulatory history (510(k)s and PMAs)."""
        try:
            # Get 510(k)s
            k_search = f'applicant:"{company_name}"'
            k_count_task = self._client.aget_count("device/510k.json", k_search, "applicant.exact", limit=1)

            # Get PMAs
            pma_search = f'applicant:"{company_name}"'
            pma_count_task = self._client.aget_count("device/pma.json", pma_search, "applicant.exact", limit=1)

            # Get recent submissions (fetch more for "view all" functionality)
            k_data_task = self._client.aget(
                "device/510k.json",
                params={"search": k_search, "limit": 100},
                sort="decision_date:desc"
            )
            pma_data_task = self._client.aget(
                "device/pma.json",
                params={"search": pma_search, "limit": 100},
                sort="decision_date:desc"
            )

            results = await asyncio.gather(
                k_count_task, pma_count_task, k_data_task, pma_data_task,
                return_exceptions=True
            )

            k_counts = results[0] if not isinstance(results[0], Exception) else []
            pma_counts = results[1] if not isinstance(results[1], Exception) else []
            k_data = results[2] if not isinstance(results[2], Exception) else {"results": []}
            pma_data = results[3] if not isinstance(results[3], Exception) else {"results": []}

            total_510k = sum(item.get("count", 0) for item in k_counts)
            total_pma = sum(item.get("count", 0) for item in pma_counts)

            recent_510k = []
            for clearance in k_data.get("results", []):
                date_raw = clearance.get("decision_date", "")
                date_fmt = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}" if len(date_raw) == 8 else date_raw
                recent_510k.append({
                    "k_number": clearance.get("k_number", ""),
                    "date": date_fmt,
                    "device_name": clearance.get("device_name", "")[:50],
                    "decision": clearance.get("decision_description", ""),
                })

            recent_pma = []
            for approval in pma_data.get("results", []):
                date_raw = approval.get("decision_date", "")
                date_fmt = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}" if len(date_raw) == 8 else date_raw
                recent_pma.append({
                    "pma_number": approval.get("pma_number", ""),
                    "date": date_fmt,
                    "trade_name": approval.get("trade_name", "")[:50],
                    "decision": approval.get("decision_code", ""),
                })

            return RegulatorySection(
                total_510k=total_510k,
                total_pma=total_pma,
                recent_510k=recent_510k,
                recent_pma=recent_pma,
            )
        except Exception as e:
            logger.warning(f"Error fetching regulatory for {company_name}: {e}")
            return None

    def close(self):
        """Close database connections."""
        if self._resolver:
            self._resolver.close()
