#!/usr/bin/env python3
"""
Build Classification Cache - Query FDA API to build product_code → device_class mapping.

Usage:
    python scripts/build_classification_cache.py

This script:
1. Gets all unique product codes from GUDID database
2. Queries FDA classifications API for each product code
3. Saves the mapping to data/product_code_classes.json
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import duckdb
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GUDID_DB_PATH = DATA_DIR / "gudid.db"
OUTPUT_PATH = DATA_DIR / "product_code_classes.json"

FDA_API_BASE = "https://api.fda.gov/"
REQUESTS_PER_SECOND = 20
BATCH_SIZE = 100


async def get_unique_product_codes(db_path: Path) -> list[str]:
    """Get all unique product codes from GUDID database."""
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        result = conn.execute(
            "SELECT DISTINCT product_code FROM product_codes WHERE product_code IS NOT NULL"
        ).fetchall()
        codes = [row[0] for row in result if row[0]]
        logger.info(f"Found {len(codes)} unique product codes in GUDID")
        return codes
    finally:
        conn.close()


async def fetch_device_class(client: httpx.AsyncClient, product_code: str) -> tuple[str, str | None]:
    """Fetch device class for a single product code."""
    try:
        url = f"{FDA_API_BASE}device/classification.json"
        params = {"search": f'product_code:"{product_code}"', "limit": 1}
        response = await client.get(url, params=params)

        if response.status_code == 404:
            return (product_code, None)

        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        if results:
            device_class = results[0].get("device_class")
            return (product_code, device_class)
        return (product_code, None)
    except Exception as e:
        logger.warning(f"Error fetching {product_code}: {e}")
        return (product_code, None)


async def fetch_batch(client: httpx.AsyncClient, codes: list[str]) -> dict[str, str | None]:
    """Fetch device classes for a batch of product codes."""
    tasks = [fetch_device_class(client, code) for code in codes]
    results = await asyncio.gather(*tasks)
    return {code: device_class for code, device_class in results}


async def build_cache(db_path: Path, output_path: Path) -> int:
    """Build the classification cache."""
    codes = await get_unique_product_codes(db_path)

    if not codes:
        logger.error("No product codes found in database")
        return 0

    cache: dict[str, str] = {}
    processed = 0
    not_found = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(0, len(codes), BATCH_SIZE):
            batch = codes[i : i + BATCH_SIZE]
            batch_results = await fetch_batch(client, batch)

            for code, device_class in batch_results.items():
                if device_class:
                    cache[code.upper()] = device_class
                else:
                    not_found += 1

            processed += len(batch)
            if processed % 500 == 0 or processed == len(codes):
                logger.info(f"Processed {processed}/{len(codes)} codes ({len(cache)} found, {not_found} not found)")

            await asyncio.sleep(1.0 / REQUESTS_PER_SECOND * len(batch))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cache, sort_keys=True, indent=2))
    logger.info(f"Saved {len(cache)} classifications to {output_path}")
    return len(cache)


def main():
    if not GUDID_DB_PATH.exists():
        logger.error(f"GUDID database not found: {GUDID_DB_PATH}")
        sys.exit(1)

    logger.info(f"Building classification cache from {GUDID_DB_PATH}")
    count = asyncio.run(build_cache(GUDID_DB_PATH, OUTPUT_PATH))
    logger.info(f"Done! Created cache with {count} entries")


if __name__ == "__main__":
    main()
