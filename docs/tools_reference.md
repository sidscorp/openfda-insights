# Agent Tools Reference

Complete parameter documentation for all 10 FDA Agent tools.

## Tool Categories

The FDA Agent uses two categories of tools:

| Category | Purpose | Shared State |
|----------|---------|--------------|
| **Resolvers** | Translate user concepts into FDA identifiers | ✅ Populate `ResolverContext` |
| **Searchers** | Query FDA databases with those identifiers | ❌ Read-only (except recalls) |

## Resolvers

### resolve_device

Search the GUDID database (180+ million registered devices) for device identification.

**When to use**: First step for any device-related query. Maps device names to FDA product codes.

```python
resolve_device(
    query: str,     # Device name, brand, company, or product code
    limit: int = 500  # Maximum results (default: 500)
)
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | ✅ | - | Device name, brand name, company name, or 3-letter product code |
| `limit` | int | ❌ | 500 | Maximum number of device matches to return |

**Returns**: Product codes, GMDN terms, manufacturers, device identifiers, match confidence scores.

**Populates**: `ResolverContext.devices` → `ResolvedEntities`

**Examples**:
```python
resolve_device("surgical mask")           # Find masks by name
resolve_device("FXX")                     # Find devices by product code
resolve_device("Medtronic")               # Find devices by manufacturer
resolve_device("insulin pump", limit=100) # Limit results
```

---

### resolve_manufacturer

Resolve company names to exact FDA firm name variations.

**When to use**: Before searching recalls/events by manufacturer. FDA databases use inconsistent firm names.

```python
resolve_manufacturer(
    query: str,      # Company or manufacturer name
    limit: int = 100  # Maximum results
)
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | ✅ | - | Company or manufacturer name (e.g., "3M", "Medtronic") |
| `limit` | int | ❌ | 100 | Maximum name variations to return |

**Returns**: All FDA name variations for a company (e.g., "3M Company", "3M COMPANY", "3M Health Care").

**Populates**: `ResolverContext.manufacturers` → `list[ManufacturerInfo]`

**Examples**:
```python
resolve_manufacturer("3M")        # Find all 3M name variations
resolve_manufacturer("Johnson")   # Find Johnson & Johnson variations
```

---

### resolve_location

Find medical device manufacturers by geographic location.

**When to use**: For geographic queries about device manufacturing origins.

```python
resolve_location(
    location: str,           # Country, region, or US state
    device_type: str = None, # Optional device filter
    limit: int = 100         # Results per location
)
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `location` | str | ✅ | - | Country name, region, or US state |
| `device_type` | str | ❌ | None | Optional device type filter (e.g., "mask", "ventilator") |
| `limit` | int | ❌ | 100 | Maximum results per country/state |

**Supported Locations**:
- **Countries**: China, Germany, Japan, France, etc. (ISO codes or full names)
- **Regions**: Asia, Europe, EU, North America, Latin America, APAC
- **US States**: California, Texas, NY, etc. (names or 2-letter codes)

**Returns**: Establishment counts, top companies, device types manufactured.

**Populates**: `ResolverContext.location` → `LocationContext`

**Examples**:
```python
resolve_location("China")                    # All Chinese manufacturers
resolve_location("Europe")                   # All EU + non-EU European manufacturers
resolve_location("California")               # California-based manufacturers
resolve_location("China", device_type="mask") # Mask manufacturers in China
```

---

## Searchers

### search_events

Search FDA adverse event reports (MAUDE database).

**When to use**: For safety issues, device problems, patient injuries.

```python
search_events(
    query: str = "",        # Device/company name
    date_from: str = "",    # Start date (YYYYMMDD)
    date_to: str = "",      # End date (YYYYMMDD)
    limit: int = 100,       # Maximum results
    country: str = "",      # Manufacturer country filter
    product_code: str = ""  # FDA product code filter
)
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | ❌ | "" | Device name or manufacturer name |
| `date_from` | str | ❌ | "" | Start date in YYYYMMDD format |
| `date_to` | str | ❌ | "" | End date in YYYYMMDD format |
| `limit` | int | ❌ | 100 | Maximum results (max 100 per API call) |
| `country` | str | ❌ | "" | Filter by manufacturer country (e.g., "China", "Germany") |
| `product_code` | str | ❌ | "" | FDA 3-letter product code (e.g., "FXX") |

