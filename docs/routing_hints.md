# Routing Hints for Agent

**Purpose**: Guide the agent to select the correct endpoint based on user intent.

## Intent → Endpoint Mapping

### Product Code / Classification
- **If** user mentions: 3-letter product code (e.g., "LZG"), device class, CFR regulation
- **Then** → use `classification` endpoint

### 510(k) Clearances
- **If** user mentions: "510(k)", "K-number" (K123456), "clearance", "premarket notification"
- **Then** → use `510k` endpoint

### PMA Approvals
- **If** user mentions: "PMA", "P-number" (P123456), "premarket approval", "supplement"
- **Then** → use `pma` endpoint

### Recalls / Enforcement
- **If** user mentions: "recall", "Class I/II/III recall", "enforcement", "withdrawn"
- **Then** → use `recall` (enforcement) endpoint

### Adverse Events
- **If** user mentions: "adverse event", "MAUDE", "malfunction", "injury", "death", "patient problem"
- **Then** → use `maude` (event) endpoint

### Device Identifiers
- **If** user mentions: "UDI", "DI number", "barcode", "GUDID", "device identifier"
- **Then** → use `udi` endpoint

### Establishments / Manufacturers
- **If** user mentions: "facility", "establishment", "FEI number", "manufacturer location", "registration"
- **Then** → use `rl_search` (registration/listing) endpoint

## Query Patterns

### Counting / Aggregation
- **If** user asks: "how many", "count", "total number"
- **Then** → use `probe_count` utility with `count=` parameter

### Time-based Queries
- **If** user mentions: "since 2023", "last year", "recent", "after 2020", "in 2024"
- **Then** → apply date filters to search query

### Multi-endpoint Patterns
- **If** user asks about recalls for a product code:
  1. First → `classification` to verify product code exists
  2. Then → `recall_search` with that product code

- **If** user asks about adverse events for a specific device:
  1. First → `udi_search` or `classification` to get product code
  2. Then → `maude_search` with product code
