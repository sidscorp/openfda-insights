# CLI Reference

Complete command-line interface reference for Enhanced FDA Explorer.

## Installation & Setup

```bash
pip install enhanced-fda-explorer
export FDA_API_KEY="your_api_key"
export AI_API_KEY="your_ai_key"  # Optional
```

## Global Options

All commands support these global options:

```bash
--config PATH     Path to configuration file
--verbose, -v     Verbose output
--quiet, -q       Suppress output
--format FORMAT   Output format (json, yaml, table)
--help, -h        Show help message
```

## Commands

### fda-explorer search

Search FDA databases with optional AI analysis.

```bash
fda-explorer search [OPTIONS] QUERY
```

**Arguments:**
- `QUERY`: Search term (e.g., "pacemaker", "insulin pump")

**Options:**
```bash
--type TYPE              Database type [device|event|recall|510k|pma|classification|udi]
--limit INTEGER          Number of results (default: 100, max: 1000)
--skip INTEGER           Number of results to skip (pagination)
--fields TEXT            Comma-separated list of fields to return
--include-ai             Include AI analysis in results
--ai-model TEXT          AI model to use (gpt-4, claude-3, etc.)
--output FILE            Save results to file
--date-from DATE         Start date (YYYY-MM-DD)
--date-to DATE           End date (YYYY-MM-DD)
--manufacturer TEXT      Filter by manufacturer
--state TEXT             Filter by state (for events/recalls)
--country TEXT           Filter by country
```

**Examples:**
```bash
# Basic search
fda-explorer search "pacemaker" --limit 50

# Search with AI analysis
fda-explorer search "insulin pump" --include-ai --ai-model gpt-4

# Search specific database
fda-explorer search "hip implant" --type recall --limit 20

# Date range search
fda-explorer search "defibrillator" --date-from 2023-01-01 --date-to 2023-12-31

# Export results
fda-explorer search "surgical mesh" --output results.json --format json
```

### fda-explorer device

Get comprehensive device intelligence and analysis.

```bash
fda-explorer device [OPTIONS] DEVICE_NAME
```

**Arguments:**
- `DEVICE_NAME`: Name of the medical device

**Options:**
```bash
--lookback INTEGER       Months to look back (default: 12)
--risk-assessment        Include AI risk assessment
--trends                 Include trend analysis
--comparisons TEXT       Comma-separated devices to compare with
--manufacturer TEXT      Focus on specific manufacturer
--output FILE            Save analysis to file
--include-events         Include adverse events
--include-recalls        Include recall information
--include-clearances     Include 510(k) clearances
--include-approvals      Include PMA approvals
```

**Examples:**
```bash
# Basic device intelligence
fda-explorer device "pacemaker" --lookback 24

# Comprehensive analysis
fda-explorer device "insulin pump" --risk-assessment --trends --include-events

# Device comparison
fda-explorer device "pacemaker" --comparisons "defibrillator,cardiac monitor"

# Manufacturer focus
fda-explorer device "hip implant" --manufacturer "Stryker" --include-recalls
```

### fda-explorer compare

Compare multiple medical devices side-by-side.

```bash
fda-explorer compare [OPTIONS] DEVICE1 DEVICE2 [DEVICE3...]
```

**Arguments:**
- `DEVICE1`, `DEVICE2`, etc.: Device names to compare

**Options:**
```bash
--lookback INTEGER       Months to look back (default: 12)
--metrics TEXT           Comma-separated metrics to compare
--ai-insights           Include AI-generated comparison insights
--output FILE           Save comparison to file
--chart                 Generate comparison chart
--format FORMAT         Output format (table, json, html)
```

**Examples:**
```bash
# Compare two devices
fda-explorer compare "pacemaker" "defibrillator"

# Multi-device comparison with AI insights
fda-explorer compare "insulin pump" "glucose monitor" "insulin pen" --ai-insights

# Generate HTML report
fda-explorer compare "hip implant" "knee implant" --format html --output comparison.html
```

### fda-explorer trends

Analyze trends across multiple time periods.

```bash
fda-explorer trends [OPTIONS] QUERY
```

**Arguments:**
- `QUERY`: Search term for trend analysis

**Options:**
```bash
--periods TEXT           Time periods (6months,1year,2years)
--type TYPE             Database type for trend analysis
--metrics TEXT          Metrics to analyze (events,recalls,approvals)
--ai-analysis          Include AI trend interpretation
--chart                Generate trend charts
--output FILE          Save analysis to file
--manufacturer TEXT    Focus on specific manufacturer
```

**Examples:**
```bash
# Basic trend analysis
fda-explorer trends "cardiac device" --periods "6months,1year,2years"

# Detailed trend analysis with AI
fda-explorer trends "surgical robot" --ai-analysis --chart --output trends.html

# Manufacturer trend analysis
fda-explorer trends "orthopedic implant" --manufacturer "Johnson & Johnson"
```

### fda-explorer manufacturer

Get manufacturer intelligence and analysis.

```bash
fda-explorer manufacturer [OPTIONS] MANUFACTURER_NAME
```

**Arguments:**
- `MANUFACTURER_NAME`: Name of the manufacturer

**Options:**
```bash
--lookback INTEGER      Months to look back (default: 12)
--devices              List devices by this manufacturer
--risk-profile         Generate risk profile
--compliance           Compliance analysis
--output FILE          Save analysis to file
--include-events       Include adverse events
--include-recalls      Include recalls
--include-clearances   Include 510(k) clearances
```

