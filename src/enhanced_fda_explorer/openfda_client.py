"""
Shared OpenFDA HTTP client with retry/backoff and pagination helpers.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import httpx

from .config import get_config

logger = logging.getLogger("openfda.client")


@dataclass
class AggregationResult:
    """Result of an aggregation query with metadata."""
    field: str
    counts: List[Dict[str, Any]]
    source: str  # "server" or "client"
    records_aggregated: int
    total_available: int

    @property
    def is_complete(self) -> bool:
        return self.records_aggregated >= self.total_available


@dataclass
class HybridAggregationResult:
    """Combined results from hybrid aggregation."""
    aggregations: Dict[str, List[Dict[str, Any]]]
    source: str  # "server", "client", or "mixed"
    records_aggregated: int
    total_available: int
    field_sources: Dict[str, str] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return self.records_aggregated >= self.total_available

    def get_label(self) -> str:
        if self.source == "server":
            return f"all {self.total_available} records"
        elif self.records_aggregated >= self.total_available:
            return f"all {self.total_available} records"
        else:
            return f"{self.records_aggregated} of {self.total_available} records"


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

    def get_count(
        self,
        path: str,
        search: str,
        count_field: str,
        limit: int = 100,
    ) -> list[Dict[str, Any]]:
        """Fetch aggregated counts for a field.

        Returns list of {"term": "value", "count": N} dicts.
        """
        params = {"search": search, "count": count_field, "limit": limit}
        data, _ = self._request_sync(path, params=params)
        return data.get("results", [])

    async def aget_count(
        self,
        path: str,
        search: str,
        count_field: str,
        limit: int = 100,
    ) -> list[Dict[str, Any]]:
        """Async version of get_count."""
        params = {"search": search, "count": count_field, "limit": limit}
        data, _ = await self._request_async(path, params=params)
        return data.get("results", [])

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

    async def aget_hybrid_aggregations(
        self,
        endpoint: str,
        search: str,
        server_count_fields: List[str],
        client_field_extractors: Dict[str, Callable[[Dict], Optional[str]]],
        max_client_records: int = 5000,
        page_size: int = 1000,
    ) -> HybridAggregationResult:
        """
        Fetch aggregations using server-side count queries when available,
        falling back to client-side aggregation for fields that don't support count.

        Args:
            endpoint: API endpoint (e.g., "device/recall.json")
            search: Search query string
            server_count_fields: Fields to try with server-side count (e.g., ["status.exact"])
            client_field_extractors: Dict mapping field names to extractor functions
                                     for client-side aggregation
            max_client_records: Maximum records to fetch for client-side aggregation
            page_size: Records per page (max 1000 per API limit)

        Returns:
            HybridAggregationResult with aggregations, source info, and coverage stats
        """
        aggregations: Dict[str, List[Dict[str, Any]]] = {}
        field_sources: Dict[str, str] = {}
        server_succeeded = []
        server_failed = []

        total_available = await self._get_total_count(endpoint, search)
        if total_available == 0:
            return HybridAggregationResult(
                aggregations={},
                source="server",
                records_aggregated=0,
                total_available=0,
                field_sources={},
            )

        async def try_server_count(field: str) -> tuple[str, List[Dict], bool]:
            try:
                results = await self.aget_count(endpoint, search, field, limit=100)
                if results:
                    return field, results, True
                return field, [], False
            except Exception as e:
                logger.debug(f"Server-side count failed for {field}: {e}")
                return field, [], False

        server_tasks = [try_server_count(f) for f in server_count_fields]
        server_results = await asyncio.gather(*server_tasks)

        for field, counts, success in server_results:
            if success and counts:
                aggregations[field] = counts
                field_sources[field] = "server"
                server_succeeded.append(field)
            else:
                server_failed.append(field)

        needs_client_side = bool(server_failed) or any(
            f not in server_count_fields for f in client_field_extractors
        )

        if needs_client_side and client_field_extractors:
            records_to_fetch = min(max_client_records, total_available)
            records = await self._fetch_records_parallel(
                endpoint, search, records_to_fetch, page_size
            )

            for field_name, extractor in client_field_extractors.items():
                if field_name in aggregations:
                    continue
                counter: Counter = Counter()
                for record in records:
                    try:
                        value = extractor(record)
                        if value:
                            counter[value] += 1
                    except Exception:
                        pass

                aggregations[field_name] = [
                    {"term": term, "count": count}
                    for term, count in counter.most_common(100)
                ]
                field_sources[field_name] = "client"

            records_aggregated = len(records)
        else:
            records_aggregated = total_available

        if all(s == "server" for s in field_sources.values()):
            source = "server"
            records_aggregated = total_available
        elif all(s == "client" for s in field_sources.values()):
            source = "client"
        else:
            source = "mixed"

        return HybridAggregationResult(
            aggregations=aggregations,
            source=source,
            records_aggregated=records_aggregated,
            total_available=total_available,
            field_sources=field_sources,
        )

    async def _get_total_count(self, endpoint: str, search: str) -> int:
        try:
            data, _ = await self._request_async(
                endpoint, params={"search": search, "limit": 1}
            )
            return data.get("meta", {}).get("results", {}).get("total", 0)
        except Exception:
            return 0

    async def _fetch_records_parallel(
        self,
        endpoint: str,
        search: str,
        max_records: int,
        page_size: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Fetch records in parallel pages."""
        page_size = min(page_size, 1000)
        num_pages = (max_records + page_size - 1) // page_size

        async def fetch_page(page_num: int) -> List[Dict]:
            skip = page_num * page_size
            remaining = max_records - skip
            limit = min(page_size, remaining)
            if limit <= 0:
                return []
            try:
                data, _ = await self._request_async(
                    endpoint,
                    params={"search": search, "limit": limit, "skip": skip},
                )
                return data.get("results", []) or []
            except Exception as e:
                logger.warning(f"Failed to fetch page {page_num}: {e}")
                return []

        tasks = [fetch_page(i) for i in range(num_pages)]
        page_results = await asyncio.gather(*tasks)

        all_records = []
        for page in page_results:
            all_records.extend(page)
        return all_records[:max_records]
