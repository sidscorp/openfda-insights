# UDI/GUDID Endpoint

## What is this endpoint for?

The `udi` endpoint contains Unique Device Identifier (UDI) records from the Global Unique Device Identification Database (GUDID). Use this endpoint to lookup devices by their UDI, search by brand name, find device identifiers (DI), or search by company name.

## Example Queries

### 1. Lookup by UDI
**Natural language**: "Find device with UDI 00819320201234"
**openFDA filter**: `identifiers.id:00819320201234`
**Returns**: Device record with that specific UDI

### 2. Search by brand name
**Natural language**: "Find devices with brand name 'Acme Surgical Stapler'"
**openFDA filter**: `brand_name:"Acme Surgical Stapler"`
**Returns**: All devices with that brand name

### 3. Search by company
**Natural language**: "What devices does Johnson & Johnson manufacture?"
**openFDA filter**: `company_name:"Johnson & Johnson"`
**Returns**: All devices manufactured by Johnson & Johnson in GUDID

## Canonical Field Names

- `identifiers.id` - UDI identifier (DI or full UDI)
- `brand_name` - Brand/trade name of device
- `version_or_model_number` - Model or version number
- `company_name` - Device manufacturer/labeler company name
- `product_codes.code` - Product code(s) associated with device
- `gmdn_terms.name` - Global Medical Device Nomenclature terms
- `identifiers.type` - Type of identifier (primary, secondary, etc.)
- `device_description` - Detailed description of the device
- `catalog_number` - Catalog number
- `device_count_in_base_package` - Number of devices per package
- `openfda.device_class` - Device regulatory class
- `openfda.device_name` - Generic device name
