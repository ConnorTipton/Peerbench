"""FDIC client retry + rate-limit behavior under failure injection.

respx mocks at the httpx transport level. We can't test the rate limiter
through respx alone (it has no real wall-clock delay) so the rate-limit test
uses TokenBucket directly with an injected clock.
"""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
import respx

from peerbench.ingest.fdic import FDIC_API_BASE, FdicClient, FdicRetryableHTTPError
from peerbench.ingest.rate_limit import TokenBucket


@pytest.fixture
def fake_clock() -> dict[str, float]:
    return {"t": 0.0}


def make_client_with_fast_rate_limiter() -> FdicClient:
    """Real httpx Client (respx will intercept), TokenBucket pre-filled
    so acquire() returns instantly."""
    bucket = TokenBucket(rate_per_second=1000.0, capacity=1000)
    return FdicClient(api_key=None, rate_limiter=bucket)


class TestFdicRetry:
    @respx.mock
    def test_retries_on_429_until_success(self) -> None:
        responses = [
            httpx.Response(429),
            httpx.Response(429),
            httpx.Response(
                200,
                json={"data": [{"data": {"CERT": 4063, "ASSET": "41200000"}}]},
            ),
        ]
        route = respx.get(f"{FDIC_API_BASE}/financials").mock(side_effect=responses)
        with make_client_with_fast_rate_limiter() as client:
            result = client.financials(cert=4063, quarter_id="2025-Q3", fields=["CERT", "ASSET"])
        assert route.call_count == 3
        assert result["ASSET"] == Decimal("41200000")

    @respx.mock
    def test_retries_on_5xx_until_success(self) -> None:
        responses = [
            httpx.Response(503),
            httpx.Response(
                200,
                json={"data": [{"data": {"CERT": 4063, "ASSET": "1"}}]},
            ),
        ]
        route = respx.get(f"{FDIC_API_BASE}/financials").mock(side_effect=responses)
        with make_client_with_fast_rate_limiter() as client:
            client.financials(cert=4063, quarter_id="2025-Q3", fields=["ASSET"])
        assert route.call_count == 2

    @respx.mock
    def test_gives_up_after_five_attempts(self) -> None:
        route = respx.get(f"{FDIC_API_BASE}/financials").mock(return_value=httpx.Response(503))
        with make_client_with_fast_rate_limiter() as client, pytest.raises(FdicRetryableHTTPError):
            client.financials(cert=4063, quarter_id="2025-Q3", fields=["ASSET"])
        assert route.call_count == 5  # stop_after_attempt(5)

    @respx.mock
    def test_does_not_retry_on_400(self) -> None:
        route = respx.get(f"{FDIC_API_BASE}/financials").mock(
            return_value=httpx.Response(400, json={"error": "bad request"})
        )
        with make_client_with_fast_rate_limiter() as client, pytest.raises(httpx.HTTPStatusError):
            client.financials(cert=4063, quarter_id="2025-Q3", fields=["ASSET"])
        assert route.call_count == 1

    @respx.mock
    def test_value_path_is_decimal_never_float(self) -> None:
        # FDIC sometimes returns numerics as JSON numbers (no quotes).
        # If httpx.Response.json() were used, those would parse as float.
        # We use json.loads(..., parse_float=Decimal) — verify it stuck.
        respx.get(f"{FDIC_API_BASE}/financials").mock(
            return_value=httpx.Response(
                200,
                text='{"data":[{"data":{"ASSET":41200000.55}}]}',
            )
        )
        with make_client_with_fast_rate_limiter() as client:
            result = client.financials(cert=4063, quarter_id="2025-Q3", fields=["ASSET"])
        assert isinstance(result["ASSET"], Decimal)
        assert result["ASSET"] == Decimal("41200000.55")


class TestRateLimiter:
    def test_first_acquire_is_immediate(self, fake_clock: dict[str, float]) -> None:
        sleeps: list[float] = []
        bucket = TokenBucket(
            rate_per_second=5.0,
            capacity=5,
            clock=lambda: fake_clock["t"],
            sleep=lambda s: sleeps.append(s) or fake_clock.update(t=fake_clock["t"] + s),
        )
        bucket.acquire()
        assert sleeps == []

    def test_drains_then_throttles(self, fake_clock: dict[str, float]) -> None:
        sleeps: list[float] = []

        def sleep(s: float) -> None:
            sleeps.append(s)
            fake_clock["t"] += s

        bucket = TokenBucket(
            rate_per_second=5.0,
            capacity=5,
            clock=lambda: fake_clock["t"],
            sleep=sleep,
        )
        # Drain the initial bucket: 5 instant acquires.
        for _ in range(5):
            bucket.acquire()
        assert sleeps == []
        # 6th acquire needs to wait ~0.2s (1 token / 5 per second).
        bucket.acquire()
        assert sleeps
        assert sum(sleeps) == pytest.approx(0.2, abs=1e-9)

    def test_rejects_non_positive_rate(self) -> None:
        with pytest.raises(ValueError, match="rate_per_second"):
            TokenBucket(rate_per_second=0)
        with pytest.raises(ValueError, match="rate_per_second"):
            TokenBucket(rate_per_second=-1)
