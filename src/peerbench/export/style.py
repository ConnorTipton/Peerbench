"""openpyxl style constants. Centralized so a Phase 4.3 design pass can re-tune the palette in one place."""

from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

# --- Colors --------------------------------------------------------------

INPUT_BLUE = "1E40AF"
HARDCODED_GREEN = "16A34A"

HEADER_FILL_HEX = "0F172A"
HEADER_FONT_HEX = "FFFFFF"
SECTION_HEADER_FILL_HEX = "F1F5F9"

ANCHOR_TINT_HEX = "E8EEF7"
QUARTILE_TOP_HEX = "E6F4EA"
QUARTILE_BOTTOM_HEX = "FCE8E6"
THRESHOLD_AMBER_HEX = "FEF7E0"
THRESHOLD_RED_HEX = "FBD5D1"

# --- Number formats ------------------------------------------------------

NUMFMT_PERCENT = "0.00%;(0.00%)"
NUMFMT_CURRENCY = "$#,##0;($#,##0)"
NUMFMT_INTEGER = "#,##0;(#,##0)"

# --- Fonts ---------------------------------------------------------------

FONT_BODY = Font(name="Calibri", size=11)
FONT_BODY_BOLD = Font(name="Calibri", size=11, bold=True)
FONT_HEADER = Font(name="Calibri", size=11, bold=True, color=HEADER_FONT_HEX)
FONT_SECTION_HEADER = Font(name="Calibri", size=11, bold=True)
FONT_TITLE = Font(name="Calibri", size=24, bold=True)
FONT_RATIO_NAME = Font(name="Calibri", size=14, bold=True)
FONT_FORMULA_ITALIC = Font(name="Calibri", size=10, italic=True, color="64748B")

# --- Fills ---------------------------------------------------------------

FILL_HEADER = PatternFill(fill_type="solid", fgColor=HEADER_FILL_HEX)
FILL_SECTION_HEADER = PatternFill(fill_type="solid", fgColor=SECTION_HEADER_FILL_HEX)
FILL_ANCHOR = PatternFill(fill_type="solid", fgColor=ANCHOR_TINT_HEX)
FILL_QUARTILE_TOP = PatternFill(fill_type="solid", fgColor=QUARTILE_TOP_HEX)
FILL_QUARTILE_BOTTOM = PatternFill(fill_type="solid", fgColor=QUARTILE_BOTTOM_HEX)
FILL_THRESHOLD_AMBER = PatternFill(fill_type="solid", fgColor=THRESHOLD_AMBER_HEX)
FILL_THRESHOLD_RED = PatternFill(fill_type="solid", fgColor=THRESHOLD_RED_HEX)

# --- Borders -------------------------------------------------------------

THIN_GRAY = Side(border_style="thin", color="CBD5E1")
BORDER_CELL = Border(left=THIN_GRAY, right=THIN_GRAY, top=THIN_GRAY, bottom=THIN_GRAY)

# --- Alignments ----------------------------------------------------------

ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")
ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
