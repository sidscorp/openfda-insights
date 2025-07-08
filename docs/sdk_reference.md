# Python SDK Reference

Complete Python SDK documentation for Enhanced FDA Explorer.

## Installation

```bash
pip install enhanced-fda-explorer
```

## Quick Start

```python
import asyncio
from enhanced_fda_explorer import FDAExplorer

async def main():
    # Initialize explorer
    explorer = FDAExplorer()
    
    # Search for device data
    results = await explorer.search(
        query="pacemaker",
        query_type="device",
        limit=100,
        include_ai_analysis=True
    )
    
    print(f"Found {len(results['results'])} results")
    
    # Clean up
    await explorer.close()

# Run async function
asyncio.run(main())
```

## Core Classes

### FDAExplorer

Main class for interacting with FDA data and AI analysis.

```python
from enhanced_fda_explorer import FDAExplorer

# Initialize with default configuration
explorer = FDAExplorer()

# Initialize with custom configuration
explorer = FDAExplorer(
    fda_api_key="your_fda_key",
    ai_api_key="your_ai_key",
    ai_provider="openai",
    ai_model="gpt-4",
    cache_enabled=True,
    database_url="postgresql://..."
)
```

#### Configuration Parameters

- **fda_api_key** (str): FDA API key
- **ai_api_key** (str, optional): AI provider API key
- **ai_provider** (str): AI provider ("openai", "anthropic", "openrouter")
- **ai_model** (str): AI model name
- **cache_enabled** (bool): Enable caching (default: True)
- **database_url** (str, optional): Database connection string
- **timeout** (int): Request timeout in seconds (default: 30)
- **max_retries** (int): Maximum retry attempts (default: 3)

### Search Methods

#### search()

Search FDA databases with optional AI analysis.

```python
async def search(
    query: str,
    query_type: str = "device",
    limit: int = 100,
    skip: int = 0,
    include_ai_analysis: bool = False,
    ai_model: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    fields: Optional[List[str]] = None,
    filters: Optional[Dict] = None
) -> Dict
```

**Parameters:**
- **query**: Search term
- **query_type**: Database type ("device", "event", "recall", "510k", "pma", "classification", "udi")
- **limit**: Maximum results (1-1000)
- **skip**: Number of results to skip (pagination)
- **include_ai_analysis**: Include AI analysis in results
- **ai_model**: Specific AI model to use
- **date_from**: Start date (YYYY-MM-DD)
- **date_to**: End date (YYYY-MM-DD)
- **fields**: List of fields to return
- **filters**: Additional filters

**Returns:**
```python
{
    "results": [...],  # Search results
    "total": 1247,     # Total matches
    "took": 150,       # Response time (ms)
    "ai_analysis": {   # Optional AI analysis
        "summary": "...",
        "risk_score": 7.2,
        "trends": [...]
    }
}
```

**Example:**
```python
# Basic search
results = await explorer.search("pacemaker", limit=50)

# Advanced search with filters
results = await explorer.search(
    query="insulin pump",
    query_type="event",
    limit=200,
    date_from="2023-01-01",
    date_to="2023-12-31",
    filters={
        "manufacturer": "Medtronic",
        "patient_age": "65+"
    },
    include_ai_analysis=True
)
```

### Device Intelligence Methods

#### get_device_intelligence()

Get comprehensive device analysis and intelligence.

```python
async def get_device_intelligence(
    device_name: str,
    lookback_months: int = 12,
    include_risk_assessment: bool = False,
    include_trends: bool = False,
    include_events: bool = True,
    include_recalls: bool = True,
    include_clearances: bool = True,
    include_approvals: bool = True,
    manufacturer: Optional[str] = None
) -> Dict
```

**Parameters:**
- **device_name**: Name of the medical device
- **lookback_months**: Months to analyze (default: 12)
- **include_risk_assessment**: Include AI risk assessment
- **include_trends**: Include trend analysis
- **include_events**: Include adverse events
- **include_recalls**: Include recall information
- **include_clearances**: Include 510(k) clearances
- **include_approvals**: Include PMA approvals
- **manufacturer**: Focus on specific manufacturer

