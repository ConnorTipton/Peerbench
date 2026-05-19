"""Profitability ratios: nim, roa, roe, eff_ratio, ppnr_assets.

YTD income-statement-derived ratios are annualized via FactView.annualize_factor():
Q1*4, Q2*2, Q3*4/3, Q4*1. Denominators are 5-period YTD averages per the
FDIC convention (ASSET5, EQ5, ERNAST5 if available; otherwise computed).
"""

from __future__ import annotations

from decimal import Decimal

from peerbench.ratio_engine.fact_view import FactView
from peerbench.ratio_engine.registry import ratio


@ratio("nim", version="v1")
def compute_nim(f: FactView) -> Decimal:
    # Net interest margin = NIM (YTD $) × annualize / average earning assets.
    # Use FDIC's precomputed ERNAST5 when available; the field is itself the
    # 5-period YTD average. Non-tax-equivalent — UBPR NIM is TE.
    return f["NIM"] * f.annualize_factor() / f["ERNAST5"]


@ratio("roa", version="v1")
def compute_roa(f: FactView) -> Decimal:
    # Return on assets = NETINC × annualize / ASSET5 (5-period avg).
    return f["NETINC"] * f.annualize_factor() / f["ASSET5"]


@ratio("roe", version="v1")
def compute_roe(f: FactView) -> Decimal:
    # Return on equity = NETINC × annualize / EQ5 (5-period avg equity).
    # FDIC returns NA if retained earnings are negative; we'll surface that
    # as DivisionByZero -> PartialResult upstream.
    return f["NETINC"] * f.annualize_factor() / f["EQ5"]


@ratio("eff_ratio", version="v1")
def compute_eff_ratio(f: FactView) -> Decimal:
    # Efficiency = NONIX / (NIM + NONII). FDIC's EEFFR subtracts amortization
    # of intangibles from NONIX in the numerator; ours uses raw NONIX, so
    # expect a small upward bias vs EEFFR. Documented in Day 4 validation.
    return f["NONIX"] / (f["NIM"] + f["NONII"])


@ratio("ppnr_assets", version="v1")
def compute_ppnr_assets(f: FactView) -> Decimal:
    # PPNR / avg assets = (NIM + NONII - NONIX) × annualize / ASSET5.
    return (f["NIM"] + f["NONII"] - f["NONIX"]) * f.annualize_factor() / f["ASSET5"]
