# Device Classification Endpoint

## What is this endpoint for?

The `classification` endpoint provides information about device classifications, including device class (I, II, III), regulation numbers, product codes, and definitions. Use this endpoint when you need to understand device categories, find devices by their regulatory class, or lookup product code definitions.

## Example Queries

### 1. Find Class II devices
**Natural language**: "Show me Class II devices"
**openFDA filter**: `device_class:2`
**Returns**: All devices classified as Class II medical devices

### 2. Search by product code
**Natural language**: "What is product code LZG?"
**openFDA filter**: `product_code:LZG`
**Returns**: Classification information for product code LZG (including device name and regulation)

### 3. Search by device name
**Natural language**: "Find surgical gloves in the classification database"
**openFDA filter**: `device_name:"surgical gloves"`
**Returns**: Classification records matching "surgical gloves"

## Canonical Field Names

- `product_code` - Three-letter product code (e.g., LZG, DQA)
- `device_class` - Device class: 1, 2, or 3 (numeric)
- `device_name` - Common device name
- `regulation_number` - CFR regulation number (e.g., 21 CFR 878.4040)
- `medical_specialty_description` - Medical specialty area
- `definition` - Regulatory definition of the device
- `openfda.device_class` - Nested device class field
- `openfda.regulation_number` - Nested regulation number
- `openfda.device_name` - Nested device name