**Returns:**
```python
{
    "device_info": {
        "name": "insulin pump",
        "category": "Endocrinology",
        "regulation_number": "21CFR862.1570",
        "device_class": "II"
    },
    "risk_assessment": {...},  # If requested
    "statistics": {...},
    "trends": {...},          # If requested
    "events": [...],          # If requested
    "recalls": [...],         # If requested
    "clearances": [...],      # If requested
    "approvals": [...]        # If requested
}
```

**Example:**
```python
# Comprehensive device analysis
intelligence = await explorer.get_device_intelligence(
    device_name="pacemaker",
    lookback_months=24,
    include_risk_assessment=True,
    include_trends=True,
    manufacturer="Medtronic"
)

print(f"Risk Score: {intelligence['risk_assessment']['overall_risk_score']}")
print(f"Total Events: {intelligence['statistics']['total_events']}")
```

#### compare_devices()

Compare multiple medical devices side-by-side.

```python
async def compare_devices(
    device_names: List[str],
    lookback_months: int = 12,
    metrics: Optional[List[str]] = None,
    include_ai_insights: bool = False
) -> Dict
```

**Parameters:**
- **device_names**: List of device names to compare
- **lookback_months**: Months to analyze
- **metrics**: Specific metrics to compare
- **include_ai_insights**: Include AI comparison insights

**Example:**
```python
# Compare three devices
comparison = await explorer.compare_devices(
    device_names=["pacemaker", "defibrillator", "cardiac monitor"],
    lookback_months=12,
    metrics=["events", "recalls", "risk_score"],
    include_ai_insights=True
)

for device in comparison["comparison"]["devices"]:
    print(f"{device['name']}: Risk Score {device['risk_score']}")
```

### Trend Analysis Methods

#### analyze_trends()

Analyze trends across multiple time periods.

```python
async def analyze_trends(
    query: str,
    periods: List[str],
    query_type: str = "device",
    metrics: Optional[List[str]] = None,
    include_ai_analysis: bool = False,
    manufacturer: Optional[str] = None
) -> Dict
```

**Parameters:**
- **query**: Search term for trend analysis
- **periods**: Time periods to analyze ("6months", "1year", "2years", "5years")
- **query_type**: Database type
- **metrics**: Metrics to analyze
- **include_ai_analysis**: Include AI trend interpretation
- **manufacturer**: Focus on specific manufacturer

**Example:**
```python
# Analyze surgical robot trends
trends = await explorer.analyze_trends(
    query="surgical robot",
    periods=["6months", "1year", "2years"],
    metrics=["events", "recalls", "approvals"],
    include_ai_analysis=True
)

print(f"1-year trend: {trends['trend_analysis']['events_trend']}")
```

### Manufacturer Analysis Methods

#### get_manufacturer_intelligence()

Get comprehensive manufacturer analysis.

```python
async def get_manufacturer_intelligence(
    manufacturer_name: str,
    lookback_months: int = 12,
    include_devices: bool = True,
    include_risk_profile: bool = False,
    include_compliance: bool = False
) -> Dict
```

**Example:**
```python
# Analyze manufacturer
manufacturer_data = await explorer.get_manufacturer_intelligence(
    manufacturer_name="Medtronic",
    lookback_months=24,
    include_risk_profile=True,
    include_compliance=True
)

print(f"Total Devices: {manufacturer_data['performance_metrics']['total_devices']}")
print(f"Risk Score: {manufacturer_data['risk_profile']['overall_risk_score']}")
```

### Regulatory Analysis Methods

#### get_regulatory_insights()

Get regulatory pathway and approval insights.

```python
async def get_regulatory_insights(
    device: Optional[str] = None,
    manufacturer: Optional[str] = None,
    pathway: Optional[str] = None,
    timeframe: str = "1year",
    include_trends: bool = False,
    include_ai_insights: bool = False
) -> Dict
```

