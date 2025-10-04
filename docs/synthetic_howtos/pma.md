# PMA Approvals Endpoint

## What is this endpoint for?

The `pma` endpoint contains premarket approval (PMA) applications for Class III medical devices. Use this endpoint to find P-numbers, search for PMA approvals by sponsor/applicant, search by decision date, or find high-risk devices that required premarket approval.

## Example Queries

### 1. Find approvals by applicant
**Natural language**: "Show me PMA approvals from Boston Scientific"
**openFDA filter**: `applicant:"Boston Scientific"`
**Returns**: All PMA approvals where Boston Scientific was the applicant

### 2. Search by P-number
**Natural language**: "What is PMA P123456?"
**openFDA filter**: `pma_number:P123456`
**Returns**: Specific PMA approval with P-number P123456

### 3. Find recent approvals
**Natural language**: "What PMA approvals happened in 2024?"
**openFDA filter**: `decision_date:[20240101 TO 20241231]`
**Returns**: All PMAs approved in 2024

## Canonical Field Names

- `pma_number` - PMA number (format: P123456)
- `supplement_number` - Supplement number if applicable (e.g., S001)
- `applicant` - Company name that submitted the PMA
- `trade_name` - Trade/brand name of the device
- `product_code` - Three-letter product code
- `decision_date` - Date of FDA decision (YYYYMMDD format)
- `advisory_committee` - FDA advisory committee that reviewed the PMA
- `openfda.device_class` - Device class (typically 3 for PMAs)
- `openfda.device_name` - Generic device name
- `openfda.medical_specialty_description` - Medical specialty
- `generic_name` - Generic/common name
- `ao_statement` - Approvable letter or approval order statement
