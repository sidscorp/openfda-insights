"""
Shared OpenFDA HTTP client with retry/backoff and pagination helpers.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

import httpx

from .config import get_config

logger = logging.getLogger("openfda.client")


class OpenFDAClient:
    """HTTP client wrapper for OpenFDA with retry/backoff and pagination."""

    RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        rate_limit_delay: Optional[float] = None,
        user_agent: Optional[str] = None,
        sync_transport: Optional[httpx.BaseTransport] = None,
        async_transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        config = get_config()
        openfda_cfg = config.openfda

        self.base_url = base_url or openfda_cfg.base_url
        self.api_key = api_key if api_key is not None else openfda_cfg.api_key
        self.timeout = timeout if timeout is not None else openfda_cfg.timeout
        self.max_retries = max_retries if max_retries is not None else openfda_cfg.max_retries
        self.rate_limit_delay = rate_limit_delay if rate_limit_delay is not None else openfda_cfg.rate_limit_delay
        self.headers = {"User-Agent": user_agent or openfda_cfg.user_agent}

        # Optional transports are provided for testing (httpx.MockTransport).
        self._sync_transport = sync_transport
        self._async_transport = async_transport

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, sort: Optional[str] = None) -> Dict[str, Any]:
        """Perform a single GET request."""
        data, _ = self._request_sync(path, params=params or {}, sort=sort)
        return data

    def get_paginated(
        self,
        path: str,
        params: Optional[Dict[str, Any]],
        limit: int,
        sort: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Fetch results across pages up to the requested limit (capped at 100 per call).
        Returns combined results with original meta preserved from the first response.
        """
        effective_limit = max(1, limit)
        page_size = max(1, min(page_size, 100))
        collected = []
        meta = {}

        offset = 0
        while len(collected) < effective_limit:
            chunk = min(page_size, effective_limit - len(collected))
            page_params = dict(params or {})
            page_params["limit"] = chunk
            if offset:
                page_params["skip"] = offset

            data, elapsed_ms = self._request_sync(path, params=page_params, sort=sort)
            meta = meta or data.get("meta", {})
            results = data.get("results", []) or []
            collected.extend(results)

            logger.debug(
                "Fetched %s results (offset=%s chunk=%s) from %s in %.1fms",
                len(results),
                offset,
                chunk,
                path,
                elapsed_ms,
            )

            if not results or len(results) < chunk:
                break

            offset += chunk

        data = {"results": collected, "meta": meta}
        return data

    async def aget(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async GET request."""
        data, _ = await self._request_async(path, params=params or {}, sort=sort)
        return data

    async def aget_paginated(
        self,
        path: str,
        params: Optional[Dict[str, Any]],
        limit: int,
        sort: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Async pagination helper mirroring get_paginated."""
        effective_limit = max(1, limit)
        page_size = max(1, min(page_size, 100))
        collected = []
        meta = {}

        offset = 0
        while len(collected) < effective_limit:
            chunk = min(page_size, effective_limit - len(collected))
            page_params = dict(params or {})
            page_params["limit"] = chunk
            if offset:
                page_params["skip"] = offset

            data, elapsed_ms = await self._request_async(path, params=page_params, sort=sort)
            meta = meta or data.get("meta", {})
            results = data.get("results", []) or []
            if results is None:
                logger.error(f"Results is None from API response: {data}")
                results = []
            collected.extend(results)

            logger.debug(
                "Fetched %s results (offset=%s chunk=%s) from %s in %.1fms",
                len(results),
                offset,
                chunk,
                path,
                elapsed_ms,
            )

            if not results or len(results) < chunk:
                break

            offset += chunk

        data = {"results": collected, "meta": meta}
        return data

    def _request_sync(
        self,
        path: str,
        params: Dict[str, Any],
        sort: Optional[str] = None,
    ) -> tuple[Dict[str, Any], float]:
        """Sync request with retry/backoff."""
        prepared_params = self._prepare_params(params, sort)
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                start = time.perf_counter()
                with httpx.Client(
                    base_url=self.base_url,
                    timeout=self.timeout,
                    headers=self.headers,
                    transport=self._sync_transport,
                ) as client:
                    response = client.get(path, params=prepared_params)

                if self._should_retry(response.status_code, attempt):
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Retrying %s (status=%s, attempt=%s, delay=%.2fs)",
                        path,
                        response.status_code,
                        attempt + 1,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                response.raise_for_status()
                elapsed_ms = (time.perf_counter() - start) * 1000
                return response.json(), elapsed_ms

            except httpx.HTTPStatusError as exc:
                last_error = exc
                if self._should_retry(exc.response.status_code, attempt):
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Retrying %s after HTTP error (status=%s, attempt=%s, delay=%.2fs)",
                        path,
                        exc.response.status_code,
                        attempt + 1,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Retrying %s after error: %s (attempt=%s, delay=%.2fs)",
                        path,
                        exc,
                        attempt + 1,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise

        # Should never reach here due to raise in loop; keep guard for completeness.
        raise last_error or RuntimeError("OpenFDA request failed without specific error")

    async def _request_async(
        self,
        path: str,
        params: Dict[str, Any],
        sort: Optional[str] = None,
    ) -> tuple[Dict[str, Any], float]:
        """Async request with retry/backoff."""
        prepared_params = self._prepare_params(params, sort)
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                start = time.perf_counter()
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=self.timeout,
                    headers=self.headers,
                    transport=self._async_transport,
                ) as client:
                    response = await client.get(path, params=prepared_params)

                if self._should_retry(response.status_code, attempt):
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Retrying %s (status=%s, attempt=%s, delay=%.2fs)",
                        path,
                        response.status_code,
                        attempt + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()
                elapsed_ms = (time.perf_counter() - start) * 1000
                return response.json(), elapsed_ms

            except httpx.HTTPStatusError as exc:
                last_error = exc
                if self._should_retry(exc.response.status_code, attempt):
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Retrying %s after HTTP error (status=%s, attempt=%s, delay=%.2fs)",
                        path,
                        exc.response.status_code,
                        attempt + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Retrying %s after error: %s (attempt=%s, delay=%.2fs)",
                        path,
                        exc,
                        attempt + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        raise last_error or RuntimeError("OpenFDA request failed without specific error")

    def _prepare_params(self, params: Dict[str, Any], sort: Optional[str]) -> Dict[str, Any]:
        prepared = dict(params or {})
        if sort:
            prepared["sort"] = sort
        if self.api_key:
            prepared.setdefault("api_key", self.api_key)
        return prepared

    def _should_retry(self, status_code: int, attempt: int) -> bool:
        return status_code in self.RETRY_STATUS_CODES and attempt < self.max_retries

    def _backoff_delay(self, attempt: int) -> float:
        # Exponential backoff capped by the configured rate_limit_delay multiplier.
        return self.rate_limit_delay * (2**attempt)
