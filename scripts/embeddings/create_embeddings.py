#!/usr/bin/env python3
"""
Create embeddings for FDA device names using OpenRouter API.
Embeds product code names and GMDN terms for semantic search.
"""
import os
import sys
import json
import time
import asyncio
from pathlib import Path
from typing import Optional

import httpx
import duckdb
import numpy as np
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/embeddings"
MODEL = "openai/text-embedding-3-small"
BATCH_SIZE = 100
MAX_RETRIES = 3
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "embeddings"
DB_PATH = Path(__file__).parent.parent.parent / "data" / "gudid.db"


async def get_embeddings(client: httpx.AsyncClient, texts: list[str], api_key: str) -> list[list[float]]:
    """Get embeddings for a batch of texts."""
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": MODEL, "input": texts},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                print(f"  Retry {attempt + 1}/{MAX_RETRIES} after {wait}s: {e}")
                await asyncio.sleep(wait)
            else:
                raise


async def embed_items(
    items: list[tuple[str, str, str]],
    api_key: str,
    desc: str,
) -> tuple[list[str], list[str], list[str], np.ndarray]:
    """Embed a list of (id, name, source_type) tuples."""
    ids, names, sources = [], [], []
    embeddings = []

    async with httpx.AsyncClient() as client:
        total_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE

        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i : i + BATCH_SIZE]
            batch_ids = [item[0] for item in batch]
            batch_names = [item[1] for item in batch]
            batch_sources = [item[2] for item in batch]

            batch_num = i // BATCH_SIZE + 1
            print(f"  {desc}: Batch {batch_num}/{total_batches} ({len(batch)} items)")

            batch_embeddings = await get_embeddings(client, batch_names, api_key)

            ids.extend(batch_ids)
            names.extend(batch_names)
            sources.extend(batch_sources)
            embeddings.extend(batch_embeddings)

            await asyncio.sleep(0.1)

    return ids, names, sources, np.array(embeddings, dtype=np.float32)


def load_product_codes(conn: duckdb.DuckDBPyConnection) -> list[tuple[str, str, str]]:
    """Load unique product code names from GUDID."""
    results = conn.execute("""
        SELECT DISTINCT product_code, product_code_name
        FROM product_codes
        WHERE product_code_name IS NOT NULL
        ORDER BY product_code
    """).fetchall()
    return [(row[0], row[1], "product_code") for row in results]


def load_gmdn_terms(conn: duckdb.DuckDBPyConnection) -> list[tuple[str, str, str]]:
    """Load unique GMDN terms from GUDID."""
    results = conn.execute("""
        SELECT DISTINCT gmdn_code, gmdn_pt_name
        FROM gmdn_terms
        WHERE gmdn_pt_name IS NOT NULL
        ORDER BY gmdn_code
    """).fetchall()
    return [(row[0], row[1], "gmdn") for row in results]


def load_fda_classifications(limit: int = 5000) -> list[tuple[str, str, str]]:
    """Load device names from FDA classification API for broader coverage."""
    import httpx

    print(f"  Fetching FDA classification device names (limit={limit})...")
    items = []

    try:
        response = httpx.get(
            "https://api.fda.gov/device/classification.json",
            params={"limit": limit},
            timeout=30,
        )
        response.raise_for_status()
        results = response.json().get("results", [])

        seen = set()
        for r in results:
            name = r.get("device_name")
            code = r.get("product_code")
            if name and code and name not in seen:
                seen.add(name)
                items.append((code, name, "fda_classification"))

        print(f"  Got {len(items)} unique FDA classification names")
    except Exception as e:
        print(f"  Warning: Could not fetch FDA classifications: {e}")

    return items


async def main():
    api_key = os.getenv("AI_API_KEY")
    if not api_key:
        print("Error: AI_API_KEY not found in environment")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to GUDID database: {DB_PATH}")
    conn = duckdb.connect(str(DB_PATH), read_only=True)

    print("\nLoading items to embed...")
    product_codes = load_product_codes(conn)
    print(f"  Product codes: {len(product_codes)}")

    gmdn_terms = load_gmdn_terms(conn)
    print(f"  GMDN terms: {len(gmdn_terms)}")

    fda_classifications = load_fda_classifications(limit=1000)
    print(f"  FDA classifications: {len(fda_classifications)}")

    all_items = product_codes + gmdn_terms + fda_classifications
    unique_names = {}
    for item in all_items:
        name_lower = item[1].lower().strip()
        if name_lower not in unique_names:
            unique_names[name_lower] = item

    items = list(unique_names.values())
    print(f"\nTotal unique items to embed: {len(items)}")

    estimated_tokens = sum(len(item[1].split()) * 1.3 for item in items)
    estimated_cost = (estimated_tokens / 1_000_000) * 0.02
    print(f"Estimated tokens: ~{int(estimated_tokens):,}")
    print(f"Estimated cost: ~${estimated_cost:.4f}")

    confirm = input("\nProceed with embedding? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    print("\nGenerating embeddings...")
    start = time.time()
    ids, names, sources, embeddings = await embed_items(items, api_key, "Embedding")
    elapsed = time.time() - start

    print(f"\nCompleted in {elapsed:.1f}s")
    print(f"Embeddings shape: {embeddings.shape}")

    embeddings_file = OUTPUT_DIR / "device_embeddings.npz"
    metadata_file = OUTPUT_DIR / "device_metadata.json"

    np.savez_compressed(embeddings_file, embeddings=embeddings)
    print(f"Saved embeddings to: {embeddings_file}")

    metadata = {
        "ids": ids,
        "names": names,
        "sources": sources,
        "model": MODEL,
        "dimension": embeddings.shape[1],
        "count": len(ids),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata to: {metadata_file}")

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
