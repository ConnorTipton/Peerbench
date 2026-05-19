"""FDIC BankFind Suite API client.

Sync httpx + tenacity retries on 429 / 5xx / transport errors with jittered
exponential backoff. 5 req/s rate limit via a shared TokenBucket. Bearer
auth header when `FDIC_API_KEY` is set (optional; the public API works
without a key but at lower rate limits).

JSON parsing forces Decimal everywhere — no float in the value path.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from peerbench.config import get_settings
from peerbench.ingest.rate_limit import TokenBucket

FDIC_API_BASE = "https://api.fdic.gov/banks"
DEFAULT_RATE_PER_SEC = 5.0
DEFAULT_TIMEOUT_SEC = 30.0

logger = logging.getLogger(__name__)


class FdicRetryableHTTPError(Exception):
    """Raised on 429/5xx — signals tenacity to retry."""


def _quarter_id_to_repdte(quarter_id: str) -> str:
    """'2025-Q3' -> '20250930' for the FDIC REPDTE filter."""
    year_str, q_str = quarter_id.split("-Q")
    year = int(year_str)
    quarter = int(q_str)
    last_day = {1: "0331", 2: "0630", 3: "0930", 4: "1231"}[quarter]
    return f"{year}{last_day}"


def _env_fdic_api_key() -> str | None:
    """Best-effort env lookup. FDIC API works anonymously, so a missing env
    file (CI, FDIC-only callers) must not crash construction."""
    try:
        return get_settings().fdic_api_key
    except Exception:
        return None


class FdicClient:
    def __init__(
        self,
        api_key: str | None = None,
        rate_limiter: TokenBucket | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else _env_fdic_api_key()
        self._rate_limiter = rate_limiter or TokenBucket(DEFAULT_RATE_PER_SEC)
        self._client = client or httpx.Client(
            base_url=FDIC_API_BASE,
            timeout=DEFAULT_TIMEOUT_SEC,
            headers=self._auth_headers(),
        )

    def _auth_headers(self) -> dict[str, str]:
        if not self._api_key:
            return {}
        return {"Authorization": f"Bearer {self._api_key}"}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> FdicClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @retry(
        retry=retry_if_exception_type((FdicRetryableHTTPError, httpx.TransportError)),
        stop=stop_after_attempt(5),
        wait=wait_random_exponential(multiplier=0.5, min=0.5, max=8.0),
        reraise=True,
    )
    def _get(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        self._rate_limiter.acquire()
        response = self._client.get(path, params=params)
        if response.status_code in {429, 500, 502, 503, 504}:
            logger.warning(
                "FDIC %s %s -> %s, will retry",
                path,
                params,
                response.status_code,
            )
            raise FdicRetryableHTTPError(f"{response.status_code} from FDIC")
        response.raise_for_status()
        # parse_float=Decimal — never let a float into the value path.
        return json.loads(response.text, parse_float=Decimal)

    def financials(
        self,
        cert: int,
        quarter_id: str,
        fields: list[str],
    ) -> dict[str, Decimal | None]:
        """Fetch one bank-quarter slice; return {field_code: Decimal | None}."""
        repdte = _quarter_id_to_repdte(quarter_id)
        params: dict[str, str | int] = {
            "filters": f"CERT:{cert} AND REPDTE:{repdte}",
            "fields": ",".join(fields),
            "limit": 1,
            "format": "json",
        }
        payload = self._get("/financials", params)
        records = payload.get("data") or []
        if not records:
            return {f: None for f in fields}
        row = records[0].get("data") or records[0]
        out: dict[str, Decimal | None] = {}
        for f in fields:
            v = row.get(f)
            if v is None or v == "":
                out[f] = None
            elif isinstance(v, Decimal):
                out[f] = v
            elif isinstance(v, int):
                out[f] = Decimal(v)
            elif isinstance(v, str):
                # Some FDIC values come back as strings ("0", "12345.67"); some
                # are non-numeric (e.g. NAMEFULL). Try Decimal; bail to None.
                try:
                    out[f] = Decimal(v)
                except (ValueError, ArithmeticError):
                    out[f] = None
            else:
                # Float would land here — refuse rather than silently coerce.
                msg = f"unexpected type {type(v).__name__} for field {f}: {v!r}"
                raise TypeError(msg)
        return out

    def institution_active(self, cert: int) -> bool:
        """Cheap check used at peer-list lock time to fail on M&A flips."""
        payload = self._get(
            "/institutions",
            {"filters": f"CERT:{cert}", "fields": "CERT,ACTIVE", "limit": 1, "format": "json"},
        )
        records = payload.get("data") or []
        if not records:
            return False
        row = records[0].get("data") or records[0]
        return str(row.get("ACTIVE", "0")) == "1"
