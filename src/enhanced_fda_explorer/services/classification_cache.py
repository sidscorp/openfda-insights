"""
Classification Cache - Maps product codes to device classes.

Loads a static JSON lookup at startup for fast device class lookups.
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("fda_agent.classification_cache")


class ClassificationCache:
    """Cache mapping product_code → device_class (1, 2, or 3)."""

    _cache: dict[str, str] = {}
    _loaded: bool = False

    @classmethod
    def load(cls, cache_file: Optional[Path] = None) -> int:
        """Load cache from JSON file. Returns number of entries loaded."""
        if cache_file is None:
            cache_file = Path(__file__).parent.parent.parent.parent / "data" / "product_code_classes.json"

        if not cache_file.exists():
            logger.warning(f"Classification cache file not found: {cache_file}")
            cls._cache = {}
            cls._loaded = True
            return 0

        try:
            cls._cache = json.loads(cache_file.read_text())
            cls._loaded = True
            logger.info(f"Loaded {len(cls._cache)} product code classifications")
            return len(cls._cache)
        except Exception as e:
            logger.error(f"Failed to load classification cache: {e}")
            cls._cache = {}
            cls._loaded = True
            return 0

    @classmethod
    def get_device_class(cls, product_code: str) -> Optional[str]:
        """Get device class for a product code, return None if unknown."""
        if not cls._loaded:
            cls.load()
        return cls._cache.get(product_code.upper())

    @classmethod
    def get_batch(cls, codes: list[str]) -> dict[str, Optional[str]]:
        """Get device classes for multiple codes at once."""
        if not cls._loaded:
            cls.load()
        return {code: cls._cache.get(code.upper()) for code in codes}

    @classmethod
    def size(cls) -> int:
        """Return number of entries in cache."""
        return len(cls._cache)

    @classmethod
    def is_loaded(cls) -> bool:
        """Check if cache has been loaded."""
        return cls._loaded
