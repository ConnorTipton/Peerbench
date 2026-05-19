# Peerbench

## Goal
Bank peer-benchmarking tool on FFIEC Call Report data, anchored on MidFirst Bank (Cert 4063). Internship-prep for Summer 2026 FP&A at MidFirst.

## Architecture
Python pipeline (uv) → Supabase Postgres → Next.js 16 dashboard → Vercel Hobby.
Daily ingest via GitHub Actions cron.
Excel comp workbook export (Phase 4) via `uv run peerbench export` — reads from the same `ratios` table the dashboard uses.

## Conventions
- Python: 3.13, uv, ruff format, pyright strict, pytest.
- TypeScript: strict mode, no `any`, prefer server components, App Router.
- DB: snake_case columns, Cert # as bank PK.
- Ratios: each ratio has a row in `ratio_defs` with human-readable formulas (source of truth for documentation) and a registered handler in `peerbench.ratio_engine.handlers` (source of truth for execution). A contract test keeps them in 1:1 correspondence. Never inline a formula in the dashboard (TS) or Excel export — those layers read computed values from the `ratios` table only.
- Post-CECL nomenclature: ACL (not ALLL).
- **Ingest pipeline is idempotent**: daily cron, upserts on `facts (cert, quarter_id, field_code)`, re-fetches the last 8 quarters each run. The restatement detector compares incoming values against stored values; on diff it flips `facts.restated = true`, writes a `quality_log` row with old/new values, and marks affected `ratios` rows for recomputation. The daily cron also serves as the Supabase inactivity heartbeat — no separate heartbeat job exists.
- **Design tokens** (palette, typography, layout rules) live in `docs/design.md` and are encoded in Tailwind v4's `@theme` block. Never hardcode colors or font sizes in component code — every design choice traces back to a `@theme` token.

## Definition of done (per phase)
1. Pipeline: ratios match FDIC pre-computed ±2 bps on 5-bank sample; restatement detector wired and logging.
2. Dashboard: all 30 ratios render for all peers, <1s load; restatement indicator surfaces on affected cells; all pages conform to `docs/design.md`.
3. Hosting: daily ingest cron green for 3 consecutive days; weekly backup green.
4. Polish: insights generate, Excel comp workbook export ships and matches the dashboard view, banking design pass complete (tabular-nums, conditional formatting, print CSS), README + Loom shipped.

## Don'ts
- No M&A, capital plans, deposit beta models, or pricing models.
- No scraping.
- No real-time intraday data.
- No commercial use of Vercel Hobby plan.
- **No formula logic in the dashboard layer or the Excel export layer** — all ratios computed in the pipeline, persisted to the `ratios` table, and read. The Excel export reads from the same `ratios` table; it does not recompute.

## MCP servers
- Context7 — version-specific docs lookup
- Supabase MCP (read-only in dev) — DB schema + safe SQL
- GitHub MCP — PR review automation
- Next.js DevTools MCP — diagnostics + upgrades

## Sub-agents
- `reviewer` — adversarial code review; runs on every diff before commit
- `pipeline-validator` — Phase 1; cross-checks ratios vs FDIC pre-computed; also verifies restatement detector behavior on synthetic diffs
- `design-critic` — Phase 2/4; banking-grade design heuristics

## Slash commands
- `/ratio <name>` — show formula, fields, current value for MidFirst + Tier 1
- `/peer-diff <ratio>` — variance vs peer median, one paragraph
- `/validate-pipeline` — run ratio validation suite
- `/insight <cert> <quarter>` — generate commentary bullet
- `/review` — invoke `reviewer` sub-agent on the current diff
