"""Unit tests for the peers.toml loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from peerbench.peer_config import (
    PEERS_TOML_PATH,
    all_certs,
    anchor_cert,
    load_peers,
    tier1_certs,
    tier2_certs,
)


def test_canonical_peers_toml_parses() -> None:
    """The shipped data/peers.toml must always load without raising."""
    peers = load_peers()
    assert len(peers) >= 5  # at minimum the pre-Phase-5 set


def test_anchor_is_midfirst() -> None:
    """MidFirst (cert 4063) is the project anchor; never silently swap it."""
    assert anchor_cert() == 4063


def test_tier_partition_covers_all_peers() -> None:
    assert sorted(all_certs()) == sorted(tier1_certs() + tier2_certs())


def test_tier2_disjoint_from_tier1() -> None:
    assert set(tier1_certs()).isdisjoint(set(tier2_certs()))


def test_anchor_is_in_tier1() -> None:
    """Tier-2 is distribution-only; the anchor would lose its head-to-head
    column if it landed there."""
    assert anchor_cert() in tier1_certs()


def test_rejects_zero_anchors(tmp_path: Path) -> None:
    p = tmp_path / "no_anchor.toml"
    p.write_text(
        '[[peers]]\ncert = 1\nname = "A"\npeer_tier = 1\n'
        '[[peers]]\ncert = 2\nname = "B"\npeer_tier = 2\n'
    )
    with pytest.raises(ValueError, match="anchor"):
        load_peers(p)


def test_rejects_multiple_anchors(tmp_path: Path) -> None:
    p = tmp_path / "two_anchors.toml"
    p.write_text(
        '[[peers]]\ncert = 1\nname = "A"\npeer_tier = 1\nanchor = true\n'
        '[[peers]]\ncert = 2\nname = "B"\npeer_tier = 1\nanchor = true\n'
    )
    with pytest.raises(ValueError, match="anchor"):
        load_peers(p)


def test_rejects_duplicate_cert(tmp_path: Path) -> None:
    p = tmp_path / "dup.toml"
    p.write_text(
        '[[peers]]\ncert = 1\nname = "A"\npeer_tier = 1\nanchor = true\n'
        '[[peers]]\ncert = 1\nname = "Dup"\npeer_tier = 1\n'
    )
    with pytest.raises(ValueError, match="duplicate cert"):
        load_peers(p)


def test_rejects_invalid_tier(tmp_path: Path) -> None:
    p = tmp_path / "bad_tier.toml"
    p.write_text(
        '[[peers]]\ncert = 1\nname = "A"\npeer_tier = 1\nanchor = true\n'
        '[[peers]]\ncert = 2\nname = "B"\npeer_tier = 3\n'
    )
    with pytest.raises(ValueError, match="peer_tier"):
        load_peers(p)


def test_load_order_preserved() -> None:
    """File order matters — it controls dashboard column ordering."""
    peers = load_peers()
    certs_in_file_order = [p.cert for p in peers]
    assert certs_in_file_order[0] == 4063, "anchor must be first row"


def test_peers_toml_exists_at_canonical_path() -> None:
    assert PEERS_TOML_PATH.exists(), f"missing canonical peers file: {PEERS_TOML_PATH}"
