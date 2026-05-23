"""Phase 4.2 — Excel comp workbook export.

Pure-function builders emit typed payloads; a single writer module owns
openpyxl. No formula logic in this layer — values are read from `ratios`
and raw line items from `facts`. See
docs/superpowers/specs/2026-05-23-excel-export-design.md.
"""

from peerbench.export.workbook import run_export

__all__ = ["run_export"]
