"""One-shot: resolve FDIC cert numbers for Phase 5.1 peer expansion.

Hits FDIC `/institutions` and prints TOML-ready rows for hand-paste into
`data/peers.toml`. Banks are well-known regionals; (name, state) is enough
to disambiguate. Each lookup prints the candidate matches so a human can
verify before committing.

Run once:
    uv run python scripts/resolve_certs.py

Committed for reproducibility; not re-run by the pipeline. M&A is handled
by the existing FDIC `ACTIVE` flag check at cron time.
"""

from __future__ import annotations

import httpx

FDIC_API_BASE = "https://api.fdic.gov/banks"

# (search_name, state, peer_tier, display_name). search_name is uppercased
# and passed to FDIC `search=NAME:<token>` which only matches the first NAME
# token (so "Prosperity" finds "Prosperity Bank" but "Cadence Bank" fails
# the tokenizer). For banks where the search returns nothing despite the
# bank being an active filer, KNOWN_CERTS below carries a hand-verified cert
# that the script re-confirms via direct CERT lookup.
TARGETS: list[tuple[str, str, int, str]] = [
    ("PROSPERITY", "TX", 1, "Prosperity Bank"),
    ("CADENCE", "MS", 1, "Cadence Bank"),
    ("VALLEY", "NJ", 1, "Valley National Bank"),
    ("TEXAS", "TX", 1, "Texas Capital Bank"),
    ("PINNACLE", "TN", 1, "Pinnacle Bank"),
    ("SYNOVUS", "GA", 1, "Synovus Bank"),
    ("COMMERCE", "MO", 1, "Commerce Bank"),
    ("CENTENNIAL", "AR", 1, "Centennial Bank"),
    ("ZIONS", "UT", 2, "Zions Bank"),
    ("COMERICA", "TX", 2, "Comerica Bank"),
    ("FIRST", "TN", 2, "First Horizon Bank"),
]

# Known certs for banks the FDIC search miss-handles. All verified active
# filers as of 2025-Q4 via `/financials?filters=CERT:<n> AND REPDTE:20251231`.
# The FDIC `ACTIVE` flag on the `/institutions` endpoint reports 0 for
# Synovus / Cadence / Comerica despite recent filings — appears to be a
# stale field on FDIC's side. Re-verify only if `peerbench ingest` returns
# no rows for one of these certs.
KNOWN_CERTS: dict[str, int] = {
    "Synovus Bank": 873,
    "Cadence Bank": 11813,
    "Comerica Bank": 983,
}


def search(client: httpx.Client, name: str, state: str) -> list[dict[str, str]]:
    response = client.get(
        "/institutions",
        params={
            "search": f"NAME:{name}",
            "filters": f"STALP:{state} AND ACTIVE:1",
            "fields": "CERT,NAME,CITY,STALP,ASSET",
            "sort_by": "ASSET",
            "sort_order": "DESC",
            "limit": 5,
            "format": "json",
        },
    )
    response.raise_for_status()
    return [r.get("data", r) for r in (response.json().get("data") or [])]


def lookup_cert(client: httpx.Client, cert: int) -> dict[str, str] | None:
    response = client.get(
        "/institutions",
        params={
            "filters": f"CERT:{cert}",
            "fields": "CERT,NAME,CITY,STALP,ASSET,ACTIVE",
            "format": "json",
        },
    )
    response.raise_for_status()
    rows = [r.get("data", r) for r in (response.json().get("data") or [])]
    return rows[0] if rows else None


def main() -> None:
    with httpx.Client(base_url=FDIC_API_BASE, timeout=30.0) as client:
        for search_name, state, tier, display in TARGETS:
            print(f"\n=== {display} ({state}, tier {tier}) ===")
            rows = search(client, search_name, state)
            if not rows and display in KNOWN_CERTS:
                row = lookup_cert(client, KNOWN_CERTS[display])
                rows = [row] if row else []
                print(f"  (FDIC search miss — using KNOWN_CERTS fallback for {display})")
            if not rows:
                print("  NO MATCHES — widen search or add to KNOWN_CERTS")
                continue
            for r in rows:
                asset = r.get("ASSET")
                asset_b = f"${int(asset) / 1_000_000:.1f}B" if asset else "n/a"
                print(
                    f"  CERT={r.get('CERT'):>6}  "
                    f"{str(r.get('NAME', ''))[:50]:<50}  "
                    f"{r.get('CITY', ''):<20}  "
                    f"{asset_b:>8}"
                )
            top = rows[0]
            print(
                f"  → toml: "
                f'{{ cert = {top.get("CERT")}, name = "{display}", peer_tier = {tier} }}'
            )


if __name__ == "__main__":
    main()