**Example:**
```python
# Regulatory landscape analysis
regulatory = await explorer.get_regulatory_insights(
    device="artificial heart",
    pathway="pma",
    timeframe="2years",
    include_trends=True,
    include_ai_insights=True
)

print(f"Approval Rate: {regulatory['pathway_analysis']['pma']['approval_rate']}%")
```

## Data Models

### SearchResult

```python
from enhanced_fda_explorer.models import SearchResult

class SearchResult:
    def __init__(self, data: Dict):
        self.device_name = data.get('device_name')
        self.manufacturer = data.get('manufacturer')
        self.date_received = data.get('date_received')
        self.event_type = data.get('event_type')
        # ... other fields
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        
    def to_json(self) -> str:
        """Convert to JSON string"""
```

### DeviceIntelligence

```python
from enhanced_fda_explorer.models import DeviceIntelligence

class DeviceIntelligence:
    def __init__(self, data: Dict):
        self.device_info = data.get('device_info', {})
        self.risk_assessment = data.get('risk_assessment', {})
        self.statistics = data.get('statistics', {})
        self.trends = data.get('trends', {})
    
    @property
    def risk_score(self) -> float:
        """Get overall risk score"""
        return self.risk_assessment.get('overall_risk_score', 0.0)
    
    @property
    def total_events(self) -> int:
        """Get total adverse events"""
        return self.statistics.get('total_events', 0)
```

## Configuration

### Environment Variables

```python
import os
from enhanced_fda_explorer import FDAExplorer

# Configure via environment variables
os.environ['FDA_API_KEY'] = 'your_fda_key'
os.environ['AI_API_KEY'] = 'your_ai_key'
os.environ['AI_PROVIDER'] = 'openai'

explorer = FDAExplorer()  # Uses environment variables
```

### Configuration File

```python
from enhanced_fda_explorer import FDAExplorer
from enhanced_fda_explorer.config import Config

# Load from configuration file
config = Config.from_file('config.yaml')
explorer = FDAExplorer(config=config)
```

### Custom Configuration

```python
from enhanced_fda_explorer import FDAExplorer
from enhanced_fda_explorer.config import Config

# Custom configuration
config = Config(
    fda_api_key="your_fda_key",
    ai_provider="anthropic",
    ai_model="claude-3-sonnet",
    cache_ttl=7200,  # 2 hours
    max_concurrent_requests=10
)

explorer = FDAExplorer(config=config)
```

## Error Handling

```python
from enhanced_fda_explorer import FDAExplorer
from enhanced_fda_explorer.exceptions import (
    FDAExplorerError,
    APIError,
    AuthenticationError,
    RateLimitError,
    TimeoutError
)

async def safe_search():
    explorer = FDAExplorer()
    
    try:
        results = await explorer.search("pacemaker")
        return results
    except AuthenticationError:
        print("Invalid API key")
    except RateLimitError as e:
        print(f"Rate limited. Retry after {e.retry_after} seconds")
    except TimeoutError:
        print("Request timed out")
    except APIError as e:
        print(f"API error: {e.message}")
    except FDAExplorerError as e:
        print(f"General error: {e}")
    finally:
        await explorer.close()
```

## Async Context Manager

```python
from enhanced_fda_explorer import FDAExplorer

# Recommended pattern for resource management
async with FDAExplorer() as explorer:
    results = await explorer.search("pacemaker")
    intelligence = await explorer.get_device_intelligence("insulin pump")
    # Automatically closed when exiting context
```

## Caching

### Enable/Disable Caching

```python
# Enable caching (default)
explorer = FDAExplorer(cache_enabled=True)

# Disable caching
explorer = FDAExplorer(cache_enabled=False)

# Custom cache configuration
explorer = FDAExplorer(
    cache_enabled=True,
    cache_ttl=3600,  # 1 hour
    cache_type="redis",
    cache_url="redis://localhost:6379"
)
```

### Manual Cache Control

