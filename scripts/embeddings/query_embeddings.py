#!/usr/bin/env python3
"""
Query FDA device embeddings for semantic search.
Finds devices semantically similar to a query string.
"""
import os
import sys
import json
import argparse
from pathlib import Path

import httpx
import numpy as np
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/embeddings"
MODEL = "openai/text-embedding-3-small"
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "embeddings"


def load_embeddings():
    """Load pre-computed embeddings and metadata."""
    embeddings_file = DATA_DIR / "device_embeddings.npz"
    metadata_file = DATA_DIR / "device_metadata.json"

    if not embeddings_file.exists() or not metadata_file.exists():
        print("Error: Embeddings not found. Run create_embeddings.py first.")
        sys.exit(1)

    embeddings = np.load(embeddings_file)["embeddings"]
    with open(metadata_file) as f:
        metadata = json.load(f)

    return embeddings, metadata


def get_query_embedding(query: str, api_key: str) -> np.ndarray:
    """Get embedding for a query string."""
    response = httpx.post(
        OPENROUTER_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"model": MODEL, "input": [query]},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return np.array(data["data"][0]["embedding"], dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query vector and all embeddings."""
    a_norm = a / np.linalg.norm(a)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return np.dot(b_norm, a_norm)


def search(query: str, embeddings: np.ndarray, metadata: dict, top_k: int = 10) -> list[dict]:
    """Search for similar devices."""
    api_key = os.getenv("AI_API_KEY")
    if not api_key:
        print("Error: AI_API_KEY not found")
        sys.exit(1)

    query_embedding = get_query_embedding(query, api_key)
    similarities = cosine_similarity(query_embedding, embeddings)
    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for idx in top_indices:
        results.append({
            "id": metadata["ids"][idx],
            "name": metadata["names"][idx],
            "source": metadata["sources"][idx],
            "similarity": float(similarities[idx]),
        })

    return results


def interactive_mode(embeddings: np.ndarray, metadata: dict):
    """Interactive query mode."""
    print("\n" + "=" * 60)
    print("FDA Device Semantic Search")
    print("=" * 60)
    print(f"Loaded {metadata['count']:,} device embeddings")
    print("Type a query to search, or 'quit' to exit.\n")

    while True:
        try:
            query = input("Query: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        print(f"\nSearching for: '{query}'")
        print("-" * 40)

        try:
            results = search(query, embeddings, metadata, top_k=10)

            for i, r in enumerate(results, 1):
                source_label = {
                    "product_code": "PC",
                    "gmdn": "GMDN",
                    "fda_classification": "FDA",
                }.get(r["source"], r["source"])

                print(f"{i:2}. [{source_label}] {r['id']}: {r['name']}")
                print(f"     Similarity: {r['similarity']:.4f}")

            print()
        except Exception as e:
            print(f"Error: {e}\n")


def main():
    parser = argparse.ArgumentParser(description="Query FDA device embeddings")
    parser.add_argument("query", nargs="?", help="Search query (interactive mode if not provided)")
    parser.add_argument("-k", "--top-k", type=int, default=10, help="Number of results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    embeddings, metadata = load_embeddings()

    if args.query:
        results = search(args.query, embeddings, metadata, top_k=args.top_k)

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"\nTop {args.top_k} results for '{args.query}':\n")
            for i, r in enumerate(results, 1):
                print(f"{i:2}. [{r['source']}] {r['id']}: {r['name']}")
                print(f"     Similarity: {r['similarity']:.4f}")
    else:
        interactive_mode(embeddings, metadata)


if __name__ == "__main__":
    main()
