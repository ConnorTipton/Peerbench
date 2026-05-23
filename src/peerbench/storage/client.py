"""Thin httpx wrapper around the Supabase Storage REST API."""

from __future__ import annotations

import httpx


class SupabaseStorageClient:
    """Single-purpose client: upload a file to a public Supabase Storage bucket.

    We use httpx directly (already a project dep) instead of supabase-py to
    avoid pulling in 5 transitive deps for one PUT call per day.
    """

    def __init__(self, *, url: str, service_role_key: str) -> None:
        self._url = url.rstrip("/")
        self._key = service_role_key

    def upload(self, bucket: str, path: str, body: bytes, content_type: str) -> None:
        """PUT `body` to `<bucket>/<path>` with upsert semantics.

        Raises RuntimeError on non-2xx (with response body in the message).
        Propagates httpx network errors (ConnectError, TimeoutException) to
        the caller — the daily cron treats both as "fail loud, retry tomorrow."
        """
        endpoint = f"{self._url}/storage/v1/object/{bucket}/{path}"
        headers = {
            "Authorization": f"Bearer {self._key}",
            "apikey": self._key,
            "x-upsert": "true",
            "Content-Type": content_type,
        }
        with httpx.Client(timeout=30.0) as http:
            resp = http.put(endpoint, content=body, headers=headers)
        if resp.status_code >= 300:
            raise RuntimeError(f"Supabase Storage upload failed: {resp.status_code} {resp.text}")
