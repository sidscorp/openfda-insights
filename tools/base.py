"""
Base HTTP client for openFDA API with retry, backoff, and rate limiting.

Rationale: Centralize retry logic and rate-limit handling (429) per openFDA guidance;
all endpoint tools inherit consistent behavior.
"""
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from pydantic import BaseModel, Field


class OpenFDAResponse(BaseModel):
    """Standardized response wrapper for all openFDA queries."""

    meta: Dict[str, Any] = Field(description="Metadata including result count and last_updated")
    results: list[Dict[str, Any]] = Field(default_factory=list, description="Result array")
    error: Optional[Dict[str, Any]] = Field(default=None, description="Error object if request failed")


class OpenFDAClient:
    """
    HTTP client for openFDA API with automatic retry on 429 and 5xx.

    Implements exponential backoff (1s, 2s, 4s) for rate limits.
    """

    BASE_URL = "https://api.fda.gov/device"
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 1.0  # seconds

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize client.

        Args:
            api_key: Optional openFDA API key for higher rate limits (1000/min vs 240/min).
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "openfda-agent/1.0"})

    def _build_url(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Construct full URL with query params."""
        if self.api_key:
            params["api_key"] = self.api_key
        query = urlencode({k: v for k, v in params.items() if v is not None})
        return f"{self.BASE_URL}/{endpoint}.json?{query}"

    def query(
        self,
        endpoint: str,
        search: Optional[str] = None,
        count: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> OpenFDAResponse:
        """
        Execute openFDA query with retry logic.

        Args:
            endpoint: API endpoint path (e.g., "registrationlisting", "510k")
            search: Lucene query string (e.g., "device_class:2")
            count: Field to count by (mutually exclusive with search results)
            limit: Max records to return (1–1000)
            skip: Pagination offset

        Returns:
            OpenFDAResponse with results or error

        Raises:
            requests.RequestException: On non-retryable failure
        """
        params: Dict[str, Any] = {"limit": limit, "skip": skip}
        if search:
            params["search"] = search
        if count:
            params["count"] = count

        url = self._build_url(endpoint, params)

        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self.session.get(url, timeout=30)

                # Retry on rate limit or server error
                if resp.status_code == 429 or resp.status_code >= 500:
                    if attempt < self.MAX_RETRIES - 1:
                        backoff = self.BACKOFF_FACTOR * (2**attempt)
                        time.sleep(backoff)
                        continue
                    # Final attempt failed
                    return OpenFDAResponse(
                        meta={},
                        results=[],
                        error={"code": resp.status_code, "message": resp.text},
                    )

                # Client error (4xx except 429)
                if 400 <= resp.status_code < 500:
                    return OpenFDAResponse(
                        meta={},
                        results=[],
                        error={"code": resp.status_code, "message": resp.text},
                    )

                # Success
                data = resp.json()
                return OpenFDAResponse(
                    meta=data.get("meta", {}),
                    results=data.get("results", []),
                )

            except requests.RequestException as e:
                if attempt < self.MAX_RETRIES - 1:
                    backoff = self.BACKOFF_FACTOR * (2**attempt)
                    time.sleep(backoff)
                    continue
                raise

        # Should not reach here
        return OpenFDAResponse(
            meta={}, results=[], error={"code": "unknown", "message": "Max retries exceeded"}
        )
