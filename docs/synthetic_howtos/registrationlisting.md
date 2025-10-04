# Registration & Listing Endpoint

## What is this endpoint for?

The `registrationlisting` endpoint contains information about medical device establishments (manufacturers, repackagers, relabelers, etc.) registered with FDA. Use this endpoint to find facilities by name, location (city, state, country), FEI number, or to see what products they manufacture.

## Example Queries

### 1. Find establishments by location
**Natural language**: "Show me device manufacturers in California"
**openFDA filter**: `registration.address.state_code:CA`
**Returns**: All registered establishments with California addresses

### 2. Search by firm name
**Natural language**: "Find establishments owned by Medtronic"
**openFDA filter**: `proprietary_name:Medtronic`
**Returns**: Establishments with "Medtronic" in their proprietary name

### 3. Search by FEI number
**Natural language**: "What is establishment FEI 1234567?"
**openFDA filter**: `registration.fei_number:1234567`
**Returns**: Registration record for that specific FEI number

## Canonical Field Names

- `proprietary_name` - Proprietary/trade name of the establishment
- `establishment_type` - Type of establishment (e.g., Manufacturer, Importer, etc.)
- `registration.fei_number` - FDA Establishment Identifier (FEI) number
- `registration.address.city` - City where establishment is located
- `registration.address.state_code` - Two-letter state code (e.g., CA, NY)
- `registration.address.iso_country_code` - Two-letter country code (e.g., US, CA)
- `registration.registration_date` - Date of registration (YYYYMMDD format)
- `products.product_code` - Product codes manufactured at this establishment
- `products.created_date` - Date product was added to registration
- `registration.name` - Official registered name
- `registration.owner_operator` - Owner/operator information
- `k_number` - Associated 510(k) numbers (if applicable)
