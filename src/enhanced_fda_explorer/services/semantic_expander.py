"""
Semantic Expander - Expands device and manufacturer queries using embeddings.

Uses pre-computed embeddings to find semantically similar terms, enabling
queries like "c section tray" to match "Cesarean Section Tray" in FDA databases.
"""
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx
import numpy as np
from cachetools import TTLCache

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/embeddings"
EMBEDDING_MODEL = "openai/text-embedding-3-small"


@dataclass
class SemanticMatch:
    text: str
    source: str
    similarity: float
    canonical: Optional[str] = None


@dataclass
class SemanticExpansionResult:
    original_query: str
    expanded_terms: list[str]
    synonym_matches: list[SemanticMatch] = field(default_factory=list)
    semantic_matches: list[SemanticMatch] = field(default_factory=list)
    expansion_time_ms: float = 0.0


class SemanticExpander:
    """
    Expands search queries using pre-computed embeddings.

    Supports:
    - Device term expansion (product codes, GMDN terms)
    - Manufacturer name expansion
    - Curated synonym/abbreviation matching
    """

    def __init__(
        self,
        embeddings_dir: Path,
        api_key: str,
        synonym_threshold: float = 0.75,
        device_threshold: float = 0.60,
        manufacturer_threshold: float = 0.65,
        cache_size: int = 100,
        cache_ttl: int = 3600,
    ):
        self.embeddings_dir = Path(embeddings_dir)
        self.api_key = api_key
        self.synonym_threshold = synonym_threshold
        self.device_threshold = device_threshold
        self.manufacturer_threshold = manufacturer_threshold

        self._embedding_cache: TTLCache = TTLCache(maxsize=cache_size, ttl=cache_ttl)

        self._device_embeddings: Optional[np.ndarray] = None
        self._device_metadata: Optional[dict] = None
        self._manufacturer_embeddings: Optional[np.ndarray] = None
        self._manufacturer_metadata: Optional[dict] = None
        self._synonym_embeddings: Optional[np.ndarray] = None
        self._synonym_metadata: Optional[dict] = None

        self._loaded = False

    def _load_embeddings(self) -> None:
        """Lazy-load embeddings on first use."""
        if self._loaded:
            return

        logger.info(f"Loading embeddings from {self.embeddings_dir}")
        start = time.time()

        device_file = self.embeddings_dir / "device_embeddings.npz"
        device_meta = self.embeddings_dir / "device_metadata.json"
        if device_file.exists() and device_meta.exists():
            self._device_embeddings = np.load(device_file)["embeddings"]
            with open(device_meta) as f:
                self._device_metadata = json.load(f)
            logger.info(f"  Loaded {self._device_embeddings.shape[0]} device embeddings")

        mfr_file = self.embeddings_dir / "manufacturer_embeddings.npz"
        mfr_meta = self.embeddings_dir / "manufacturer_metadata.json"
        if mfr_file.exists() and mfr_meta.exists():
            self._manufacturer_embeddings = np.load(mfr_file)["embeddings"]
            with open(mfr_meta) as f:
                self._manufacturer_metadata = json.load(f)
            logger.info(f"  Loaded {self._manufacturer_embeddings.shape[0]} manufacturer embeddings")

        syn_file = self.embeddings_dir / "synonym_embeddings.npz"
        syn_meta = self.embeddings_dir / "synonym_metadata.json"
        if syn_file.exists() and syn_meta.exists():
            self._synonym_embeddings = np.load(syn_file)["embeddings"]
            with open(syn_meta) as f:
                self._synonym_metadata = json.load(f)
            logger.info(f"  Loaded {self._synonym_embeddings.shape[0]} synonym embeddings")

        elapsed = (time.time() - start) * 1000
        logger.info(f"Embeddings loaded in {elapsed:.0f}ms")
        self._loaded = True

    def _get_query_embedding(self, text: str) -> np.ndarray:
        """Get embedding for query text, with caching."""
        cache_key = text.lower().strip()
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        response = httpx.post(
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": EMBEDDING_MODEL, "input": [text]},
            timeout=30,
        )
        response.raise_for_status()
        embedding = np.array(response.json()["data"][0]["embedding"], dtype=np.float32)
        self._embedding_cache[cache_key] = embedding
        return embedding

    def _cosine_similarity(self, query_vec: np.ndarray, embeddings: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between query and all embeddings."""
        query_norm = query_vec / np.linalg.norm(query_vec)
        emb_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        return np.dot(emb_norm, query_norm)

    def _find_similar(
        self,
        query_vec: np.ndarray,
        embeddings: np.ndarray,
        metadata: dict,
        top_k: int = 5,
    ) -> list[SemanticMatch]:
        """Find top-k similar items from embeddings."""
        sims = self._cosine_similarity(query_vec, embeddings)
        top_idx = np.argsort(sims)[::-1][:top_k]

        results = []
        ids = metadata.get("ids", [])
        names = metadata.get("names", [])
        sources = metadata.get("sources", [])
        items = metadata.get("items", [])

        for idx in top_idx:
            if items:
                item = items[idx]
                results.append(SemanticMatch(
                    text=item.get("text", ""),
                    source=item.get("type", "unknown"),
                    similarity=float(sims[idx]),
                    canonical=item.get("canonical"),
                ))
            else:
                results.append(SemanticMatch(
                    text=names[idx] if names else str(idx),
                    source=sources[idx] if sources else "unknown",
                    similarity=float(sims[idx]),
                ))

        return results

    def _check_synonyms(self, query: str) -> list[SemanticMatch]:
        """Check if query matches known synonyms/abbreviations."""
        if self._synonym_embeddings is None or self._synonym_metadata is None:
            return []

        query_vec = self._get_query_embedding(query)
        return self._find_similar(
            query_vec,
            self._synonym_embeddings,
            self._synonym_metadata,
            top_k=5,
        )

    def expand_device_query(self, query: str) -> SemanticExpansionResult:
        """
        Expand a device query using synonyms and semantic similarity.

        Returns expanded terms to search for, including the original query.
        """
        start = time.time()
        self._load_embeddings()

        expanded_terms = [query]
        synonym_matches = []
        semantic_matches = []

        try:
            synonyms = self._check_synonyms(query)
            for syn in synonyms:
                if syn.similarity >= self.synonym_threshold and syn.canonical:
                    synonym_matches.append(syn)
                    if syn.canonical.lower() != query.lower():
                        expanded_terms.append(syn.canonical)

            if self._device_embeddings is not None and self._device_metadata is not None:
                query_vec = self._get_query_embedding(query)
                similar = self._find_similar(
                    query_vec,
                    self._device_embeddings,
                    self._device_metadata,
                    top_k=5,
                )

                for item in similar:
                    if item.similarity >= self.device_threshold:
                        semantic_matches.append(item)
                        if item.text.lower() not in [t.lower() for t in expanded_terms]:
                            expanded_terms.append(item.text)

        except Exception as e:
            logger.warning(f"Semantic expansion failed for '{query}': {e}")

        elapsed = (time.time() - start) * 1000
        return SemanticExpansionResult(
            original_query=query,
            expanded_terms=list(dict.fromkeys(expanded_terms)),
            synonym_matches=synonym_matches,
            semantic_matches=semantic_matches,
            expansion_time_ms=elapsed,
        )

    def expand_manufacturer_query(self, query: str) -> SemanticExpansionResult:
        """
        Expand a manufacturer query using semantic similarity.

        Returns similar manufacturer names to search for.
        """
        start = time.time()
        self._load_embeddings()

        expanded_terms = [query]
        semantic_matches = []

        try:
            if self._manufacturer_embeddings is not None and self._manufacturer_metadata is not None:
                query_vec = self._get_query_embedding(query)
                similar = self._find_similar(
                    query_vec,
                    self._manufacturer_embeddings,
                    self._manufacturer_metadata,
                    top_k=10,
                )

                for item in similar:
                    if item.similarity >= self.manufacturer_threshold:
                        semantic_matches.append(item)
                        if item.text.lower() not in [t.lower() for t in expanded_terms]:
                            expanded_terms.append(item.text)

        except Exception as e:
            logger.warning(f"Manufacturer expansion failed for '{query}': {e}")

        elapsed = (time.time() - start) * 1000
        return SemanticExpansionResult(
            original_query=query,
            expanded_terms=list(dict.fromkeys(expanded_terms)),
            semantic_matches=semantic_matches,
            expansion_time_ms=elapsed,
        )

    async def expand_device_query_async(self, query: str) -> SemanticExpansionResult:
        """Async version of expand_device_query."""
        import asyncio
        return await asyncio.to_thread(self.expand_device_query, query)

    async def expand_manufacturer_query_async(self, query: str) -> SemanticExpansionResult:
        """Async version of expand_manufacturer_query."""
        import asyncio
        return await asyncio.to_thread(self.expand_manufacturer_query, query)