**Note**: At least one of `query`, `country`, or `product_code` is required.

**Country Codes**: Accepts both names ("China") and ISO codes ("CN"). Auto-normalized.

**Returns**: Event types (Death, Injury, Malfunction), patient outcomes, device problems.

**Examples**:
```python
search_events(query="pacemaker")                      # Events for pacemakers
search_events(product_code="FXX")                     # Events by product code
search_events(country="China")                        # Events from Chinese manufacturers
search_events(product_code="FXX", country="China")    # Mask events from China
search_events(query="Medtronic", date_from="20230101") # Recent Medtronic events
```

---

### search_recalls

Search FDA device recall enforcement actions.

**When to use**: For product recalls, safety alerts, enforcement history.

```python
search_recalls(
    query: str,              # Device/manufacturer name
    date_from: str = "",     # Start date (YYYYMMDD)
    date_to: str = "",       # End date (YYYYMMDD)
    limit: int = 100,        # Maximum results
    search_field: str = "both", # Search target
    country: str = ""        # Recalling firm country
)
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | ❌ | "" | Device name or manufacturer name |
| `date_from` | str | ❌ | "" | Start date in YYYYMMDD format |
| `date_to` | str | ❌ | "" | End date in YYYYMMDD format |
| `limit` | int | ❌ | 100 | Maximum results (max 100 per API call) |
| `search_field` | str | ❌ | "both" | Where to search: "product", "firm", or "both" |
| `country` | str | ❌ | "" | Filter by recalling firm's country |

**Note**: At least one of `query` or `country` is required.

**Search Fields**:
- `"product"`: Search `product_description` field only
- `"firm"`: Search `recalling_firm` field only
- `"both"`: Search both fields (default)

**Country Format**: Uses full country names ("China", "Germany", "United States").

**Returns**: Recall classifications (Class I/II/III), status, reasons, affected products.

**Populates**: `RecallSearchResult` (for structured access)

**Examples**:
```python
search_recalls(query="mask")                          # All mask recalls
search_recalls(query="Medtronic", search_field="firm") # Recalls by Medtronic
search_recalls(country="China")                       # All recalls from China
search_recalls(query="mask", country="China")         # Mask recalls from China
search_recalls(query="pacemaker", date_from="20200101") # Recent pacemaker recalls
```

---

### search_510k

Search FDA 510(k) premarket notifications (clearances).

**When to use**: For device clearances, substantial equivalence, regulatory pathway.

```python
search_510k(
    query: str,          # Device name, company, or K number
    date_from: str = "", # Start date (YYYYMMDD)
    date_to: str = "",   # End date (YYYYMMDD)
    limit: int = 100     # Maximum results
)
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | ✅ | - | Device name, applicant name, or K number (e.g., "K201234") |
| `date_from` | str | ❌ | "" | Start date in YYYYMMDD format |
| `date_to` | str | ❌ | "" | End date in YYYYMMDD format |
| `limit` | int | ❌ | 100 | Maximum results |

**Auto-detection**: If query starts with "K" and is 6+ characters, searches by K number.

**Returns**: K numbers, clearance dates, applicants, predicate devices.

**Examples**:
```python
search_510k("surgical mask")         # 510(k)s for surgical masks
search_510k("K201234")              # Specific 510(k) by number
search_510k("Medtronic")            # 510(k)s filed by Medtronic
search_510k("pacemaker", date_from="20230101") # Recent pacemaker clearances
```

---

### search_pma

Search FDA Premarket Approval (PMA) database.

**When to use**: For Class III high-risk device approvals requiring clinical data.

