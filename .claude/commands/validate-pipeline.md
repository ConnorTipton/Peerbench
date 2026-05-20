---
description: Run the Peerbench ratio validation suite via the pipeline-validator sub-agent. Cross-checks computed ratios against FDIC pre-computed truth and verifies the restatement detector.
---

Invoke the `pipeline-validator` sub-agent to validate the Peerbench Phase 1 pipeline.

The sub-agent will:
1. Run `uv run peerbench validate` and capture output.
2. Compute per-ratio error tables (mean abs bps, max abs bps) against FDIC pre-computed values.
3. Verify the restatement detector with synthetic diffs.
4. Verify the `ratio_defs` ↔ handler contract.
5. Report PASS / FAIL with a per-ratio breakdown and any blocking issues.

Tolerance bands per `PLAN.md` Phase 1 DoD: mean abs error < 2 bps, max abs error < 5 bps.

$ARGUMENTS will be passed through to the sub-agent — use it to scope the validation (e.g., a specific ratio_id, cert, or quarter_id) or to leave blank for a full run.
