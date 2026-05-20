---
description: Adversarial pre-commit code review via the `reviewer` sub-agent. Catches Peerbench-specific architecture violations (inline formulas in dashboard/export, ALLL nomenclature, ratio_defs↔handler contract breaks, snake_case violations, hardcoded design tokens, restatement detector bypasses).
---

Invoke the `reviewer` sub-agent on the current diff.

The sub-agent will:
1. Read `CLAUDE.md` and `PLAN.md` for current conventions.
2. Inspect the uncommitted diff (both staged and unstaged) via `git diff` and `git diff --cached`.
3. Report blocking issues and soft signals in the format:
   - `## Blocking issues` — violations that must be fixed before commit (with file:line, why, and a concrete fix).
   - `## Soft issues` — items worth a second look (with reasoning).
   - `## Looks good` — what was done well.

The reviewer does NOT run tests, commit code, or write code. It reports.

$ARGUMENTS — optional. Pass a specific file path, a directory, or `--cached` / `HEAD~1` to scope the review. Leave blank to review all uncommitted changes.