```python
# Clear cache for specific query
await explorer.clear_cache("pacemaker")

# Clear all cache
await explorer.clear_all_cache()

# Get cache statistics
cache_stats = await explorer.get_cache_stats()
print(f"Cache hit ratio: {cache_stats['hit_ratio']}")
```

## Pagination

```python
# Manual pagination
page_size = 100
page = 0

all_results = []
while True:
    results = await explorer.search(
        "pacemaker",
        limit=page_size,
        skip=page * page_size
    )
    
    if not results['results']:
        break
        
    all_results.extend(results['results'])
    page += 1

print(f"Total results: {len(all_results)}")
```

### Pagination Helper

```python
# Using built-in pagination helper
async for batch in explorer.search_paginated("pacemaker", batch_size=100):
    print(f"Processing batch of {len(batch)} results")
    # Process batch...
```

## Streaming Results

```python
# Stream large result sets
async for result in explorer.search_stream("insulin pump"):
    print(f"Device: {result['device_name']}")
    # Process result immediately
```

## Batch Operations

```python
# Batch device intelligence queries
device_names = ["pacemaker", "defibrillator", "insulin pump"]

# Sequential
results = []
for device in device_names:
    intelligence = await explorer.get_device_intelligence(device)
    results.append(intelligence)

# Concurrent (faster)
import asyncio

tasks = [
    explorer.get_device_intelligence(device) 
    for device in device_names
]
results = await asyncio.gather(*tasks)
```

## Export Data

```python
import pandas as pd
import json

# Export to pandas DataFrame
results = await explorer.search("pacemaker", limit=1000)
df = pd.DataFrame(results['results'])
df.to_csv('pacemaker_data.csv', index=False)

# Export to JSON
with open('pacemaker_data.json', 'w') as f:
    json.dump(results, f, indent=2)

# Export device intelligence
intelligence = await explorer.get_device_intelligence("insulin pump")
with open('insulin_pump_intelligence.json', 'w') as f:
    json.dump(intelligence, f, indent=2)
```

## Testing

```python
import pytest
from enhanced_fda_explorer import FDAExplorer
from enhanced_fda_explorer.testing import MockFDAExplorer

# Use mock for testing
@pytest.fixture
async def mock_explorer():
    explorer = MockFDAExplorer()
    yield explorer
    await explorer.close()

async def test_search(mock_explorer):
    results = await mock_explorer.search("test_device")
    assert len(results['results']) > 0
    assert 'device_name' in results['results'][0]
```

## Performance Tips

1. **Use caching** for repeated queries
2. **Batch requests** when possible
3. **Use appropriate limits** to avoid unnecessary data transfer
4. **Stream large result sets** instead of loading all at once
5. **Use async context managers** for proper resource cleanup
6. **Enable connection pooling** for high-throughput applications

## Examples

### Complete Analysis Workflow

```python
import asyncio
from enhanced_fda_explorer import FDAExplorer

async def analyze_device_portfolio():
    async with FDAExplorer() as explorer:
        devices = ["pacemaker", "defibrillator", "insulin pump"]
        
        # Get intelligence for each device
        intelligence_data = {}
        for device in devices:
            intelligence = await explorer.get_device_intelligence(
                device_name=device,
                include_risk_assessment=True,
                include_trends=True
            )
            intelligence_data[device] = intelligence
        
        # Compare devices
        comparison = await explorer.compare_devices(
            device_names=devices,
            include_ai_insights=True
        )
        
        # Generate report
        print("Device Portfolio Analysis")
        print("=" * 40)
        
        for device, data in intelligence_data.items():
            risk_score = data['risk_assessment']['overall_risk_score']
            total_events = data['statistics']['total_events']
            print(f"{device.title()}: Risk Score {risk_score}, Events {total_events}")
        
        print("\nAI Insights:")
        print(comparison['ai_insights']['summary'])

# Run analysis
asyncio.run(analyze_device_portfolio())
```

For more examples and tutorials, see the [examples directory](https://github.com/siddnambiar/enhanced-fda-explorer/tree/main/examples) in the repository.