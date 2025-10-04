# MAUDE Adverse Events Endpoint

## What is this endpoint for?

The `event` endpoint (MAUDE database) contains medical device adverse event reports submitted to FDA. Use this endpoint to find device malfunctions, injuries, deaths, and other adverse events. Search by device name, brand, event type, or date received.

## Example Queries

### 1. Find adverse events by device
**Natural language**: "Show me adverse events for pacemakers"
**openFDA filter**: `device.generic_name:pacemaker`
**Returns**: All adverse event reports mentioning pacemakers

### 2. Search by event type
**Natural language**: "Find device malfunctions"
**openFDA filter**: `event_type:Malfunction`
**Returns**: All events classified as device malfunctions

### 3. Find recent events
**Natural language**: "What adverse events were reported since 2024?"
**openFDA filter**: `date_received:[20240101 TO 20251231]`
**Returns**: All events received by FDA from 2024 onwards

## Canonical Field Names

- `report_number` - Unique adverse event report number
- `event_type` - Type of event: Malfunction, Injury, Death, Other, or No Answer Provided
- `date_received` - Date FDA received the report (YYYYMMDD format)
- `device.generic_name` - Generic/common name of device
- `device.brand_name` - Brand/trade name of device
- `device.openfda.device_class` - Device regulatory class
- `device.manufacturer_d_name` - Device manufacturer name
- `patient.sequence_number_outcome` - Patient outcome codes
- `mdr_text.text` - Narrative description of the event
- `product_problem_flag` - Whether there was a product problem (Y/N)
- `date_of_event` - Date the adverse event occurred
- `device_date_of_manufacturer` - Manufacturing date of device
