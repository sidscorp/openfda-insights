"""
Device resolver for searching and matching medical devices from GUDID data.
"""
import duckdb
from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher
import time
import logging
from pathlib import Path

from ..device_models.device_concept import (
    DeviceConcept,
    DeviceMatch,
    ResolverResponse,
    MatchType,
    GMDNTerm,
    FDAProductCode,
    DeviceIdentifier,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeviceResolver:
    """
    Resolves device queries to DeviceConcept objects using GUDID data.
    Supports exact and fuzzy matching across multiple fields.
    """

    def __init__(self, db_path: str = "gudid.db"):
        """Initialize resolver with database path."""
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """Connect to DuckDB database."""
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}. Run indexer first.")
        self.conn = duckdb.connect(self.db_path, read_only=True)
        logger.debug(f"Connected to database: {self.db_path}")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity score between two strings."""
        if not str1 or not str2:
            return 0.0
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def _build_device_concept(self, device_row: Dict[str, Any]) -> DeviceConcept:
        """Build DeviceConcept from database row and related data."""
        device_key = device_row['public_device_record_key']

        # Fetch related data
        gmdn_terms = []
        gmdn_rows = self.conn.execute("""
            SELECT gmdn_code, gmdn_pt_name, gmdn_pt_definition, implantable, gmdn_code_status
            FROM gmdn_terms WHERE device_key = ?
        """, [device_key]).fetchall()

        for gmdn_row in gmdn_rows:
            gmdn_terms.append(GMDNTerm(
                gmdnCode=gmdn_row[0],
                gmdnPTName=gmdn_row[1],
                gmdnPTDefinition=gmdn_row[2],
                implantable=gmdn_row[3] or False,
                gmdnCodeStatus=gmdn_row[4]
            ))

        product_codes = []
        code_rows = self.conn.execute("""
            SELECT product_code, product_code_name
            FROM product_codes WHERE device_key = ?
        """, [device_key]).fetchall()

        for code_row in code_rows:
            product_codes.append(FDAProductCode(
                productCode=code_row[0],
                productCodeName=code_row[1]
            ))

        identifiers = []
        id_rows = self.conn.execute("""
            SELECT device_id, device_id_type, device_id_issuing_agency, pkg_quantity, pkg_type
            FROM device_identifiers WHERE device_key = ?
        """, [device_key]).fetchall()

        for id_row in id_rows:
            identifiers.append(DeviceIdentifier(
                deviceId=id_row[0],
                deviceIdType=id_row[1],
                deviceIdIssuingAgency=id_row[2],
                pkgQuantity=id_row[3],
                pkgType=id_row[4]
            ))

        # Build DeviceConcept
        return DeviceConcept(
            publicDeviceRecordKey=device_row['public_device_record_key'],
            primary_di=device_row.get('primary_di'),
            brandName=device_row.get('brand_name'),
            versionModelNumber=device_row.get('version_model_number'),
            catalogNumber=device_row.get('catalog_number'),
            deviceDescription=device_row.get('device_description'),
            companyName=device_row.get('company_name'),
            dunsNumber=device_row.get('duns_number'),
            gmdnTerms=gmdn_terms,
            productCodes=product_codes,
            deviceCount=device_row.get('device_count'),
            deviceCombinationProduct=device_row.get('is_combination_product', False),
            deviceKit=device_row.get('is_kit', False),
            singleUse=device_row.get('is_single_use', False),
            deviceSterile=device_row.get('is_sterile', False),
            rx=device_row.get('is_rx', False),
            otc=device_row.get('is_otc', False),
            deviceCommDistributionStatus=device_row.get('device_status', 'Unknown'),
            devicePublishDate=device_row.get('device_publish_date'),
            identifiers=identifiers
        )

    def search_exact(self, query: str, limit: int = 100) -> List[DeviceMatch]:
        """Search for exact matches across all fields."""
        if not self.conn:
            self.connect()

        matches = []

        # Search brand name (exact)
        brand_results = self.conn.execute("""
            SELECT * FROM devices
            WHERE LOWER(brand_name) = LOWER(?)
            LIMIT ?
        """, [query, limit]).fetchdf()

        for _, row in brand_results.iterrows():
            device = self._build_device_concept(row.to_dict())
            matches.append(DeviceMatch(
                device=device,
                match_type=MatchType.EXACT_BRAND,
                match_field="brand_name",
                match_value=row['brand_name'],
                match_query=query,
                confidence=1.0
            ))

        # Search company name (exact)
        company_results = self.conn.execute("""
            SELECT * FROM devices
            WHERE LOWER(company_name) = LOWER(?)
            LIMIT ?
        """, [query, limit]).fetchdf()

        for _, row in company_results.iterrows():
            device = self._build_device_concept(row.to_dict())
            matches.append(DeviceMatch(
                device=device,
                match_type=MatchType.EXACT_COMPANY,
                match_field="company_name",
                match_value=row['company_name'],
                match_query=query,
                confidence=1.0
            ))

        # Search product code (exact)
        code_results = self.conn.execute("""
            SELECT DISTINCT d.* FROM devices d
            JOIN product_codes pc ON d.public_device_record_key = pc.device_key
            WHERE LOWER(pc.product_code) = LOWER(?)
            LIMIT ?
        """, [query, limit]).fetchdf()

        for _, row in code_results.iterrows():
            device = self._build_device_concept(row.to_dict())
            matches.append(DeviceMatch(
                device=device,
                match_type=MatchType.EXACT_PRODUCT_CODE,
                match_field="product_code",
                match_value=query.upper(),
                match_query=query,
                confidence=1.0
            ))

        # Search primary DI (exact)
        di_results = self.conn.execute("""
            SELECT * FROM devices
            WHERE primary_di = ?
            LIMIT ?
        """, [query, limit]).fetchdf()

        for _, row in di_results.iterrows():
            device = self._build_device_concept(row.to_dict())
            matches.append(DeviceMatch(
                device=device,
                match_type=MatchType.EXACT_DI,
                match_field="primary_di",
                match_value=row['primary_di'],
                match_query=query,
                confidence=1.0
            ))

        return matches

    def search_fuzzy(self, query: str, min_confidence: float = 0.7, limit: int = 100, progress_callback=None, min_devices_per_code: int = 2) -> List[DeviceMatch]:
        """Search for fuzzy matches across text fields.

        Args:
            query: Search query
            min_confidence: Minimum confidence for fuzzy matches
            limit: Maximum results
            progress_callback: Callback for progress updates
            min_devices_per_code: Minimum devices a product code must have to be included (default 2)
        """
        if not self.conn:
            self.connect()

        matches = []

        if progress_callback:
            progress_callback("Stage 1/5: brand names", len(matches))
        # Search brand name (fuzzy)
        brand_results = self.conn.execute("""
            SELECT * FROM devices
            WHERE brand_name IS NOT NULL
            AND (
                LOWER(brand_name) LIKE LOWER(?)
                OR LOWER(brand_name) LIKE LOWER(?)
                OR LOWER(brand_name) LIKE LOWER(?)
            )
            LIMIT ?
        """, [f"%{query}%", f"{query}%", f"%{query}", limit * 2]).fetchdf()

        for _, row in brand_results.iterrows():
            similarity = self._calculate_similarity(query, row['brand_name'])
            if similarity >= min_confidence:
                device = self._build_device_concept(row.to_dict())
                matches.append(DeviceMatch(
                    device=device,
                    match_type=MatchType.FUZZY_BRAND,
                    match_field="brand_name",
                    match_value=row['brand_name'],
                    match_query=query,
                    confidence=similarity
                ))

        if progress_callback:
            progress_callback("Stage 2/5: device descriptions", len(matches))
        # Search device description (fuzzy) with better relevance ordering
        desc_results = self.conn.execute("""
            SELECT * FROM devices
            WHERE device_description IS NOT NULL
            AND LOWER(device_description) LIKE LOWER(?)
            ORDER BY
                CASE
                    -- Prioritize exact word matches
                    WHEN LOWER(device_description) LIKE LOWER(?) THEN 1
                    WHEN LOWER(device_description) LIKE LOWER(?) THEN 2
                    -- Prioritize surgical/N95/respirator keywords
                    WHEN LOWER(device_description) LIKE '%surgical%' THEN 3
                    WHEN LOWER(device_description) LIKE '%n95%' THEN 4
                    WHEN LOWER(device_description) LIKE '%respirator%' THEN 5
                    -- Then general matches
                    ELSE 6
                END,
                LENGTH(device_description)  -- Shorter descriptions often more relevant
            LIMIT ?
        """, [f"%{query}%", f"% {query} %", f"{query} %", limit]).fetchdf()

        for _, row in desc_results.iterrows():
            # For description, use presence of term rather than full string similarity
            confidence = 0.8 if query.lower() in row['device_description'].lower() else 0.7
            device = self._build_device_concept(row.to_dict())
            matches.append(DeviceMatch(
                device=device,
                match_type=MatchType.FUZZY_DESCRIPTION,
                match_field="device_description",
                match_value=row['device_description'][:100] + "...",
                match_query=query,
                confidence=confidence
            ))

        if progress_callback:
            progress_callback("Stage 3/5: company names", len(matches))
        # Search company name (fuzzy)
        company_results = self.conn.execute("""
            SELECT * FROM devices
            WHERE company_name IS NOT NULL
            AND LOWER(company_name) LIKE LOWER(?)
            LIMIT ?
        """, [f"%{query}%", limit]).fetchdf()

        for _, row in company_results.iterrows():
            similarity = self._calculate_similarity(query, row['company_name'])
            if similarity >= min_confidence:
                device = self._build_device_concept(row.to_dict())
                matches.append(DeviceMatch(
                    device=device,
                    match_type=MatchType.FUZZY_COMPANY,
                    match_field="company_name",
                    match_value=row['company_name'],
                    match_query=query,
                    confidence=similarity
                ))

        if progress_callback:
            progress_callback("Stage 4/5: GMDN terms", len(matches))
        # Search GMDN terms (fuzzy)
        gmdn_results = self.conn.execute("""
            SELECT DISTINCT d.* FROM devices d
            JOIN gmdn_terms g ON d.public_device_record_key = g.device_key
            WHERE g.gmdn_pt_name IS NOT NULL
            AND LOWER(g.gmdn_pt_name) LIKE LOWER(?)
            LIMIT ?
        """, [f"%{query}%", limit]).fetchdf()

        for _, row in gmdn_results.iterrows():
            device = self._build_device_concept(row.to_dict())
            # Get the matching GMDN term
            gmdn_match = self.conn.execute("""
                SELECT gmdn_pt_name FROM gmdn_terms
                WHERE device_key = ?
                AND LOWER(gmdn_pt_name) LIKE LOWER(?)
                LIMIT 1
            """, [row['public_device_record_key'], f"%{query}%"]).fetchone()

            if gmdn_match:
                confidence = 0.8 if query.lower() in gmdn_match[0].lower() else 0.7
                matches.append(DeviceMatch(
                    device=device,
                    match_type=MatchType.FUZZY_GMDN_NAME,
                    match_field="gmdn_pt_name",
                    match_value=gmdn_match[0],
                    match_query=query,
                    confidence=confidence
                ))

        if progress_callback:
            progress_callback("Stage 5/5: product codes", len(matches))
        # Search product code names (fuzzy)
        product_code_results = self.conn.execute("""
            SELECT DISTINCT d.*, pc.product_code, pc.product_code_name
            FROM devices d
            JOIN product_codes pc ON d.public_device_record_key = pc.device_key
            WHERE pc.product_code_name IS NOT NULL
            AND LOWER(pc.product_code_name) LIKE LOWER(?)
            LIMIT ?
        """, [f"%{query}%", limit]).fetchdf()

        for _, row in product_code_results.iterrows():
            device = self._build_device_concept(row.to_dict())
            confidence = 0.85 if query.lower() in row['product_code_name'].lower() else 0.75
            matches.append(DeviceMatch(
                device=device,
                match_type=MatchType.FUZZY_PRODUCT_CODE_NAME,
                match_field="product_code_name",
                match_value=f"{row['product_code']}: {row['product_code_name']}",
                match_query=query,
                confidence=confidence
            ))

        # Filter to only include devices with product codes that have >= min_devices_per_code matches
        if min_devices_per_code > 1 and matches:
            if progress_callback:
                progress_callback("Filtering by product code frequency", len(matches))

            # Count devices per product code
            product_code_counts: Dict[str, int] = {}
            for match in matches:
                for pc in match.device.get_product_codes():
                    product_code_counts[pc] = product_code_counts.get(pc, 0) + 1

            # Get product codes that meet the threshold
            qualifying_codes = {pc for pc, count in product_code_counts.items() if count >= min_devices_per_code}

            # Filter matches to only those with qualifying product codes
            filtered_matches = []
            for match in matches:
                device_codes = set(match.device.get_product_codes())
                if device_codes & qualifying_codes:  # intersection - has at least one qualifying code
                    filtered_matches.append(match)

            if progress_callback:
                progress_callback(f"Filtered to {len(qualifying_codes)} product codes", len(filtered_matches))

            return filtered_matches

        return matches

    def _normalize_query(self, query: str) -> list[str]:
        """Generate query variants to improve search coverage."""
        variants = [query]
        q_lower = query.lower().strip()
        if q_lower.endswith('s') and len(q_lower) > 3:
            variants.append(q_lower[:-1])
        elif not q_lower.endswith('s'):
            variants.append(q_lower + 's')
        if q_lower.endswith('es') and len(q_lower) > 4:
            variants.append(q_lower[:-2])
        return list(set(variants))

    def resolve(self, query: str, limit: int = 100, fuzzy: bool = True, min_confidence: float = 0.7, progress_callback=None, min_devices_per_code: int = 2) -> ResolverResponse:
        """
        Main resolve method that combines exact and fuzzy matching.

        Args:
            query: Search query string
            limit: Maximum number of results
            fuzzy: Whether to include fuzzy matches
            min_confidence: Minimum confidence score for fuzzy matches
            progress_callback: Optional callback function(step: str, count: int) for progress updates
            min_devices_per_code: Minimum devices a product code must have to be included (default 2)

        Returns:
            ResolverResponse with all matching devices
        """
        if not self.conn:
            self.connect()

        start_time = time.time()
        query_variants = self._normalize_query(query)

        all_matches = []
        for variant in query_variants:
            if progress_callback:
                progress_callback("Searching exact matches", len(all_matches))
            exact_matches = self.search_exact(variant, limit)
            all_matches.extend(exact_matches)
            if fuzzy:
                fuzzy_matches = self.search_fuzzy(variant, min_confidence, limit * 2, progress_callback=progress_callback, min_devices_per_code=min_devices_per_code)
                all_matches.extend(fuzzy_matches)

        seen_combinations = set()
        unique_matches = []

        for match in all_matches:
            product_codes = tuple(sorted(match.device.get_product_codes()))
            key = (
                match.device.company_name,
                match.device.brand_name,
                product_codes
            )
            if key not in seen_combinations:
                seen_combinations.add(key)
                unique_matches.append(match)

        unique_matches.sort(key=lambda x: x.confidence, reverse=True)
        unique_matches = unique_matches[:limit]

        execution_time = (time.time() - start_time) * 1000

        search_fields = [
            "brand_name", "company_name", "device_description",
            "product_code", "gmdn_pt_name", "primary_di"
        ]

        return ResolverResponse(
            query=query,
            total_matches=len(unique_matches),
            matches=unique_matches,
            search_fields=search_fields,
            execution_time_ms=execution_time
        )


def resolve_device(query: str, db_path: str = "gudid.db", **kwargs) -> ResolverResponse:
    """
    Convenience function to resolve a device query.

    Args:
        query: Search query
        db_path: Path to GUDID database
        **kwargs: Additional arguments passed to resolve()

    Returns:
        ResolverResponse with matching devices
    """
    resolver = DeviceResolver(db_path)
    try:
        return resolver.resolve(query, **kwargs)
    finally:
        resolver.close()
