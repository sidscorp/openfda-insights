# Enforcement/Recalls Endpoint

## What is this endpoint for?

The `enforcement` endpoint (also called recalls) contains enforcement actions including voluntary and mandatory recalls of medical devices. Use this endpoint to find recalls by classification (Class I, II, III), search by recalling firm, find recall reasons, or track device safety issues.

## Example Queries

### 1. Find Class I recalls
**Natural language**: "Show me Class I recalls"
**openFDA filter**: `classification:"Class I"`
**Returns**: All Class I recalls (most serious - risk of serious injury or death)

### 2. Search recalls by firm
**Natural language**: "Any recalls from Medtronic?"
**openFDA filter**: `recalling_firm:Medtronic`
**Returns**: All recalls where Medtronic was the recalling firm

### 3. Find recent recalls
**Natural language**: "What recalls happened since 2023?"
**openFDA filter**: `event_date_initiated:[20230101 TO 20251231]`
**Returns**: All recalls initiated from 2023 onwards

## Canonical Field Names

- `recall_number` - Unique recall identifier
- `classification` - Recall classification: "Class I", "Class II", or "Class III" (string with "Class " prefix)
- `product_description` - Description of the recalled product
- `recalling_firm` - Company name that initiated the recall
- `product_code` - Three-letter product code
- `event_date_initiated` - Date recall was initiated (YYYYMMDD format)
- `reason_for_recall` - Explanation of why device was recalled
- `openfda.device_class` - Device regulatory class
- `openfda.device_name` - Generic device name
- `status` - Recall status (e.g., Ongoing, Completed, Terminated)
- `distribution_pattern` - Geographic distribution of recalled devices
- `product_quantity` - Quantity of products recalled
