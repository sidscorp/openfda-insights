"""
Hybrid retrieval: BM25 + embeddings with endpoint prefiltering.

Rationale: CEO resolution #2 - boost RAG precision to ≥90% via hybrid search.
Combines keyword matching (BM25) with semantic search, plus metadata filtering.
"""
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


# Endpoint aliases for prefiltering
ENDPOINT_ALIASES = {
    "510k": ["510k", "k-number", "k number", "kxxxxx", "k-", "clearance", "premarket notification"],
    "pma": ["pma", "p-number", "p number", "p-", "premarket approval"],
    "classification": [
        "class i",
        "class ii",
        "class iii",
        "class 1",
        "class 2",
        "class 3",
        "classification",
        "regulation number",
        "product code",
    ],
    "recall": [
        "recall",
        "enforcement",
        "class i recall",
        "class ii recall",
        "class iii recall",
        "recall class",
    ],
    "maude": ["maude", "adverse event", "event report", "foi", "injury", "death", "malfunction"],
    "udi": ["udi", "gudid", "device identifier", "di", "pi", "unique device"],
    "rl_search": [
        "registration",
        "listing",
        "establishment",
        "owner/operator",
        "fei",
        "duns",
        "facility",
    ],
}


def infer_endpoint_hint(query: str) -> List[str]:
    """
    Infer which endpoints are likely relevant based on query keywords.

    Args:
        query: User question

    Returns:
        List of endpoint names that match query keywords
    """
    q_lower = query.lower()
    hints = []

    for endpoint, keywords in ENDPOINT_ALIASES.items():
        if any(kw in q_lower for kw in keywords):
            hints.append(endpoint)

    return hints


class HybridRetriever:
    """
    Hybrid retriever combining BM25 keyword search and semantic embeddings.

    Uses reciprocal rank fusion (RRF) to combine scores from both methods.
    Supports endpoint prefiltering via metadata.
    """

    def __init__(
        self,
        docs: List[Dict[str, Any]],
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """
        Initialize hybrid retriever.

        Args:
            docs: List of doc dicts with 'text' and 'metadata' keys
            embedding_model: Sentence transformer model name
        """
        self.docs = docs
        self.doc_texts = [d["text"] for d in docs]

        # Initialize BM25
        tokenized_docs = [doc.lower().split() for doc in self.doc_texts]
        self.bm25 = BM25Okapi(tokenized_docs)

        # Initialize embeddings
        self.encoder = SentenceTransformer(embedding_model)
        self.doc_embeddings = self.encoder.encode(
            self.doc_texts, convert_to_numpy=True, show_progress_bar=False
        )

    def search(
        self,
        query: str,
        top_k: int = 6,
        min_score: float = 0.0,
        use_endpoint_filter: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search using hybrid BM25 + embeddings with RRF fusion.

        Args:
            query: Search query
            top_k: Number of results to return
            min_score: Minimum relevance score (not used in RRF, kept for API compat)
            use_endpoint_filter: Whether to prefilter by endpoint hints

        Returns:
            List of dicts with 'text', 'metadata', 'score' keys
        """
        # 1) Endpoint prefiltering
        endpoint_hints = set(infer_endpoint_hint(query)) if use_endpoint_filter else set()
        candidate_ids = list(range(len(self.docs)))

        if endpoint_hints:
            filtered_ids = [
                i
                for i, doc in enumerate(self.docs)
                if doc.get("metadata", {}).get("endpoint") in endpoint_hints
            ]
            if filtered_ids:
                candidate_ids = filtered_ids
                print(
                    f"[HybridRetriever] Prefiltered to {len(candidate_ids)} docs matching endpoints: {endpoint_hints}"
                )

        # 2) BM25 search over candidates
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_hits = [(i, bm25_scores[i]) for i in candidate_ids]
        bm25_hits = sorted(bm25_hits, key=lambda x: x[1], reverse=True)[:50]

        # 3) Embedding search over candidates
        query_embedding = self.encoder.encode([query], convert_to_numpy=True)
        candidate_embeddings = self.doc_embeddings[candidate_ids]
        emb_scores = cosine_similarity(query_embedding, candidate_embeddings)[0]
        emb_hits = [(candidate_ids[i], emb_scores[i]) for i in range(len(candidate_ids))]
        emb_hits = sorted(emb_hits, key=lambda x: x[1], reverse=True)[:50]

        # 4) Reciprocal Rank Fusion (RRF)
        # RRF formula: score = sum(1 / (k + rank)) for each method
        # k=60 is a common constant from literature
        rrf_scores = defaultdict(float)

        for rank, (doc_id, _) in enumerate(bm25_hits):
            rrf_scores[doc_id] += 1.0 / (60 + rank)

        for rank, (doc_id, _) in enumerate(emb_hits):
            rrf_scores[doc_id] += 1.0 / (60 + rank)

        # 5) Sort by fused score and return top-k
        fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for doc_id, score in fused:
            results.append(
                {
                    "text": self.docs[doc_id]["text"],
                    "metadata": self.docs[doc_id].get("metadata", {}),
                    "score": score,
                }
            )

        return results
