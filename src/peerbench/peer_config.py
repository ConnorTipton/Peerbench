"""Peer-set loader — `data/peers.toml` is the canonical source.

Replaces the hard-coded cert list in `.github/workflows/daily-ingest.yml`
and the docs/operations.md prose with a single human-editable TOML file.
The daily cron calls `peerbench list-peers --tier 1` to enumerate the
ingest set; the dashboard query layer calls `tier1_certs()` / `tier2_certs()`
indirectly via the database (post sync-peers).

Tier-1 peers appear as head-to-head columns. Tier-2 peers contribute to a
"Larger peer median" summary only — never selectable for head-to-head
comparison (Phase 5 decision; see plan).

Exactly one peer must have `anchor = true`. Module-load fails loudly if
the TOML violates that invariant — peers.toml is hand-edited, so the cost
of a strict guard is one helpful error message at CI time.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from peerbench.config import REPO_ROOT

PEERS_TOML_PATH = REPO_ROOT / "data" / "peers.toml"


@dataclass(frozen=True, slots=True)
class Peer:
    cert: int
    name: str
    state: str | None
    peer_tier: int
    anchor: bool


def load_peers(path: Path | None = None) -> tuple[Peer, ...]:
    """Parse `data/peers.toml` and return all peers in file order.

    Raises ValueError if the file has zero anchors, more than one anchor,
    duplicate certs, or a peer_tier outside {1, 2}.
    """
    toml_path = path or PEERS_TOML_PATH
    with toml_path.open("rb") as fh:
        data: dict[str, Any] = tomllib.load(fh)
    raw_peers: list[dict[str, Any]] = list(data.get("peers") or [])
    peers: list[Peer] = []
    seen_certs: set[int] = set()
    for entry in raw_peers:
        cert = int(entry["cert"])
        if cert in seen_certs:
            msg = f"duplicate cert in {toml_path.name}: {cert}"
            raise ValueError(msg)
        seen_certs.add(cert)
        tier = int(entry["peer_tier"])
        if tier not in (1, 2):
            msg = f"peer {cert} ({entry.get('name')}) has invalid peer_tier {tier}; expected 1 or 2"
            raise ValueError(msg)
        peers.append(
            Peer(
                cert=cert,
                name=str(entry["name"]),
                state=str(entry["state"]) if "state" in entry else None,
                peer_tier=tier,
                anchor=bool(entry.get("anchor", False)),
            )
        )
    anchors = [p for p in peers if p.anchor]
    if len(anchors) != 1:
        names = ", ".join(f"{p.cert} ({p.name})" for p in anchors) or "none"
        msg = f"{toml_path.name} must declare exactly one anchor peer; found {len(anchors)}: {names}"
        raise ValueError(msg)
    return tuple(peers)


def tier1_certs(path: Path | None = None) -> tuple[int, ...]:
    """Anchor + tier-1 head-to-head peers, in file order."""
    return tuple(p.cert for p in load_peers(path) if p.peer_tier == 1)


def tier2_certs(path: Path | None = None) -> tuple[int, ...]:
    """Tier-2 distribution-only peers, in file order."""
    return tuple(p.cert for p in load_peers(path) if p.peer_tier == 2)


def all_certs(path: Path | None = None) -> tuple[int, ...]:
    """Every cert the ingest pipeline should fetch."""
    return tuple(p.cert for p in load_peers(path))


def anchor_cert(path: Path | None = None) -> int:
    """The single peer flagged anchor = true. Always MidFirst (4063) today."""
    for peer in load_peers(path):
        if peer.anchor:
            return peer.cert
    msg = "unreachable: load_peers() guarantees exactly one anchor"  # pragma: no cover
    raise RuntimeError(msg)  # pragma: no cover
