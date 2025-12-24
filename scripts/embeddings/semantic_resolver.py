#!/usr/bin/env python3
"""
Semantic Device Resolver - Combines embeddings with GUDID search.

This demonstrates how embeddings augment (not replace) existing search:
1. Embeddings find semantically similar terms (c section → cesarean section)
2. Those terms drive a broader GUDID search
3. Result: ALL relevant product codes, not just one
"""
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional

import httpx
import numpy as np
import duckdb
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/embeddings"
MODEL = "openai/text-embedding-3-small"
DATA_DIR = Path(__file__).parent.parent.parent / "data"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"
DB_PATH = DATA_DIR / "gudid.db"


class SemanticResolver:
    def __init__(self):
        self.api_key = os.getenv("AI_API_KEY")
        self.device_embeddings = None
        self.device_metadata = None
        self.mfr_embeddings = None
        self.mfr_metadata = None
        self.synonym_embeddings = None
        self.synonym_metadata = None
        self.conn = None

    def load(self):
        print("Loading embeddings...")

        dev_file = EMBEDDINGS_DIR / "device_embeddings.npz"
        dev_meta = EMBEDDINGS_DIR / "device_metadata.json"
        if dev_file.exists():
            self.device_embeddings = np.load(dev_file)["embeddings"]
            with open(dev_meta) as f:
                self.device_metadata = json.load(f)
            print(f"  Devices: {self.device_embeddings.shape[0]} embeddings")

        mfr_file = EMBEDDINGS_DIR / "manufacturer_embeddings.npz"
        mfr_meta = EMBEDDINGS_DIR / "manufacturer_metadata.json"
        if mfr_file.exists():
            self.mfr_embeddings = np.load(mfr_file)["embeddings"]
            with open(mfr_meta) as f:
                self.mfr_metadata = json.load(f)
            print(f"  Manufacturers: {self.mfr_embeddings.shape[0]} embeddings")

        syn_file = EMBEDDINGS_DIR / "synonym_embeddings.npz"
        syn_meta = EMBEDDINGS_DIR / "synonym_metadata.json"
        if syn_file.exists():
            self.synonym_embeddings = np.load(syn_file)["embeddings"]
            with open(syn_meta) as f:
                self.synonym_metadata = json.load(f)
            print(f"  Synonyms: {self.synonym_embeddings.shape[0]} embeddings")

        print("Connecting to GUDID...")
        self.conn = duckdb.connect(str(DB_PATH), read_only=True)
        print("Ready!\n")

    def get_embedding(self, text: str) -> np.ndarray:
        response = httpx.post(
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": MODEL, "input": [text]},
            timeout=30,
        )
        response.raise_for_status()
        return np.array(response.json()["data"][0]["embedding"], dtype=np.float32)

    def cosine_similarity(self, query_vec: np.ndarray, embeddings: np.ndarray) -> np.ndarray:
        query_norm = query_vec / np.linalg.norm(query_vec)
        emb_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        return np.dot(emb_norm, query_norm)

    def find_similar_devices(self, query: str, top_k: int = 5) -> list[dict]:
        if self.device_embeddings is None:
            return []

        query_vec = self.get_embedding(query)
        sims = self.cosine_similarity(query_vec, self.device_embeddings)
        top_idx = np.argsort(sims)[::-1][:top_k]

        results = []
        ids = self.device_metadata.get("ids", [])
        names = self.device_metadata.get("names", [])
        sources = self.device_metadata.get("sources", [])

        for idx in top_idx:
            results.append({
                "id": ids[idx] if ids else str(idx),
                "name": names[idx] if names else "unknown",
                "source": sources[idx] if sources else "unknown",
                "similarity": float(sims[idx]),
            })
        return results

    def find_similar_manufacturers(self, query: str, top_k: int = 5) -> list[dict]:
        if self.mfr_embeddings is None:
            return []

        query_vec = self.get_embedding(query)
        sims = self.cosine_similarity(query_vec, self.mfr_embeddings)
        top_idx = np.argsort(sims)[::-1][:top_k]

        results = []
        items = self.mfr_metadata.get("items", [])
        for idx in top_idx:
            item = items[idx]
            results.append({
                "name": item["text"],
                "device_count": item.get("device_count", 0),
                "similarity": float(sims[idx]),
            })
        return results

    def check_synonyms(self, query: str) -> list[dict]:
        """Check if query matches a known synonym/abbreviation."""
        if self.synonym_embeddings is None:
            return []

        query_vec = self.get_embedding(query)
        sims = self.cosine_similarity(query_vec, self.synonym_embeddings)
        top_idx = np.argsort(sims)[::-1][:5]

        results = []
        items = self.synonym_metadata.get("items", [])
        for idx in top_idx:
            item = items[idx]
            results.append({
                "text": item["text"],
                "canonical": item.get("canonical", item["text"]),
                "type": item["type"],
                "similarity": float(sims[idx]),
            })
        return results

    def expand_query_terms(self, query: str) -> list[str]:
        """Get expanded search terms from synonyms + embeddings."""
        terms = [query]

        synonyms = self.check_synonyms(query)
        for syn in synonyms:
            if syn["similarity"] > 0.75 and syn.get("canonical"):
                terms.append(syn["canonical"])

        similar = self.find_similar_devices(query, top_k=3)
        for item in similar:
            if item["similarity"] > 0.6:
                terms.append(item["name"])

        return list(set(terms))

    def search_gudid(self, terms: list[str], limit: int = 50) -> dict:
        """Search GUDID with multiple terms, aggregate results."""
        all_codes = {}

        for term in terms:
            results = self.conn.execute("""
                SELECT
                    pc.product_code,
                    MAX(pc.product_code_name) as name,
                    COUNT(DISTINCT pc.device_key) as device_count
                FROM product_codes pc
                WHERE pc.product_code_name ILIKE ?
                GROUP BY pc.product_code
                ORDER BY device_count DESC
                LIMIT ?
            """, [f"%{term}%", limit]).fetchall()

            for code, name, count in results:
                if code not in all_codes or count > all_codes[code]["device_count"]:
                    all_codes[code] = {
                        "code": code,
                        "name": name,
                        "device_count": count,
                        "matched_term": term,
                    }

        sorted_codes = sorted(all_codes.values(), key=lambda x: x["device_count"], reverse=True)
        return {"product_codes": sorted_codes, "search_terms": terms}

    def resolve_device(self, query: str, verbose: bool = True) -> dict:
        """Full resolution: synonyms → embeddings → term expansion → GUDID search."""
        if verbose:
            print(f"Query: '{query}'")
            print("-" * 50)

        if verbose:
            print("\n1. SYNONYM CHECK")
        synonyms = self.check_synonyms(query)
        if verbose:
            if synonyms and synonyms[0]["similarity"] > 0.7:
                for syn in synonyms[:3]:
                    print(f"   {syn['similarity']:.2f} | '{syn['text']}' → '{syn['canonical']}' ({syn['type']})")
            else:
                print("   No strong synonym matches")

        if verbose:
            print("\n2. SEMANTIC EXPANSION (embeddings)")
        similar = self.find_similar_devices(query, top_k=5)
        if verbose:
            for item in similar[:3]:
                print(f"   {item['similarity']:.2f} | [{item['source']}] {item['name']}")

        expanded_terms = [query]

        for syn in synonyms:
            if syn["similarity"] > 0.75 and syn.get("canonical"):
                expanded_terms.append(syn["canonical"])

        for item in similar:
            if item["similarity"] > 0.65:
                name_words = item["name"].lower().split()
                query_words = query.lower().split()
                if not all(w in name_words for w in query_words):
                    expanded_terms.append(item["name"])

        if verbose:
            print(f"\n3. EXPANDED SEARCH TERMS")
            for t in expanded_terms:
                print(f"   → {t}")

        if verbose:
            print(f"\n4. GUDID SEARCH RESULTS")
        gudid_results = self.search_gudid(expanded_terms, limit=30)

        if verbose:
            codes = gudid_results["product_codes"]
            print(f"   Found {len(codes)} product codes:")
            for pc in codes[:10]:
                print(f"   {pc['code']}: {pc['name']} ({pc['device_count']} devices)")
                print(f"         matched: '{pc['matched_term']}'")
            if len(codes) > 10:
                print(f"   ... and {len(codes) - 10} more")

        return {
            "query": query,
            "semantic_matches": similar,
            "expanded_terms": expanded_terms,
            "product_codes": gudid_results["product_codes"],
        }

    def resolve_manufacturer(self, query: str, verbose: bool = True) -> dict:
        """Resolve manufacturer name using embeddings."""
        if verbose:
            print(f"Manufacturer Query: '{query}'")
            print("-" * 50)

        if verbose:
            print("\n1. SEMANTIC MATCHES (embeddings)")
        similar = self.find_similar_manufacturers(query, top_k=10)
        if verbose:
            for item in similar[:5]:
                print(f"   {item['similarity']:.2f} | {item['name']} ({item['device_count']} devices)")

        if verbose:
            print(f"\n2. DIRECT DATABASE SEARCH")
        db_results = self.conn.execute("""
            SELECT company_name, COUNT(*) as cnt
            FROM devices
            WHERE company_name ILIKE ?
            GROUP BY company_name
            ORDER BY cnt DESC
            LIMIT 10
        """, [f"%{query}%"]).fetchall()

        if verbose:
            for name, cnt in db_results:
                print(f"   {name} ({cnt} devices)")

        return {
            "query": query,
            "semantic_matches": similar,
            "database_matches": [{"name": r[0], "device_count": r[1]} for r in db_results],
        }


def main():
    parser = argparse.ArgumentParser(description="Semantic Device Resolver")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--manufacturer", "-m", action="store_true", help="Search manufacturers")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    args = parser.parse_args()

    resolver = SemanticResolver()
    resolver.load()

    if args.interactive or not args.query:
        print("=" * 60)
        print("Semantic Device Resolver - Interactive Mode")
        print("=" * 60)
        print("Commands:")
        print("  <query>        - Search for devices")
        print("  m:<query>      - Search for manufacturers")
        print("  quit           - Exit")
        print()

        while True:
            try:
                query = input("Search: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not query:
                continue
            if query.lower() in ("quit", "exit", "q"):
                break

            if query.startswith("m:"):
                resolver.resolve_manufacturer(query[2:].strip())
            else:
                resolver.resolve_device(query)
            print()
    else:
        if args.manufacturer:
            resolver.resolve_manufacturer(args.query)
        else:
            resolver.resolve_device(args.query)


if __name__ == "__main__":
    main()
