from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from peerbench.export.data.restatement import (
    build_restatement_log,
    derive_affected_ratios,
)


def test_derive_affected_ratios_simple_case() -> None:
    field_deps = {
        "nim": ["INTINC", "EINTEXP", "ERNAST5"],
        "roa": ["NETINC", "ASSET5"],
        "eff_ratio": ["NONIX", "EAMINTAN", "NIM", "NONII"],
    }
    affected = derive_affected_ratios("NIM", field_deps)
    assert "nim" not in affected  # NIM the ratio reads NIM-component fields, not literal 'NIM'
    assert "eff_ratio" in affected


def test_derive_affected_ratios_no_match() -> None:
    assert derive_affected_ratios("CBLRIND", {"nim": ["INTINC"]}) == []


def test_build_restatement_log_filters_to_workbook_window() -> None:
    events = [
        _make_event(
            quarter_id="2025-Q3",
            field_code="NETINC",
            cert=4063,
            old=Decimal("100"),
            new=Decimal("120"),
        ),
        _make_event(
            quarter_id="2023-Q4",
            field_code="NETINC",
            cert=4063,
            old=Decimal("100"),
            new=Decimal("120"),
        ),
    ]
    bank_names = {4063: "MidFirst"}
    field_deps = {"roa": ["NETINC", "ASSET5"]}
    window = {
        "2024-Q1",
        "2024-Q2",
        "2024-Q3",
        "2024-Q4",
        "2025-Q1",
        "2025-Q2",
        "2025-Q3",
        "2025-Q4",
    }
    tab = build_restatement_log(events, bank_names=bank_names, field_deps=field_deps, window=window)
    assert len(tab.rows) == 1
    assert tab.rows[0].quarter_id == "2025-Q3"
    assert "roa" in tab.rows[0].affected_ratios


def test_build_restatement_log_filters_to_workbook_ratios() -> None:
    events = [
        _make_event(
            quarter_id="2025-Q4",
            field_code="UNKNOWN_FIELD",
            cert=4063,
            old=Decimal("100"),
            new=Decimal("120"),
        ),
    ]
    tab = build_restatement_log(
        events,
        bank_names={4063: "MidFirst"},
        field_deps={"nim": ["INTINC"]},
        window={"2025-Q4"},
    )
    assert tab.rows == []


def test_build_restatement_log_sorts_detected_at_desc() -> None:
    events = [
        _make_event(
            quarter_id="2025-Q4",
            field_code="NETINC",
            cert=4063,
            old=Decimal("100"),
            new=Decimal("110"),
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        _make_event(
            quarter_id="2025-Q4",
            field_code="NETINC",
            cert=4063,
            old=Decimal("110"),
            new=Decimal("120"),
            detected_at=datetime(2026, 5, 1, tzinfo=UTC),
        ),
    ]
    tab = build_restatement_log(
        events,
        bank_names={4063: "MidFirst"},
        field_deps={"roa": ["NETINC"]},
        window={"2025-Q4"},
    )
    assert tab.rows[0].detected_at > tab.rows[1].detected_at


def _make_event(
    *,
    cert: int,
    quarter_id: str,
    field_code: str,
    old: Decimal | None,
    new: Decimal | None,
    detected_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "detected_at": detected_at or datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC),
        "cert": cert,
        "quarter_id": quarter_id,
        "field_code": field_code,
        "old_value": old,
        "new_value": new,
    }
