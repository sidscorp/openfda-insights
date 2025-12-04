# FDA API Reference

This document covers the FDA data sources used by the system.

## OpenFDA API

Base URL: `https://api.fda.gov`

OpenFDA provides public access to FDA data via a REST API. No authentication required, but rate limits apply.

### Rate Limits

| With API Key | Without API Key |
|--------------|-----------------|
| 240 requests/minute | 40 requests/minute |
| 120,000 requests/day | 1,000 requests/day |

Get a free API key: https://open.fda.gov/apis/authentication/

### Device Endpoints

#### 1. Device Events (MAUDE)

Manufacturer and User Facility Device Experience database - adverse event reports.

```
GET https://api.fda.gov/device/event.json
```

**Key Fields**:
- `device.brand_name` - Product brand name
- `device.manufacturer_d_name` - Manufacturer name
- `device.manufacturer_d_country` - Manufacturer country code (e.g., "CN", "DE", "US")
- `device.device_report_product_code` - FDA product code (3-letter, e.g., "FXX")
- `event_type` - Malfunction, Injury, Death
- `date_received` - Report date
- `mdr_text` - Narrative description

**Geographic Filtering**:
The `device.manufacturer_d_country` field enables direct filtering by manufacturer location:
```bash
# Events from Chinese manufacturers
curl "https://api.fda.gov/device/event.json?search=device.manufacturer_d_country:CN&limit=10"

# Mask events from China (combine product code + country)
curl "https://api.fda.gov/device/event.json?search=device.device_report_product_code:FXX+AND+device.manufacturer_d_country:CN&limit=10"
```

**Example**:
```bash
curl "https://api.fda.gov/device/event.json?search=device.brand_name:pacemaker&limit=10"
```

#### 2. Device Recalls

Recall enforcement reports for medical devices.

```
GET https://api.fda.gov/device/enforcement.json
```

**Key Fields**:
- `product_description` - Device description
- `recalling_firm` - Company name
- `country` - Recalling firm's country (e.g., "China", "United States", "Germany")
- `reason_for_recall` - Why recalled
- `classification` - Class I (serious), II, III
- `status` - Ongoing, Completed, Terminated
- `recall_initiation_date` - When recall started

**Geographic Filtering**:
The `country` field enables direct filtering by recalling firm's location:
```bash
# All recalls from Chinese firms
curl "https://api.fda.gov/device/enforcement.json?search=country:China&limit=10"

# Mask recalls from China
curl "https://api.fda.gov/device/enforcement.json?search=product_description:mask+AND+country:China&limit=10"
```

**Note**: Unlike MAUDE, this uses full country names (not ISO codes).

**Example**:
```bash
curl "https://api.fda.gov/device/enforcement.json?search=recalling_firm:medtronic&limit=10"
```

#### 3. 510(k) Clearances

Premarket notification clearances - "substantially equivalent" determinations.

```
GET https://api.fda.gov/device/510k.json
```

**Key Fields**:
- `device_name` - Device name
- `applicant` - Company name
- `product_code` - FDA product code
- `decision_date` - Clearance date
- `decision_description` - SESE (substantially equivalent)
- `k_number` - 510(k) number (e.g., K201234)

**Example**:
```bash
curl "https://api.fda.gov/device/510k.json?search=product_code:DXY&limit=10"
```

#### 4. PMA Approvals

Premarket Approval decisions - Class III devices requiring clinical data.

```
GET https://api.fda.gov/device/pma.json
```

**Key Fields**:
- `trade_name` - Device name
- `applicant` - Company name
- `product_code` - FDA product code
- `decision_date` - Approval date
- `pma_number` - PMA number (e.g., P200001)
- `supplement_number` - For supplements to original PMA

**Example**:
```bash
curl "https://api.fda.gov/device/pma.json?search=product_code:DXY&limit=10"
```

#### 5. Device Classifications

FDA device classification database - regulatory class and product codes.

```
GET https://api.fda.gov/device/classification.json
```

**Key Fields**:
- `device_name` - Official device name
- `device_class` - 1, 2, or 3
- `product_code` - Three-letter code (e.g., DXY)
- `regulation_number` - CFR citation
- `medical_specialty` - Specialty panel (CV, SU, etc.)
- `review_panel` - Review panel name

**Example**:
```bash
curl "https://api.fda.gov/device/classification.json?search=product_code:DXY"
```

#### 6. UDI (Unique Device Identification)

Device identification from the Global UDI Database.

```
GET https://api.fda.gov/device/udi.json
```

**Key Fields**:
- `brand_name` - Product brand name
- `company_name` - Manufacturer
- `device_description` - Description
- `identifiers.id` - Device identifier (DI)
- `product_codes.code` - FDA product codes
- `gmdn_terms` - GMDN terminology

**Example**:
```bash
curl "https://api.fda.gov/device/udi.json?search=brand_name:insulin+pump&limit=10"
```

### Query Syntax

