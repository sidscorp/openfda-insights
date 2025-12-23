"""
GUDID XML data indexer for DuckDB.
Parses AccessGUDID XML files and creates searchable database.
Optimized for fast bulk loading with parallel processing and native DataFrame inserts.
"""
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import duckdb
from tqdm import tqdm
import logging
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# XML namespace for GUDID
GUDID_NS = {'gudid': 'http://www.fda.gov/cdrh/gudid'}

# Batch size for bulk inserts
BATCH_SIZE = 5000

# Number of parallel workers (use all cores)
NUM_WORKERS = max(1, multiprocessing.cpu_count() - 1)


def _parse_xml_file(xml_path: str) -> Tuple[List[tuple], List[tuple], List[tuple], List[tuple]]:
    """
    Parse a single XML file and return extracted data.
    This is a standalone function for multiprocessing.
    Returns: (devices, identifiers, gmdn_terms, product_codes)
    """
    devices = []
    identifiers = []
    gmdn_terms = []
    product_codes = []
    indexed_at = datetime.now()

    def get_text(elem, path, default=None):
        found = elem.find(path, GUDID_NS)
        if found is not None and found.text:
            return found.text.strip()
        return default

    def get_bool(elem, path, default=False):
        text = get_text(elem, path)
        if text:
            return text.lower() == 'true'
        return default

    try:
        context = ET.iterparse(xml_path, events=('end',))

        for event, elem in context:
            if elem.tag == '{http://www.fda.gov/cdrh/gudid}device':
                try:
                    # Parse device data
                    device_key = get_text(elem, 'gudid:publicDeviceRecordKey')
                    primary_di = None

                    # Parse identifiers
                    identifiers_elem = elem.find('gudid:identifiers', GUDID_NS)
                    if identifiers_elem:
                        for identifier in identifiers_elem.findall('gudid:identifier', GUDID_NS):
                            device_id = get_text(identifier, 'gudid:deviceId')
                            if device_id:
                                device_id_type = get_text(identifier, 'gudid:deviceIdType')
                                if device_id_type == 'Primary':
                                    primary_di = device_id
                                pkg_qty = get_text(identifier, 'gudid:pkgQuantity')
                                if pkg_qty:
                                    try:
                                        pkg_qty = int(pkg_qty)
                                    except:
                                        pkg_qty = None
                                identifiers.append((
                                    device_key, device_id, device_id_type,
                                    get_text(identifier, 'gudid:deviceIdIssuingAgency'),
                                    pkg_qty, get_text(identifier, 'gudid:pkgType')
                                ))

                    # Parse GMDN terms
                    gmdn_elem = elem.find('gudid:gmdnTerms', GUDID_NS)
                    if gmdn_elem:
                        for gmdn in gmdn_elem.findall('gudid:gmdn', GUDID_NS):
                            gmdn_code = get_text(gmdn, 'gudid:gmdnCode')
                            if gmdn_code:
                                gmdn_terms.append((
                                    device_key, gmdn_code,
                                    get_text(gmdn, 'gudid:gmdnPTName'),
                                    get_text(gmdn, 'gudid:gmdnPTDefinition'),
                                    get_bool(gmdn, 'gudid:implantable'),
                                    get_text(gmdn, 'gudid:gmdnCodeStatus')
                                ))

                    # Parse product codes
                    codes_elem = elem.find('gudid:productCodes', GUDID_NS)
                    if codes_elem:
                        for code in codes_elem.findall('gudid:fdaProductCode', GUDID_NS):
                            pc = get_text(code, 'gudid:productCode')
                            if pc:
                                product_codes.append((
                                    device_key, pc, get_text(code, 'gudid:productCodeName')
                                ))

                    # Parse device count
                    device_count = get_text(elem, 'gudid:deviceCount')
                    if device_count:
                        try:
                            device_count = int(device_count)
                        except:
                            device_count = None

                    # Add device
                    devices.append((
                        device_key, primary_di,
                        get_text(elem, 'gudid:brandName'),
                        get_text(elem, 'gudid:versionModelNumber'),
                        get_text(elem, 'gudid:catalogNumber'),
                        get_text(elem, 'gudid:deviceDescription'),
                        get_text(elem, 'gudid:companyName'),
                        get_text(elem, 'gudid:dunsNumber'),
                        device_count,
                        get_text(elem, 'gudid:deviceCommDistributionStatus'),
                        get_text(elem, 'gudid:devicePublishDate'),
                        get_bool(elem, 'gudid:deviceCombinationProduct'),
                        get_bool(elem, 'gudid:deviceKit'),
                        get_bool(elem, 'gudid:singleUse'),
                        get_bool(elem, 'gudid:deviceSterile'),
                        get_bool(elem, 'gudid:rx'),
                        get_bool(elem, 'gudid:otc'),
                        indexed_at
                    ))

                except Exception:
                    pass

                elem.clear()

    except ET.ParseError:
        # Fallback for malformed XML
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if not content.rstrip().endswith('</gudid>'):
                last_device_end = content.rfind('</device>')
                if last_device_end > 0:
                    content = content[:last_device_end + len('</device>')] + '\n</gudid>'
                else:
                    return devices, identifiers, gmdn_terms, product_codes

            root = ET.fromstring(content)
            for elem in root.findall('.//gudid:device', GUDID_NS):
                # Same parsing logic (abbreviated for fallback)
                device_key = get_text(elem, 'gudid:publicDeviceRecordKey')
                if device_key:
                    devices.append((
                        device_key, None,
                        get_text(elem, 'gudid:brandName'),
                        get_text(elem, 'gudid:versionModelNumber'),
                        get_text(elem, 'gudid:catalogNumber'),
                        get_text(elem, 'gudid:deviceDescription'),
                        get_text(elem, 'gudid:companyName'),
                        get_text(elem, 'gudid:dunsNumber'),
                        None, None, None, False, False, False, False, False, False, indexed_at
                    ))
        except Exception:
            pass

    except Exception:
        pass

    return devices, identifiers, gmdn_terms, product_codes


