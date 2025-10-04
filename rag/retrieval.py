"""
RAG retrieval service for openFDA documentation.

Rationale: Hybrid search (BM25 + embeddings) with endpoint prefiltering.
CEO resolution #2 - boost precision to ≥90% via hybrid search.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from rag.hybrid import HybridRetriever


class RetrievalResult(BaseModel):
    """A retrieved documentation chunk with relevance score."""

    url: str = Field(description="Source URL")
    endpoint: str = Field(description="Endpoint name")
    section: str = Field(description="Section heading")
    content: str = Field(description="Markdown content")
    score: float = Field(description="Relevance score (0-1)")


class DocRetriever:
    """
    Hybrid search (BM25 + embeddings) over openFDA documentation corpus.

    Uses HybridRetriever for improved precision via keyword + semantic matching.
    Includes endpoint prefiltering for better routing accuracy.
    """

    def __init__(
        self,
        corpus_path: str = "docs/corpus.json",
        model_name: str = "all-MiniLM-L6-v2",
        use_hybrid: bool = True,
    ):
        """
        Initialize retriever.

        Args:
            corpus_path: Path to scraped docs JSON
            model_name: Sentence-transformers model (default: all-MiniLM-L6-v2, 384-dim, fast)
            use_hybrid: Use hybrid (BM25+embeddings) vs pure semantic (default: True)
        """
        self.corpus_path = Path(corpus_path)
        self.model_name = model_name
        self.use_hybrid = use_hybrid

        # Load corpus
        if not self.corpus_path.exists():
            raise FileNotFoundError(
                f"Corpus not found: {corpus_path}. Run: python -m rag.scraper"
            )

        with self.corpus_path.open() as f:
            raw_corpus = json.load(f)

        # Convert to format expected by HybridRetriever
        self.docs = [
            {
                "text": chunk["content"],
                "metadata": {
                    "url": chunk["url"],
                    "endpoint": chunk["endpoint"],
                    "section": chunk["section"],
                },
            }
            for chunk in raw_corpus
        ]

        # Initialize retriever
        if use_hybrid:
            print(f"Loading hybrid retriever (BM25 + {model_name})...")
            self.retriever = HybridRetriever(self.docs, embedding_model=model_name)
        else:
            # Fallback to pure semantic search
            print(f"Loading embedding model: {model_name}...")
            self.encoder = SentenceTransformer(model_name)
            print(f"Embedding {len(self.docs)} chunks...")
            self.doc_texts = [d["text"] for d in self.docs]
            self.doc_embeddings = self.encoder.encode(
                self.doc_texts, convert_to_numpy=True, show_progress_bar=False
            )

        print(f"✓ Retriever ready ({len(self.docs)} docs)")

    def search(self, query: str, top_k: int = 3, min_score: float = 0.0) -> List[RetrievalResult]:
        """
        Search docs corpus for relevant chunks.

        Args:
            query: User question or search query
            top_k: Number of top results to return
            min_score: Minimum relevance score threshold (not enforced in hybrid mode)

        Returns:
            List of RetrievalResult, ranked by relevance
        """
        if self.use_hybrid:
            # Use hybrid retriever
            raw_results = self.retriever.search(query, top_k=top_k, min_score=min_score)
            # Convert to RetrievalResult format
            results = []
            for r in raw_results:
                results.append(
                    RetrievalResult(
                        url=r["metadata"]["url"],
                        endpoint=r["metadata"]["endpoint"],
                        section=r["metadata"]["section"],
                        content=r["text"],
                        score=r["score"],
                    )
                )
            return results
        else:
            # Fallback to pure semantic search
            query_embedding = self.encoder.encode([query], convert_to_numpy=True)
            similarities = cosine_similarity(query_embedding, self.doc_embeddings)[0]
            top_indices = np.argsort(similarities)[::-1][:top_k]

            results = []
            for idx in top_indices:
                score = float(similarities[idx])
                if score >= min_score:
                    doc = self.docs[idx]
                    results.append(
                        RetrievalResult(
                            url=doc["metadata"]["url"],
                            endpoint=doc["metadata"]["endpoint"],
                            section=doc["metadata"]["section"],
                            content=doc["text"],
                            score=score,
                        )
                    )
            return results

    def get_routing_hints(self) -> str:
        """Load routing hints document."""
        hints_path = Path("docs/routing_hints.md")
        if hints_path.exists():
            return hints_path.read_text()
        return ""


def main():
    """CLI for RAG retrieval testing."""
    parser = argparse.ArgumentParser(
        description="Query openFDA documentation corpus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m rag.retrieval "How do I search by date range?"
  python -m rag.retrieval "What fields are in the 510k endpoint?" --top-k 5
        """,
    )
    parser.add_argument("query", help="Search query")
    parser.add_argument(
        "--top-k", type=int, default=3, help="Number of results to return (default: 3)"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.3,
        help="Minimum relevance score 0-1 (default: 0.3)",
    )
    parser.add_argument(
        "--corpus", default="docs/corpus.json", help="Path to corpus JSON"
    )
    parser.add_argument("--config", help="Path to config file (unused, reserved)")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )

    args = parser.parse_args()

    # Initialize retriever
    try:
        retriever = DocRetriever(corpus_path=args.corpus)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Search
    results = retriever.search(args.query, top_k=args.top_k, min_score=args.min_score)

    if not results:
        print(f"No results found for: {args.query}")
        sys.exit(0)

    # Display results
    print(f"\n=== Results for: {args.query} ===\n")
    for i, result in enumerate(results, 1):
        print(f"[{i}] {result.section} ({result.endpoint}) - Score: {result.score:.3f}")
        print(f"    URL: {result.url}")
        print(f"    {result.content[:200]}...")
        print()


if __name__ == "__main__":
    main()