**Examples:**
```bash
# Basic manufacturer analysis
fda-explorer manufacturer "Medtronic"

# Comprehensive manufacturer profile
fda-explorer manufacturer "Boston Scientific" --risk-profile --compliance --devices

# Focus on specific areas
fda-explorer manufacturer "Abbott" --include-events --include-recalls --lookback 24
```

### fda-explorer regulatory

Get regulatory insights and timeline analysis.

```bash
fda-explorer regulatory [OPTIONS]
```

**Options:**
```bash
--device TEXT           Focus on specific device
--manufacturer TEXT     Focus on specific manufacturer
--type TYPE            Regulatory pathway (510k, pma, de_novo)
--timeframe TEXT       Analysis timeframe (1year, 2years, 5years)
--trends              Include trend analysis
--ai-insights         Include AI regulatory insights
--output FILE         Save analysis to file
```

**Examples:**
```bash
# General regulatory landscape
fda-explorer regulatory --timeframe 2years --trends

# Device-specific regulatory analysis
fda-explorer regulatory --device "artificial heart" --type pma --ai-insights

# Manufacturer regulatory profile
fda-explorer regulatory --manufacturer "Medtronic" --trends --output regulatory_analysis.json
```

### fda-explorer web

Launch the web interface.

```bash
fda-explorer web [OPTIONS]
```

**Options:**
```bash
--host TEXT            Host address (default: localhost)
--port INTEGER         Port number (default: 8501)
--config FILE          Configuration file
--theme TEXT           UI theme (light, dark, auto)
--debug               Enable debug mode
```

**Examples:**
```bash
# Launch web interface
fda-explorer web

# Custom host and port
fda-explorer web --host 0.0.0.0 --port 8080

# Debug mode
fda-explorer web --debug --theme dark
```

### fda-explorer serve

Launch the REST API server.

```bash
fda-explorer serve [OPTIONS]
```

**Options:**
```bash
--host TEXT            Host address (default: localhost)
--port INTEGER         Port number (default: 8000)
--workers INTEGER      Number of worker processes
--reload              Enable auto-reload for development
--config FILE         Configuration file
--cors               Enable CORS
--auth               Enable authentication
```

**Examples:**
```bash
# Launch API server
fda-explorer serve

# Production deployment
fda-explorer serve --host 0.0.0.0 --port 8000 --workers 4

# Development mode
fda-explorer serve --reload --cors --debug
```

## Configuration

### Environment Variables

```bash
FDA_API_KEY              FDA API key (required)
AI_API_KEY               AI provider API key (optional)
DATABASE_URL             Database connection string
REDIS_URL                Redis cache URL
LOG_LEVEL                Logging level (DEBUG, INFO, WARNING, ERROR)
```

### Configuration File

Create `~/.fda-explorer/config.yaml`:

```yaml
openfda:
  api_key: "your_fda_api_key"
  timeout: 30
  
ai:
  provider: "openai"
  api_key: "your_ai_api_key"
  model: "gpt-4"
  
output:
  default_format: "table"
  max_results: 1000
  
cache:
  enabled: true
  ttl: 3600
```

## Output Formats

### Table (Default)
Human-readable tabular output suitable for terminal viewing.

### JSON
Structured JSON output for programmatic use:
```bash
fda-explorer search "pacemaker" --format json
```

### YAML
YAML format for configuration and data exchange:
```bash
fda-explorer search "pacemaker" --format yaml
```

### CSV
Comma-separated values for spreadsheet import:
```bash
fda-explorer search "pacemaker" --format csv --output results.csv
```

## Error Handling

The CLI provides detailed error messages and exit codes:

- `0`: Success
- `1`: General error
- `2`: Invalid arguments
- `3`: API error
- `4`: Authentication error
- `5`: Network error

## Advanced Usage

### Piping and Redirection

```bash
# Pipe results to other commands
fda-explorer search "pacemaker" --format json | jq '.results[0]'

# Redirect output to file
fda-explorer device "insulin pump" > device_analysis.txt

# Combine with other tools
fda-explorer search "hip implant" --format csv | csvkit
```

### Batch Processing

```bash
# Process multiple devices
for device in "pacemaker" "defibrillator" "insulin pump"; do
  fda-explorer device "$device" --output "${device//[^a-zA-Z0-9]/_}_analysis.json"
done

# Bulk comparison
fda-explorer compare $(cat device_list.txt)
```

### Integration with Scripts

```bash
#!/bin/bash
# Daily device monitoring script

DEVICES=("pacemaker" "defibrillator" "insulin pump")
DATE=$(date +%Y%m%d)

for device in "${DEVICES[@]}"; do
  echo "Analyzing $device..."
  fda-explorer device "$device" \
    --risk-assessment \
    --include-events \
    --output "reports/${DATE}_${device}_report.json"
done

echo "Analysis complete. Reports saved to reports/"
```

## Tips and Best Practices

1. **Use specific search terms** for better results
2. **Set appropriate limits** to avoid rate limiting
3. **Cache results** for repeated analysis
4. **Use AI features** for deeper insights
5. **Export data** for further analysis in other tools
6. **Monitor API usage** to stay within limits

## Getting Help

```bash
# General help
fda-explorer --help

# Command-specific help
fda-explorer search --help
fda-explorer device --help

# Version information
fda-explorer --version
```

For more help:
- [Documentation](https://enhanced-fda-explorer.readthedocs.io)
- [GitHub Issues](https://github.com/siddnambiar/enhanced-fda-explorer/issues)
- [Community Discussions](https://github.com/siddnambiar/enhanced-fda-explorer/discussions)