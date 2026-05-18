from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from aquadx.api.errors import NotFoundError, UpstreamError, UpstreamTimeoutError
from aquadx.settings import Settings, get_settings
from aquadx.utils.logging import get_logger
from aquadx.utils.ratelimit import TokenBucket

log = get_logger("aquadx.client")


def _should_retry(exc: BaseException) -> bool:
    if isinstance(
        exc, httpx.ConnectError | httpx.ReadError | httpx.WriteError | httpx.TimeoutException
    ):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return 500 <= exc.response.status_code < 600
    return False


class AquadxClient:
    """Async HTTP client around the AquaDX REST v2 API.

    Wraps httpx.AsyncClient with retries (3x exponential backoff on 5xx / connect)
    and a token-bucket rate limiter to be polite to upstream.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.settings.aquadx_base_url,
            timeout=self.settings.http_timeout_s,
        )
        self._bucket = TokenBucket(rate=self.settings.http_rps)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AquadxClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json: Any = None,
    ) -> httpx.Response:
        async def attempt() -> httpx.Response:
            await self._bucket.acquire()
            log.debug("upstream_request", method=method, path=path)
            response = await self._client.request(method, path, params=params, data=data, json=json)
            if response.status_code >= 500:
                response.raise_for_status()
            return response

        retrying = AsyncRetrying(
            reraise=False,
            retry=retry_if_exception(_should_retry),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.1, min=0.1, max=2.0),
        )
        try:
            async for attempt_ctx in retrying:
                with attempt_ctx:
                    return await attempt()
        except RetryError as e:
            last = e.last_attempt.exception()
            if isinstance(last, httpx.TimeoutException):
                raise UpstreamTimeoutError(
                    f"Upstream timed out: {method} {path}",
                    upstream_status=None,
                ) from last
            status = last.response.status_code if isinstance(last, httpx.HTTPStatusError) else None
            raise UpstreamError(
                f"Upstream failed after retries: {method} {path}",
                upstream_status=status,
            ) from last
        raise UpstreamError(
            f"Upstream call yielded no response: {method} {path}"
        )  # pragma: no cover

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = await self._request("GET", path, params=params)
        return _decode(response, path)

    async def post(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        response = await self._request("POST", path, params=params, data=data, json=json)
        return _decode(response, path)


def _decode(response: httpx.Response, path: str) -> Any:
    if response.status_code == 404:
        raise NotFoundError(
            f"Upstream not found: {path}",
            upstream_status=404,
        )
    if 400 <= response.status_code < 500:
        # Intentionally do NOT propagate the raw upstream body — it may contain
        # internal field names or partial diagnostics we should not surface to
        # API consumers. Log for ops, surface a sanitised message.
        log.warning(
            "upstream_4xx",
            method="GET",
            path=path,
            status=response.status_code,
            body=_safe_body(response),
        )
        raise UpstreamError(
            f"Upstream client error {response.status_code}: {path}",
            upstream_status=response.status_code,
        )
    try:
        return response.json()
    except ValueError:
        return response.text


def _safe_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:512]
