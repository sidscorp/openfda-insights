# Data Directory

This directory contains large data files that are not committed to git.

## Required Files

### GUDID Database (`gudid.db`)

SQLite database containing FDA device data from the Global Unique Device Identification Database.

**To obtain:**
1. Download from FDA GUDID: https://accessgudid.nlm.nih.gov/download
2. Import into SQLite using the provided scripts (see `scripts/gudid/`)

**Size:** ~3.5 GB

### Embeddings (`embeddings/`)

Pre-computed vector embeddings for semantic search of device names and manufacturers.

**Contents:**
- `device_embeddings.npz` - Device name embeddings (~93 MB)
- `device_metadata.json` - Device metadata (~3 MB)
- `manufacturer_embeddings.npz` - Manufacturer name embeddings (~40 MB)
- `manufacturer_metadata.json` - Manufacturer metadata (~1.5 MB)
- `synonym_embeddings.npz` - Medical synonym/abbreviation embeddings (~300 KB)
- `synonym_metadata.json` - Synonym mappings (~12 KB)

**To generate:**
```bash
# Requires OPENROUTER_API_KEY or AI_API_KEY in environment
cd /path/to/openfda-insights
python scripts/embeddings/create_embeddings_v2.py
```

**Note:** Generating embeddings requires API calls to OpenRouter (using `openai/text-embedding-3-small` model) and may take 10-30 minutes depending on database size.

## Directory Structure

```
data/
├── README.md              # This file
├── gudid.db               # GUDID SQLite database (not in git)
└── embeddings/            # Vector embeddings (not in git)
    ├── device_embeddings.npz
    ├── device_metadata.json
    ├── manufacturer_embeddings.npz
    ├── manufacturer_metadata.json
    ├── synonym_embeddings.npz
    └── synonym_metadata.json
```
