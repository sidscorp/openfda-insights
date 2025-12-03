"""
GUDID XML data indexer for DuckDB.
Parses AccessGUDID XML files and creates searchable database.
"""
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional
import duckdb
from tqdm import tqdm
import logging
from datetime import datetime

# Only show INFO and above, not DEBUG
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# XML namespace for GUDID
GUDID_NS = {'gudid': 'http://www.fda.gov/cdrh/gudid'}


class GUDIDIndexer:
    """Indexes GUDID XML data into DuckDB for fast searching."""

    def __init__(self, db_path: str = "gudid.db"):
        """Initialize indexer with database path."""
        self.db_path = db_path
        self.conn = None
        self.total_records = 0

    def connect(self):
        """Connect to DuckDB database."""
        self.conn = duckdb.connect(self.db_path)
        logger.info(f"Connected to database: {self.db_path}")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def create_tables(self):
        """Create database tables for GUDID data."""
        if not self.conn:
            raise RuntimeError("Not connected to database")

        # Main devices table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                public_device_record_key VARCHAR PRIMARY KEY,
                primary_di VARCHAR,
                brand_name VARCHAR,
                version_model_number VARCHAR,
                catalog_number VARCHAR,
                device_description TEXT,
                company_name VARCHAR,
                duns_number VARCHAR,
                device_count INTEGER,
                device_status VARCHAR,
                device_publish_date DATE,
                is_combination_product BOOLEAN,
                is_kit BOOLEAN,
                is_single_use BOOLEAN,
                is_sterile BOOLEAN,
                is_rx BOOLEAN,
                is_otc BOOLEAN,
                indexed_at TIMESTAMP
            )
        """)

        # GMDN terms table
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS gmdn_terms_seq START 1;
            CREATE TABLE IF NOT EXISTS gmdn_terms (
                id INTEGER PRIMARY KEY DEFAULT nextval('gmdn_terms_seq'),
                device_key VARCHAR REFERENCES devices(public_device_record_key),
                gmdn_code VARCHAR,
                gmdn_pt_name VARCHAR,
                gmdn_pt_definition TEXT,
                implantable BOOLEAN,
                gmdn_code_status VARCHAR
            )
        """)

        # Product codes table
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS product_codes_seq START 1;
            CREATE TABLE IF NOT EXISTS product_codes (
                id INTEGER PRIMARY KEY DEFAULT nextval('product_codes_seq'),
                device_key VARCHAR REFERENCES devices(public_device_record_key),
                product_code VARCHAR,
                product_code_name VARCHAR
            )
        """)

        # Device identifiers table
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS device_identifiers_seq START 1;
            CREATE TABLE IF NOT EXISTS device_identifiers (
                id INTEGER PRIMARY KEY DEFAULT nextval('device_identifiers_seq'),
                device_key VARCHAR REFERENCES devices(public_device_record_key),
                device_id VARCHAR,
                device_id_type VARCHAR,
                device_id_issuing_agency VARCHAR,
                pkg_quantity INTEGER,
                pkg_type VARCHAR
            )
        """)

        # Create indexes for search performance
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_brand_name ON devices(brand_name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_company_name ON devices(company_name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_device_description ON devices(device_description)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_primary_di ON devices(primary_di)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_product_code ON product_codes(product_code)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_gmdn_code ON gmdn_terms(gmdn_code)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_gmdn_name ON gmdn_terms(gmdn_pt_name)")

        logger.info("Database tables and indexes created")

    def parse_device(self, device_elem: ET.Element) -> Dict[str, Any]:
        """Parse a single device element from XML."""
        def get_text(elem: ET.Element, path: str, default=None):
            """Safely get text from XML element."""
            found = elem.find(path, GUDID_NS)
            if found is not None and found.text:
                return found.text.strip()
            return default

        def get_bool(elem: ET.Element, path: str, default=False):
            """Safely get boolean value from XML element."""
            text = get_text(elem, path)
            if text:
                return text.lower() == 'true'
            return default

        device_data = {
            'public_device_record_key': get_text(device_elem, 'gudid:publicDeviceRecordKey'),
            'brand_name': get_text(device_elem, 'gudid:brandName'),
            'version_model_number': get_text(device_elem, 'gudid:versionModelNumber'),
            'catalog_number': get_text(device_elem, 'gudid:catalogNumber'),
            'device_description': get_text(device_elem, 'gudid:deviceDescription'),
            'company_name': get_text(device_elem, 'gudid:companyName'),
            'duns_number': get_text(device_elem, 'gudid:dunsNumber'),
            'device_count': get_text(device_elem, 'gudid:deviceCount'),
            'device_status': get_text(device_elem, 'gudid:deviceCommDistributionStatus'),
            'device_publish_date': get_text(device_elem, 'gudid:devicePublishDate'),
            'is_combination_product': get_bool(device_elem, 'gudid:deviceCombinationProduct'),
            'is_kit': get_bool(device_elem, 'gudid:deviceKit'),
            'is_single_use': get_bool(device_elem, 'gudid:singleUse'),
            'is_sterile': get_bool(device_elem, 'gudid:deviceSterile'),
            'is_rx': get_bool(device_elem, 'gudid:rx'),
            'is_otc': get_bool(device_elem, 'gudid:otc'),
        }

        # Parse identifiers
        identifiers = []
        identifiers_elem = device_elem.find('gudid:identifiers', GUDID_NS)
        if identifiers_elem:
            for identifier in identifiers_elem.findall('gudid:identifier', GUDID_NS):
                id_data = {
                    'device_id': get_text(identifier, 'gudid:deviceId'),
                    'device_id_type': get_text(identifier, 'gudid:deviceIdType'),
                    'device_id_issuing_agency': get_text(identifier, 'gudid:deviceIdIssuingAgency'),
                    'pkg_quantity': get_text(identifier, 'gudid:pkgQuantity'),
                    'pkg_type': get_text(identifier, 'gudid:pkgType'),
                }
                identifiers.append(id_data)
                # Set primary DI if this is the primary identifier
                if id_data['device_id_type'] == 'Primary':
                    device_data['primary_di'] = id_data['device_id']

        # Parse GMDN terms
        gmdn_terms = []
        gmdn_elem = device_elem.find('gudid:gmdnTerms', GUDID_NS)
        if gmdn_elem:
            for gmdn in gmdn_elem.findall('gudid:gmdn', GUDID_NS):
                gmdn_data = {
                    'gmdn_code': get_text(gmdn, 'gudid:gmdnCode'),
                    'gmdn_pt_name': get_text(gmdn, 'gudid:gmdnPTName'),
                    'gmdn_pt_definition': get_text(gmdn, 'gudid:gmdnPTDefinition'),
                    'implantable': get_bool(gmdn, 'gudid:implantable'),
                    'gmdn_code_status': get_text(gmdn, 'gudid:gmdnCodeStatus'),
                }
                gmdn_terms.append(gmdn_data)

        # Parse product codes
        product_codes = []
        codes_elem = device_elem.find('gudid:productCodes', GUDID_NS)
        if codes_elem:
            for code in codes_elem.findall('gudid:fdaProductCode', GUDID_NS):
                code_data = {
                    'product_code': get_text(code, 'gudid:productCode'),
                    'product_code_name': get_text(code, 'gudid:productCodeName'),
                }
                product_codes.append(code_data)

        return {
            'device': device_data,
            'identifiers': identifiers,
            'gmdn_terms': gmdn_terms,
            'product_codes': product_codes
        }

    def index_file(self, xml_path: str) -> int:
        """Index a single GUDID XML file."""
        if not self.conn:
            raise RuntimeError("Not connected to database")

        logger.info(f"Indexing file: {xml_path}")

        # Read file content and try to fix truncated XML
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # If file is truncated, try to close open tags
            if not content.rstrip().endswith('</gudid>'):
                # Find last complete device element
                last_device_end = content.rfind('</device>')
                if last_device_end > 0:
                    content = content[:last_device_end + len('</device>')] + '\n</gudid>'
                else:
                    # No complete devices found in this file
                    return 0

            # Parse the (possibly repaired) content
            root = ET.fromstring(content)
            devices = root.findall('.//gudid:device', GUDID_NS)
            indexed_count = 0

            for device_elem in devices:
                try:
                    device_data = self.parse_device(device_elem)

                    # Insert main device record
                    device = device_data['device']
                    device['indexed_at'] = datetime.now()

                    # Convert device_count to int if present
                    if device.get('device_count'):
                        try:
                            device['device_count'] = int(device['device_count'])
                        except:
                            device['device_count'] = None

                    # Insert device
                    self.conn.execute("""
                        INSERT OR REPLACE INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, tuple(device.get(k) for k in [
                        'public_device_record_key', 'primary_di', 'brand_name', 'version_model_number',
                        'catalog_number', 'device_description', 'company_name', 'duns_number',
                        'device_count', 'device_status', 'device_publish_date',
                        'is_combination_product', 'is_kit', 'is_single_use', 'is_sterile',
                        'is_rx', 'is_otc', 'indexed_at'
                    ]))

                    # Insert related records
                    device_key = device['public_device_record_key']

                    # Insert identifiers (only if they exist and have required data)
                    for identifier in device_data['identifiers']:
                        if identifier.get('device_id'):  # Only insert if device_id exists
                            try:
                                self.conn.execute("""
                                    INSERT INTO device_identifiers (device_key, device_id, device_id_type,
                                                                   device_id_issuing_agency, pkg_quantity, pkg_type)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (device_key, identifier['device_id'], identifier['device_id_type'],
                                      identifier['device_id_issuing_agency'], identifier.get('pkg_quantity'),
                                      identifier.get('pkg_type')))
                            except Exception as e:
                                logger.debug(f"Skipping identifier for device {device_key}: {e}")

                    # Insert GMDN terms (only if they exist and have required data)
                    for gmdn in device_data['gmdn_terms']:
                        if gmdn.get('gmdn_code'):  # Only insert if gmdn_code exists
                            try:
                                self.conn.execute("""
                                    INSERT INTO gmdn_terms (device_key, gmdn_code, gmdn_pt_name,
                                                            gmdn_pt_definition, implantable, gmdn_code_status)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (device_key, gmdn['gmdn_code'], gmdn.get('gmdn_pt_name'),
                                      gmdn.get('gmdn_pt_definition'), gmdn.get('implantable', False),
                                      gmdn.get('gmdn_code_status')))
                            except Exception as e:
                                logger.debug(f"Skipping GMDN term for device {device_key}: {e}")

                    # Insert product codes (only if they exist and have required data)
                    for code in device_data['product_codes']:
                        if code.get('product_code'):  # Only insert if product_code exists
                            try:
                                self.conn.execute("""
                                    INSERT INTO product_codes (device_key, product_code, product_code_name)
                                    VALUES (?, ?, ?)
                                """, (device_key, code['product_code'], code.get('product_code_name')))
                            except Exception as e:
                                logger.debug(f"Skipping product code for device {device_key}: {e}")

                    indexed_count += 1

                except Exception as e:
                    # Skip devices that fail to index silently
                    continue

            self.conn.commit()
            self.total_records += indexed_count
            logger.info(f"Indexed {indexed_count} devices from {xml_path}")
            return indexed_count

        except Exception as e:
            # Skip files that fail to parse
            return 0

    def index_directory(self, directory: str):
        """Index all GUDID XML files in a directory."""
        if not self.conn:
            self.connect()

        self.create_tables()

        xml_dir = Path(directory)
        xml_files = sorted(xml_dir.glob("*.xml"))

        logger.info(f"Found {len(xml_files)} XML files to index")

        for xml_file in tqdm(xml_files, desc="Indexing GUDID files"):
            self.index_file(str(xml_file))

        logger.info(f"Indexing complete. Total records: {self.total_records}")

        # Print statistics
        device_count = self.conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        gmdn_count = self.conn.execute("SELECT COUNT(DISTINCT gmdn_code) FROM gmdn_terms").fetchone()[0]
        product_code_count = self.conn.execute("SELECT COUNT(DISTINCT product_code) FROM product_codes").fetchone()[0]
        company_count = self.conn.execute("SELECT COUNT(DISTINCT company_name) FROM devices WHERE company_name IS NOT NULL").fetchone()[0]

        logger.info(f"Database statistics:")
        logger.info(f"  - Total devices: {device_count}")
        logger.info(f"  - Unique GMDN codes: {gmdn_count}")
        logger.info(f"  - Unique product codes: {product_code_count}")
        logger.info(f"  - Unique companies: {company_count}")

    def verify_index(self):
        """Verify the index with sample queries."""
        if not self.conn:
            self.connect()

        # Test queries
        test_queries = [
            "SELECT COUNT(*) FROM devices WHERE brand_name LIKE '%mask%'",
            "SELECT COUNT(*) FROM devices WHERE company_name LIKE '%3M%'",
            "SELECT COUNT(*) FROM devices WHERE device_description LIKE '%needle%'",
            "SELECT COUNT(DISTINCT d.public_device_record_key) FROM devices d JOIN product_codes pc ON d.public_device_record_key = pc.device_key WHERE pc.product_code IN ('FXX', 'MSH', 'CBK')",
        ]

        logger.info("Running verification queries:")
        for query in test_queries:
            result = self.conn.execute(query).fetchone()[0]
            logger.info(f"  {query[:50]}... => {result} results")


if __name__ == "__main__":
    # Index the GUDID data
    indexer = GUDIDIndexer("gudid.db")
    try:
        indexer.index_directory("gudid_full_release_20250804")
        indexer.verify_index()
    finally:
        indexer.close()