OpenFDA uses Elasticsearch query syntax.

**Search operators**:
```
search=field:value              # Exact match
search=field:value1+value2      # AND
search=field:value1+OR+value2   # OR
search=field:"exact phrase"     # Phrase match
search=field:val*               # Wildcard
```

**Date ranges**:
```
search=date_received:[2023-01-01+TO+2023-12-31]
```

**Counting**:
```
count=device.device_report_product_code.exact  # Count by field
```

**Pagination**:
```
limit=100    # Results per page (max 1000)
skip=100     # Offset for pagination
```

### Product Codes

Three-letter codes that classify devices. Examples:

| Code | Device Type |
|------|-------------|
| DXY | Pacemaker |
| DTB | Implantable Defibrillator |
| FRN | Surgical Mask |
| MSH | Filtering Facepiece Respirator |
| LZG | Insulin Pump |
| OZP | COVID-19 Test |

Search all product codes: https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPCD/classification.cfm

### Cross-Database Identifier Availability

FDA databases do NOT share a unified device identifier. Understanding which fields are available in each database is critical for designing queries:

| Field | Events (MAUDE) | Recalls | 510(k) | PMA | Classifications | Registrations |
|-------|---------------|---------|--------|-----|-----------------|---------------|
| Product Code | ✅ `device.device_report_product_code` | ❌ | ✅ | ✅ | ✅ | ✅ |
| Device ID (DI) | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Country | ✅ `device.manufacturer_d_country` (ISO) | ✅ `country` (full name) | ❌ | ❌ | ❌ | ✅ |
| Manufacturer | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |

**Key limitations**:
- **Recalls have no product code field** - the `openfda{}` block is empty, so you cannot link recalls to specific product codes
- **No unified device ID** - you cannot trace a specific device across databases by its UDI
- **Country field inconsistency** - MAUDE uses ISO codes ("CN"), recalls use full names ("China")

**Workarounds**:
- Use product codes to link MAUDE events → classifications → 510(k)/PMA
- Use manufacturer name text matching to link recalls → other databases
- Use the `resolve_device` tool to find product codes, then search by code where supported

## GUDID (Global UDI Database)

The GUDID is FDA's database of device identifiers. We use a local SQLite copy for fast queries.

### Data Source

Download from: https://accessgudid.nlm.nih.gov/download

Files:
- `gudid_data.zip` - Full database (~2GB uncompressed)
- Updated monthly

### Local Database Schema

```sql
-- Main device table
CREATE TABLE devices (
    primary_di TEXT PRIMARY KEY,
    brand_name TEXT,
    company_name TEXT,
    device_description TEXT,
    ...
);

-- Product codes (many-to-one)
CREATE TABLE product_codes (
    device_id TEXT,
    code TEXT,
    name TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(primary_di)
);

-- GMDN terms (many-to-one)
CREATE TABLE gmdn_terms (
    device_id TEXT,
    gmdn_pt_code TEXT,
    gmdn_pt_name TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(primary_di)
);

-- Full-text search index
CREATE VIRTUAL TABLE devices_fts USING fts5(
    brand_name, company_name, device_description
);
```

### Device Resolution Algorithm

1. **Exact match**: `brand_name = query`
2. **Fuzzy match**: Levenshtein distance on `brand_name`
3. **Full-text search**: FTS5 on description fields
4. **Company search**: Match `company_name`

Each match gets a confidence score (0.0-1.0) based on match type and string similarity.

## Data Freshness

| Source | Update Frequency |
|--------|------------------|
| Device Events | Daily |
| Recalls | Weekly |
| 510(k) | Weekly |
| PMA | Weekly |
| Classifications | Monthly |
| UDI | Daily |
| GUDID (local) | Monthly (manual) |

## Common Query Patterns

### Find all events for a device type

```python
# 1. Resolve device name to product codes
codes = resolve_device("pacemaker")  # Returns ["DXY", "DTB", ...]

# 2. Search events with product codes
events = search_events(product_codes=codes, limit=100)
```

### Find recalls by manufacturer

```python
recalls = search_recalls(
    manufacturer="Medtronic",
    date_from="2023-01-01",
    limit=50
)
```

### Get regulatory history for a product code

```python
# 510(k) clearances
clearances = search_510k(product_code="DXY")

# PMA approvals
approvals = search_pma(product_code="DXY")

# Classification info
classification = search_classifications(product_code="DXY")
```

## Error Handling

| HTTP Code | Meaning | Action |
|-----------|---------|--------|
| 200 | Success | Parse response |
| 404 | No results | Return empty list |
| 429 | Rate limited | Back off and retry |
| 500 | Server error | Retry with backoff |

## References

- OpenFDA Documentation: https://open.fda.gov/apis/
- OpenFDA GitHub: https://github.com/FDA/openfda
- GUDID: https://accessgudid.nlm.nih.gov/
- Product Code Database: https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPCD/classification.cfm