```python
search_pma(
    query: str,          # Device name, company, or PMA number
    date_from: str = "", # Start date (YYYYMMDD)
    date_to: str = "",   # End date (YYYYMMDD)
    limit: int = 100     # Maximum results
)
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | ✅ | - | Trade name, generic name, applicant, or PMA number (e.g., "P200001") |
| `date_from` | str | ❌ | "" | Start date in YYYYMMDD format |
| `date_to` | str | ❌ | "" | End date in YYYYMMDD format |
| `limit` | int | ❌ | 100 | Maximum results |

**Auto-detection**: If query starts with "P" and is 6+ characters, searches by PMA number.

**Returns**: PMA numbers, approval dates, applicants, supplements, decision codes.

**Examples**:
```python
search_pma("pacemaker")              # PMA approvals for pacemakers
search_pma("P200001")                # Specific PMA by number
search_pma("Medtronic")              # PMAs filed by Medtronic
search_pma("defibrillator", date_from="20200101") # Recent defibrillator approvals
```

---

### search_classifications

Search FDA device classification database.

**When to use**: For regulatory requirements, device class, submission type.

```python
search_classifications(
    query: str,       # Device name, product code, or regulation number
    limit: int = 50   # Maximum results
)
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | ✅ | - | Device name, 3-letter product code, or regulation number |
| `limit` | int | ❌ | 50 | Maximum results |

**Auto-detection**:
- 3 uppercase letters → product code search
- Decimal format (e.g., "880.5100") → regulation number search
- Otherwise → device name search

**Returns**: Device class (I/II/III), submission type, regulation numbers, specialty.

**Examples**:
```python
search_classifications("surgical mask")  # Classifications for surgical masks
search_classifications("FXX")           # Classification for product code FXX
search_classifications("880.5100")      # Classification by regulation number
```

---

### search_udi

Search FDA Unique Device Identification (UDI) database.

**When to use**: For specific device models, identifiers, physical characteristics.

```python
search_udi(
    query: str,      # Brand name, company, or model number
    limit: int = 50  # Maximum results
)
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | ✅ | - | Brand name, company name, or model number |
| `limit` | int | ❌ | 50 | Maximum results |

**Returns**: Device identifiers (DI), MRI safety, sterile/single-use status, descriptions.

**Examples**:
```python
search_udi("insulin pump")    # UDI records for insulin pumps
search_udi("Medtronic")       # UDI records from Medtronic
search_udi("Model ABC123")    # Search by model number
```

---

### search_registrations

Search FDA establishment registrations for manufacturer locations.

**When to use**: For geographic data about where manufacturers are located.

```python
search_registrations(
    query: str,       # Company name or product
    limit: int = 100  # Maximum results
)
```

**Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | ✅ | - | Company name, product name, or product code |
| `limit` | int | ❌ | 100 | Maximum results |

**Returns**: Company addresses (city, state, country), products manufactured.

**Examples**:
```python
search_registrations("Medtronic")   # Find Medtronic facility locations
search_registrations("mask")        # Find mask manufacturer locations
```

---

## Common Query Patterns

### Device Safety Investigation
```python
# Step 1: Identify the device
resolve_device("surgical mask")
# Returns product codes: FXX, MSH, OUK

# Step 2: Search adverse events
search_events(product_code="FXX")

# Step 3: Search recalls
search_recalls(query="surgical mask")
```

### Geographic Analysis
```python
# Find manufacturers in a country
resolve_location("China", device_type="mask")

# Search recalls from that country
search_recalls(country="China")

# Search adverse events from that country
search_events(country="China")
```

### Regulatory Pathway Research
```python
# Determine device class
search_classifications("FXX")

# Find 510(k) clearances
search_510k(query="surgical mask")

# Or PMA approvals for Class III
search_pma(query="pacemaker")
```

### Manufacturer Analysis
```python
# Find exact firm names
resolve_manufacturer("3M")

# Search recalls by firm
search_recalls(query="3M Company", search_field="firm")

# Find facility locations
search_registrations("3M")
```

---

## Async Execution

All tools implement both synchronous (`_run`) and asynchronous (`_arun`) methods:

```python
# Sync (blocking)
result = tool._run(query="mask")

# Async (non-blocking)
result = await tool._arun(query="mask")
```

When the agent calls multiple tools, `ContextAwareToolNode.ainvoke()` executes them concurrently via `asyncio.gather()`, reducing latency by 2-3x for multi-tool queries.

---

## Error Handling

All tools return human-readable error messages:

| Scenario | Response |
|----------|----------|
| No results | `"No [type] found for '[query]'."` |
| Missing params | `"Error: Must provide [required param]."` |
| API error | `"FDA API error: [details]"` |
| Rate limit (429) | Automatic retry with backoff |
| Server error (500) | `"Error searching [type]: [details]"` |
