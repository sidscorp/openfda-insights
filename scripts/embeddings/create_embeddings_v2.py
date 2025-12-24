#!/usr/bin/env python3
"""
Create embeddings for FDA device names AND manufacturers using OpenRouter API.
V2: Adds manufacturer embeddings and synonym layer support.
"""
import os
import sys
import json
import time
import asyncio
from pathlib import Path
from collections import defaultdict

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


async def embed_items(items: list[dict], api_key: str, desc: str) -> tuple[list[dict], np.ndarray]:
    embeddings = []
    async with httpx.AsyncClient() as client:
        total_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE
        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i : i + BATCH_SIZE]
            batch_texts = [item["text"] for item in batch]
            batch_num = i // BATCH_SIZE + 1
            print(f"  {desc}: Batch {batch_num}/{total_batches} ({len(batch)} items)")
            batch_embeddings = await get_embeddings(client, batch_texts, api_key)
            embeddings.extend(batch_embeddings)
            await asyncio.sleep(0.1)
    return items, np.array(embeddings, dtype=np.float32)


def load_device_terms(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    items = []
    seen = set()

    results = conn.execute("""
        SELECT DISTINCT product_code, product_code_name
        FROM product_codes WHERE product_code_name IS NOT NULL
    """).fetchall()
    for code, name in results:
        key = name.lower().strip()
        if key not in seen:
            seen.add(key)
            items.append({
                "id": code,
                "text": name,
                "type": "product_code",
                "canonical": name,
            })

    results = conn.execute("""
        SELECT DISTINCT gmdn_code, gmdn_pt_name
        FROM gmdn_terms WHERE gmdn_pt_name IS NOT NULL
    """).fetchall()
    for code, name in results:
        key = name.lower().strip()
        if key not in seen:
            seen.add(key)
            items.append({
                "id": code,
                "text": name,
                "type": "gmdn",
                "canonical": name,
            })

    return items


def load_manufacturers(conn: duckdb.DuckDBPyConnection, min_devices: int = 5) -> list[dict]:
    results = conn.execute("""
        SELECT company_name, COUNT(*) as device_count
        FROM devices
        WHERE company_name IS NOT NULL
        GROUP BY company_name
        HAVING COUNT(*) >= ?
        ORDER BY device_count DESC
    """, [min_devices]).fetchall()

    items = []
    for name, count in results:
        items.append({
            "id": name,
            "text": name,
            "type": "manufacturer",
            "canonical": name,
            "device_count": count,
        })

    return items


def create_synonym_entries() -> list[dict]:
    """Create entries for common medical abbreviations and synonyms."""
    synonyms = {
        "c section": {"canonical": "cesarean section", "type": "synonym"},
        "c-section": {"canonical": "cesarean section", "type": "synonym"},
        "csection": {"canonical": "cesarean section", "type": "synonym"},
        "ICD": {"canonical": "implantable cardioverter defibrillator", "type": "abbreviation"},
        "AICD": {"canonical": "automatic implantable cardioverter defibrillator", "type": "abbreviation"},
        "hip replacement": {"canonical": "hip prosthesis", "type": "synonym"},
        "hip implant": {"canonical": "hip prosthesis", "type": "synonym"},
        "knee replacement": {"canonical": "knee prosthesis", "type": "synonym"},
        "pacemaker": {"canonical": "cardiac pacemaker pulse generator", "type": "synonym"},
        "defib": {"canonical": "defibrillator", "type": "abbreviation"},
        "AED": {"canonical": "automated external defibrillator", "type": "abbreviation"},
        "CT scanner": {"canonical": "computed tomography x-ray system", "type": "abbreviation"},
        "MRI": {"canonical": "magnetic resonance imaging system", "type": "abbreviation"},
        "EKG": {"canonical": "electrocardiograph", "type": "abbreviation"},
        "ECG": {"canonical": "electrocardiograph", "type": "abbreviation"},
        "IV catheter": {"canonical": "intravascular catheter", "type": "abbreviation"},
        "vent": {"canonical": "ventilator", "type": "abbreviation"},
        "ventilator": {"canonical": "emergency ventilator", "type": "synonym"},
        "blood pressure cuff": {"canonical": "sphygmomanometer", "type": "synonym"},
        "BP monitor": {"canonical": "blood pressure monitor", "type": "abbreviation"},
        "pulse ox": {"canonical": "pulse oximeter", "type": "abbreviation"},
        "CPAP": {"canonical": "continuous positive airway pressure", "type": "abbreviation"},
        "BiPAP": {"canonical": "bilevel positive airway pressure", "type": "abbreviation"},
        "stent": {"canonical": "intravascular stent", "type": "synonym"},
        "heart stent": {"canonical": "coronary artery stent", "type": "synonym"},
        "contact lens": {"canonical": "contact lens", "type": "synonym"},
        "contacts": {"canonical": "contact lens", "type": "synonym"},
        "hearing aid": {"canonical": "hearing aid", "type": "synonym"},
        "cochlear implant": {"canonical": "cochlear implant system", "type": "synonym"},
        "insulin pump": {"canonical": "insulin infusion pump", "type": "synonym"},
        "glucose monitor": {"canonical": "blood glucose monitor", "type": "synonym"},
        "CGM": {"canonical": "continuous glucose monitor", "type": "abbreviation"},
        "dialysis machine": {"canonical": "hemodialysis system", "type": "synonym"},
        "X-ray": {"canonical": "x-ray system", "type": "synonym"},
        "xray": {"canonical": "x-ray system", "type": "synonym"},
        "ultrasound": {"canonical": "ultrasonic imaging system", "type": "synonym"},
    }

    items = []
    for abbrev, info in synonyms.items():
        items.append({
            "id": f"syn_{abbrev.replace(' ', '_')}",
            "text": abbrev,
            "type": info["type"],
            "canonical": info["canonical"],
            "maps_to": info["canonical"],
        })
        if abbrev.lower() != info["canonical"].lower():
            items.append({
                "id": f"syn_{info['canonical'].replace(' ', '_')}",
                "text": info["canonical"],
                "type": "canonical_form",
                "canonical": info["canonical"],
            })

    seen = set()
    unique = []
    for item in items:
        key = item["text"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


async def main():
    api_key = os.getenv("AI_API_KEY")
    if not api_key:
        print("Error: AI_API_KEY not found in environment")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to GUDID database: {DB_PATH}")
    conn = duckdb.connect(str(DB_PATH), read_only=True)

    print("\nLoading items to embed...")

    device_terms = load_device_terms(conn)
    print(f"  Device terms (product codes + GMDN): {len(device_terms)}")

    manufacturers = load_manufacturers(conn, min_devices=5)
    print(f"  Manufacturers (5+ devices): {len(manufacturers)}")

    synonyms = create_synonym_entries()
    print(f"  Synonym entries: {len(synonyms)}")

    all_items = device_terms + manufacturers + synonyms
    print(f"\nTotal items to embed: {len(all_items)}")

    estimated_tokens = sum(len(item["text"].split()) * 1.3 for item in all_items)
    estimated_cost = (estimated_tokens / 1_000_000) * 0.02
    print(f"Estimated tokens: ~{int(estimated_tokens):,}")
    print(f"Estimated cost: ~${estimated_cost:.4f}")

    confirm = input("\nProceed with embedding? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    print("\n=== Embedding Device Terms ===")
    start = time.time()
    device_items, device_embeddings = await embed_items(device_terms, api_key, "Devices")

    print("\n=== Embedding Manufacturers ===")
    mfr_items, mfr_embeddings = await embed_items(manufacturers, api_key, "Manufacturers")

    print("\n=== Embedding Synonyms ===")
    syn_items, syn_embeddings = await embed_items(synonyms, api_key, "Synonyms")

    elapsed = time.time() - start
    print(f"\nCompleted in {elapsed:.1f}s")

    print("\nSaving device embeddings...")
    np.savez_compressed(OUTPUT_DIR / "device_embeddings_v2.npz", embeddings=device_embeddings)
    with open(OUTPUT_DIR / "device_metadata_v2.json", "w") as f:
        json.dump({
            "items": device_items,
            "model": MODEL,
            "dimension": device_embeddings.shape[1],
            "count": len(device_items),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, f, indent=2)

    print("Saving manufacturer embeddings...")
    np.savez_compressed(OUTPUT_DIR / "manufacturer_embeddings.npz", embeddings=mfr_embeddings)
    with open(OUTPUT_DIR / "manufacturer_metadata.json", "w") as f:
        json.dump({
            "items": mfr_items,
            "model": MODEL,
            "dimension": mfr_embeddings.shape[1],
            "count": len(mfr_items),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, f, indent=2)

    print("Saving synonym embeddings...")
    np.savez_compressed(OUTPUT_DIR / "synonym_embeddings.npz", embeddings=syn_embeddings)
    with open(OUTPUT_DIR / "synonym_metadata.json", "w") as f:
        json.dump({
            "items": syn_items,
            "model": MODEL,
            "dimension": syn_embeddings.shape[1],
            "count": len(syn_items),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, f, indent=2)

    conn.close()
    print("\nDone! Created:")
    print(f"  - device_embeddings_v2.npz ({device_embeddings.shape})")
    print(f"  - manufacturer_embeddings.npz ({mfr_embeddings.shape})")
    print(f"  - synonym_embeddings.npz ({syn_embeddings.shape})")


if __name__ == "__main__":
    asyncio.run(main())