class GUDIDIndexer:
    """Indexes GUDID XML data into DuckDB for fast searching."""

    def __init__(self, db_path: str = "gudid.db"):
        """Initialize indexer with database path."""
        self.db_path = db_path
        self.conn = None
        self.total_records = 0

        # Batch buffers
        self._devices_batch: List[tuple] = []
        self._identifiers_batch: List[tuple] = []
        self._gmdn_batch: List[tuple] = []
        self._product_codes_batch: List[tuple] = []

    def connect(self):
        """Connect to DuckDB database."""
        self.conn = duckdb.connect(self.db_path)
        logger.info(f"Connected to database: {self.db_path}")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def create_tables(self, with_indexes: bool = False):
        """Create database tables for GUDID data."""
        if not self.conn:
            raise RuntimeError("Not connected to database")

        # Drop existing tables for clean rebuild
        self.conn.execute("DROP TABLE IF EXISTS device_identifiers")
        self.conn.execute("DROP TABLE IF EXISTS gmdn_terms")
        self.conn.execute("DROP TABLE IF EXISTS product_codes")
        self.conn.execute("DROP TABLE IF EXISTS devices")

        # Main devices table
        self.conn.execute("""
            CREATE TABLE devices (
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
            CREATE TABLE gmdn_terms (
                id INTEGER PRIMARY KEY,
                device_key VARCHAR,
                gmdn_code VARCHAR,
                gmdn_pt_name VARCHAR,
                gmdn_pt_definition TEXT,
                implantable BOOLEAN,
                gmdn_code_status VARCHAR
            )
        """)

        # Product codes table
        self.conn.execute("""
            CREATE TABLE product_codes (
                id INTEGER PRIMARY KEY,
                device_key VARCHAR,
                product_code VARCHAR,
                product_code_name VARCHAR
            )
        """)

        # Device identifiers table
        self.conn.execute("""
            CREATE TABLE device_identifiers (
                id INTEGER PRIMARY KEY,
                device_key VARCHAR,
                device_id VARCHAR,
                device_id_type VARCHAR,
                device_id_issuing_agency VARCHAR,
                pkg_quantity INTEGER,
                pkg_type VARCHAR
            )
        """)

        if with_indexes:
            self._create_indexes()

        logger.info("Database tables created")

    def _create_indexes(self):
        """Create indexes for search performance (call after bulk load)."""
        logger.info("Creating indexes...")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_brand_name ON devices(brand_name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_company_name ON devices(company_name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_primary_di ON devices(primary_di)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_pc_device_key ON product_codes(device_key)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_product_code ON product_codes(product_code)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_gmdn_device_key ON gmdn_terms(device_key)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_gmdn_code ON gmdn_terms(gmdn_code)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_gmdn_name ON gmdn_terms(gmdn_pt_name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_di_device_key ON device_identifiers(device_key)")
        logger.info("Indexes created")

    def _flush_batches(self):
        """Flush all batch buffers to database."""
        if self._devices_batch:
            self.conn.executemany("""
                INSERT OR REPLACE INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, self._devices_batch)
            self._devices_batch = []

        if self._identifiers_batch:
            self.conn.executemany("""
                INSERT INTO device_identifiers (id, device_key, device_id, device_id_type,
                                               device_id_issuing_agency, pkg_quantity, pkg_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, self._identifiers_batch)
            self._identifiers_batch = []

        if self._gmdn_batch:
            self.conn.executemany("""
                INSERT INTO gmdn_terms (id, device_key, gmdn_code, gmdn_pt_name,
                                        gmdn_pt_definition, implantable, gmdn_code_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, self._gmdn_batch)
            self._gmdn_batch = []

        if self._product_codes_batch:
            self.conn.executemany("""
                INSERT INTO product_codes (id, device_key, product_code, product_code_name)
                VALUES (?, ?, ?, ?)
            """, self._product_codes_batch)
            self._product_codes_batch = []

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

    def index_file(self, xml_path: str, id_counter: Dict[str, int]) -> int:
        """Index a single GUDID XML file using streaming iterparse."""
        if not self.conn:
            raise RuntimeError("Not connected to database")

        indexed_count = 0
        indexed_at = datetime.now()

        try:
            # Use iterparse for streaming - much faster for large files
            context = ET.iterparse(xml_path, events=('end',))

            for event, elem in context:
                # Only process device elements
                if elem.tag == '{http://www.fda.gov/cdrh/gudid}device':
                    try:
                        device_data = self.parse_device(elem)
                        device = device_data['device']
                        device['indexed_at'] = indexed_at

                        # Convert device_count to int
                        if device.get('device_count'):
                            try:
                                device['device_count'] = int(device['device_count'])
                            except:
                                device['device_count'] = None

                        # Add to devices batch
                        self._devices_batch.append(tuple(device.get(k) for k in [
                            'public_device_record_key', 'primary_di', 'brand_name', 'version_model_number',
                            'catalog_number', 'device_description', 'company_name', 'duns_number',
                            'device_count', 'device_status', 'device_publish_date',
                            'is_combination_product', 'is_kit', 'is_single_use', 'is_sterile',
                            'is_rx', 'is_otc', 'indexed_at'
                        ]))

                        device_key = device['public_device_record_key']

                        # Add identifiers to batch
                        for identifier in device_data['identifiers']:
                            if identifier.get('device_id'):
                                id_counter['identifiers'] += 1
                                pkg_qty = identifier.get('pkg_quantity')
                                if pkg_qty:
                                    try:
                                        pkg_qty = int(pkg_qty)
                                    except:
                                        pkg_qty = None
                                self._identifiers_batch.append((
                                    id_counter['identifiers'], device_key, identifier['device_id'],
                                    identifier['device_id_type'], identifier['device_id_issuing_agency'],
                                    pkg_qty, identifier.get('pkg_type')
                                ))

                        # Add GMDN terms to batch
                        for gmdn in device_data['gmdn_terms']:
                            if gmdn.get('gmdn_code'):
                                id_counter['gmdn'] += 1
                                self._gmdn_batch.append((
                                    id_counter['gmdn'], device_key, gmdn['gmdn_code'],
                                    gmdn.get('gmdn_pt_name'), gmdn.get('gmdn_pt_definition'),
                                    gmdn.get('implantable', False), gmdn.get('gmdn_code_status')
                                ))

                        # Add product codes to batch
                        for code in device_data['product_codes']:
                            if code.get('product_code'):
                                id_counter['product_codes'] += 1
                                self._product_codes_batch.append((
                                    id_counter['product_codes'], device_key,
                                    code['product_code'], code.get('product_code_name')
                                ))

                        indexed_count += 1

                        # Flush batches when they get large
                        if len(self._devices_batch) >= BATCH_SIZE:
                            self._flush_batches()

                    except Exception:
                        pass

                    # Clear element to free memory (critical for iterparse)
                    elem.clear()

            self.total_records += indexed_count
            return indexed_count

        except ET.ParseError:
            # Handle truncated/malformed XML by falling back to manual repair
            return self._index_file_fallback(xml_path, id_counter, indexed_at)
        except Exception:
            return 0

    def _index_file_fallback(self, xml_path: str, id_counter: Dict[str, int], indexed_at: datetime) -> int:
        """Fallback for truncated XML files - repairs and parses."""
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.rstrip().endswith('</gudid>'):
                last_device_end = content.rfind('</device>')
                if last_device_end > 0:
                    content = content[:last_device_end + len('</device>')] + '\n</gudid>'
                else:
                    return 0

            root = ET.fromstring(content)
            devices = root.findall('.//gudid:device', GUDID_NS)
            indexed_count = 0

            for device_elem in devices:
                try:
                    device_data = self.parse_device(device_elem)
                    device = device_data['device']
                    device['indexed_at'] = indexed_at

                    if device.get('device_count'):
                        try:
                            device['device_count'] = int(device['device_count'])
                        except:
                            device['device_count'] = None

                    self._devices_batch.append(tuple(device.get(k) for k in [
                        'public_device_record_key', 'primary_di', 'brand_name', 'version_model_number',
                        'catalog_number', 'device_description', 'company_name', 'duns_number',
                        'device_count', 'device_status', 'device_publish_date',
                        'is_combination_product', 'is_kit', 'is_single_use', 'is_sterile',
                        'is_rx', 'is_otc', 'indexed_at'
                    ]))

                    device_key = device['public_device_record_key']

                    for identifier in device_data['identifiers']:
                        if identifier.get('device_id'):
                            id_counter['identifiers'] += 1
                            pkg_qty = identifier.get('pkg_quantity')
                            if pkg_qty:
                                try:
                                    pkg_qty = int(pkg_qty)
                                except:
                                    pkg_qty = None
                            self._identifiers_batch.append((
                                id_counter['identifiers'], device_key, identifier['device_id'],
                                identifier['device_id_type'], identifier['device_id_issuing_agency'],
                                pkg_qty, identifier.get('pkg_type')
                            ))

                    for gmdn in device_data['gmdn_terms']:
                        if gmdn.get('gmdn_code'):
                            id_counter['gmdn'] += 1
                            self._gmdn_batch.append((
                                id_counter['gmdn'], device_key, gmdn['gmdn_code'],
                                gmdn.get('gmdn_pt_name'), gmdn.get('gmdn_pt_definition'),
                                gmdn.get('implantable', False), gmdn.get('gmdn_code_status')
                            ))

                    for code in device_data['product_codes']:
                        if code.get('product_code'):
                            id_counter['product_codes'] += 1
                            self._product_codes_batch.append((
                                id_counter['product_codes'], device_key,
                                code['product_code'], code.get('product_code_name')
                            ))

                    indexed_count += 1

                    if len(self._devices_batch) >= BATCH_SIZE:
                        self._flush_batches()

                except Exception:
                    continue

            self.total_records += indexed_count
            return indexed_count

        except Exception:
            return 0

    def index_directory(self, directory: str):
        """Index all GUDID XML files in a directory using parallel processing."""
        if not self.conn:
            self.connect()

        # Create tables WITHOUT indexes for faster bulk loading
        self.create_tables(with_indexes=False)

        xml_dir = Path(directory)
        xml_files = sorted(xml_dir.glob("*.xml"))

        logger.info(f"Found {len(xml_files)} XML files to index")
        logger.info(f"Using {NUM_WORKERS} parallel workers")

        # Process files in parallel
        all_devices = []
        all_identifiers = []
        all_gmdn = []
        all_product_codes = []

        with ProcessPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = {executor.submit(_parse_xml_file, str(f)): f for f in xml_files}

            for future in tqdm(as_completed(futures), total=len(xml_files), desc="Parsing XML files"):
                try:
                    devices, identifiers, gmdn_terms, product_codes = future.result()
                    all_devices.extend(devices)
                    all_identifiers.extend(identifiers)
                    all_gmdn.extend(gmdn_terms)
                    all_product_codes.extend(product_codes)
                except Exception as e:
                    logger.debug(f"Error processing file: {e}")

        logger.info(f"Parsed {len(all_devices)} devices, inserting into database...")

        # Use pandas DataFrames for fast bulk insert (DuckDB native support)
        if all_devices:
            logger.info("Inserting devices...")
            df_devices = pd.DataFrame(all_devices, columns=[
                'public_device_record_key', 'primary_di', 'brand_name', 'version_model_number',
                'catalog_number', 'device_description', 'company_name', 'duns_number',
                'device_count', 'device_status', 'device_publish_date',
                'is_combination_product', 'is_kit', 'is_single_use', 'is_sterile',
                'is_rx', 'is_otc', 'indexed_at'
            ])
            self.conn.execute("INSERT OR REPLACE INTO devices SELECT * FROM df_devices")

        if all_identifiers:
            logger.info("Inserting device identifiers...")
            df_identifiers = pd.DataFrame(all_identifiers, columns=[
                'device_key', 'device_id', 'device_id_type',
                'device_id_issuing_agency', 'pkg_quantity', 'pkg_type'
            ])
            df_identifiers.insert(0, 'id', range(1, len(df_identifiers) + 1))
            self.conn.execute("INSERT INTO device_identifiers SELECT * FROM df_identifiers")

        if all_gmdn:
            logger.info("Inserting GMDN terms...")
            df_gmdn = pd.DataFrame(all_gmdn, columns=[
                'device_key', 'gmdn_code', 'gmdn_pt_name',
                'gmdn_pt_definition', 'implantable', 'gmdn_code_status'
            ])
            df_gmdn.insert(0, 'id', range(1, len(df_gmdn) + 1))
            self.conn.execute("INSERT INTO gmdn_terms SELECT * FROM df_gmdn")

        if all_product_codes:
            logger.info("Inserting product codes...")
            df_product_codes = pd.DataFrame(all_product_codes, columns=[
                'device_key', 'product_code', 'product_code_name'
            ])
            df_product_codes.insert(0, 'id', range(1, len(df_product_codes) + 1))
            self.conn.execute("INSERT INTO product_codes SELECT * FROM df_product_codes")

        self.conn.commit()
        self.total_records = len(all_devices)

        # Create indexes AFTER bulk load
        self._create_indexes()

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

    def index_directory_batched(self, directory: str, batch_size: int = 40):
        """Memory-optimized indexing: processes files in batches to avoid OOM."""
        if not self.conn:
            self.connect()

        self.create_tables(with_indexes=False)

        xml_dir = Path(directory)
        xml_files = sorted(xml_dir.glob("*.xml"))

        logger.info(f"Found {len(xml_files)} XML files to index")
        logger.info(f"Processing in batches of {batch_size} files")

        total_devices = 0
        id_counter = {'identifiers': 0, 'gmdn': 0, 'product_codes': 0}

        for i in range(0, len(xml_files), batch_size):
            batch = xml_files[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(xml_files) + batch_size - 1)//batch_size} ({len(batch)} files)")

            batch_devices = []
            batch_identifiers = []
            batch_gmdn = []
            batch_product_codes = []

            with ProcessPoolExecutor(max_workers=1) as executor:
                futures = {executor.submit(_parse_xml_file, str(f)): f for f in batch}

                for future in tqdm(as_completed(futures), total=len(batch), desc=f"Batch {i//batch_size + 1}"):
                    try:
                        devices, identifiers, gmdn_terms, product_codes = future.result()
                        batch_devices.extend(devices)
                        batch_identifiers.extend(identifiers)
                        batch_gmdn.extend(gmdn_terms)
                        batch_product_codes.extend(product_codes)
                    except Exception as e:
                        logger.debug(f"Error: {e}")

            if batch_devices:
                logger.info(f"Inserting {len(batch_devices)} devices from batch...")
                df_devices = pd.DataFrame(batch_devices, columns=[
                    'public_device_record_key', 'primary_di', 'brand_name', 'version_model_number',
                    'catalog_number', 'device_description', 'company_name', 'duns_number',
                    'device_count', 'device_status', 'device_publish_date',
                    'is_combination_product', 'is_kit', 'is_single_use', 'is_sterile',
                    'is_rx', 'is_otc', 'indexed_at'
                ])
                self.conn.execute("INSERT OR REPLACE INTO devices SELECT * FROM df_devices")
                total_devices += len(batch_devices)
                del df_devices

            if batch_identifiers:
                df_identifiers = pd.DataFrame(batch_identifiers, columns=[
                    'device_key', 'device_id', 'device_id_type',
                    'device_id_issuing_agency', 'pkg_quantity', 'pkg_type'
                ])
                df_identifiers.insert(0, 'id', range(id_counter['identifiers'] + 1, id_counter['identifiers'] + len(df_identifiers) + 1))
                self.conn.execute("INSERT INTO device_identifiers SELECT * FROM df_identifiers")
                id_counter['identifiers'] += len(df_identifiers)
                del df_identifiers

            if batch_gmdn:
                df_gmdn = pd.DataFrame(batch_gmdn, columns=[
                    'device_key', 'gmdn_code', 'gmdn_pt_name',
                    'gmdn_pt_definition', 'implantable', 'gmdn_code_status'
                ])
                df_gmdn.insert(0, 'id', range(id_counter['gmdn'] + 1, id_counter['gmdn'] + len(df_gmdn) + 1))
                self.conn.execute("INSERT INTO gmdn_terms SELECT * FROM df_gmdn")
                id_counter['gmdn'] += len(df_gmdn)
                del df_gmdn

            if batch_product_codes:
                df_product_codes = pd.DataFrame(batch_product_codes, columns=[
                    'device_key', 'product_code', 'product_code_name'
                ])
                df_product_codes.insert(0, 'id', range(id_counter['product_codes'] + 1, id_counter['product_codes'] + len(df_product_codes) + 1))
                self.conn.execute("INSERT INTO product_codes SELECT * FROM df_product_codes")
                id_counter['product_codes'] += len(df_product_codes)
                del df_product_codes

            self.conn.commit()
            logger.info(f"Batch complete. Total devices so far: {total_devices}")

        self.total_records = total_devices
        self._create_indexes()

        logger.info(f"Indexing complete. Total records: {self.total_records}")

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

        test_queries = [
            "SELECT COUNT(*) FROM devices WHERE brand_name ILIKE '%mask%'",
            "SELECT COUNT(*) FROM devices WHERE company_name ILIKE '%3M%'",
            "SELECT COUNT(*) FROM devices WHERE device_description ILIKE '%needle%'",
            "SELECT COUNT(DISTINCT d.public_device_record_key) FROM devices d JOIN product_codes pc ON d.public_device_record_key = pc.device_key WHERE pc.product_code IN ('FXX', 'MSH', 'CBK')",
        ]

        logger.info("Running verification queries:")
        for query in test_queries:
            result = self.conn.execute(query).fetchone()[0]
            logger.info(f"  {query[:50]}... => {result} results")


if __name__ == "__main__":
    indexer = GUDIDIndexer("gudid.db")
    try:
        indexer.index_directory("gudid_full_release_20250804")
        indexer.verify_index()
    finally:
        indexer.close()
