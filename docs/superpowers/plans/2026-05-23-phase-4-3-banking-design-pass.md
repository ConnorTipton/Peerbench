# Phase 4.3 — Banking Design Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close Phase 4 §"Banking design pass" DoD — every visual choice traces to a `@theme` token (drop the last hardcoded inline-style + the repeated eyebrow-label ad-hoc), `docs/design.md` is the consistent source of truth (reconciles freeze-panes spec, documents the Recharts/anchor-stroke rules added during Sprint 2), and the dashboard prints cleanly to letter-size PDF (Summary matrix at `/` + per-ratio drilldown at `/ratio/<id>`).

**Architecture:** Two atomic PRs landed in order:
- **PR-G (token + documentation cleanup):** add `--color-anchor-tint` / `--color-anchor-tint-alt` tokens (drives the 6% navy blend currently inlined in `ratio-matrix.tsx` twice + writer's `_tint(PRIMARY, 0.06)`), extract `.eyebrow-label` utility, update `docs/design.md` (Recharts typography line, anchor trend-stroke line, freeze-panes `C3` reconcile) + a one-line PLAN.md amendment. Zero rendered-pixel change — composed `color-mix` resolves to the same RGB. Reviewer + design-critic gate before merge.
- **PR-H (print CSS + verification):** add `@media print` block to `globals.css` (hide chrome, drop backgrounds, set letter-size margins, page breaks between matrix categories + drilldown sections, preserve tabular-nums + right-align), tag interactive chrome with `print:hidden`, capture `docs/screenshots/print-summary.pdf` + `docs/screenshots/print-comp-sheet.pdf` from a real Chromium print-to-PDF, document the verification procedure in `docs/operations.md`.

Sentry env-var split and the `cre_rbc_growth_36mo` pipeline ratio are **out of scope** for this plan (separate follow-ups tracked in HANDOFF.md; Sentry change is config-only, growth-gate is a Phase 4.1/4.2 pipeline task).

**Tech Stack:** Tailwind v4 (`@theme` + `@utility`), Next.js 16 App Router, Inter via `next/font/google`, Recharts (drilldown only — print CSS hides the chart canvas? No: chart prints as SVG, just drop the surrounding tints), openpyxl (writer.py — docs reconcile only, no behavior change).

---

## File map

**PR-G — token + documentation cleanup**

| File | Change | Responsibility |
| --- | --- | --- |
| `web/app/globals.css` | Modify | Add 2 anchor-tint tokens to `@theme`; add `.eyebrow-label` utility class |
| `web/components/ratio-matrix.tsx:340-344` | Modify | Replace `<th style={{ background: isAnchorCol ? "color-mix(...)" : "..." }}>` with token reference |
| `web/components/ratio-matrix.tsx:540-567` | Modify | `composeCellBg` reads from `--color-anchor-tint` / `--color-anchor-tint-alt` instead of inlining `color-mix` |
| `web/app/ratio/[ratio_id]/page.tsx:99,114,128` | Modify | Replace 3 `text-table-data uppercase tracking-wide text-text-tertiary` className strings with `eyebrow-label` |
| `web/components/ratio-matrix.tsx:700` | Modify | Replace `text-section-header font-semibold uppercase tracking-wide text-text-secondary` — this one's a different size (section header vs eyebrow), so leave it alone OR introduce `.section-eyebrow` if it appears more than once. Verify uniqueness first. |
| `docs/design.md` | Modify | §Typography +1 line (Recharts text tokens), §Anchor highlighting +1 line (trend-chart 2.5px accent stroke), §Excel export design parity reconcile `freeze_panes` to `C3` with rationale |
| `PLAN.md` | Modify | One-line §Phase 4 Excel-export amendment: `Frozen panes: top 2 rows + first 2 columns on Summary (anchor + ratio name).` |
| `src/peerbench/export/style.py:42` | Modify | Add comment pointer: `# Matches dashboard --color-anchor-tint (globals.css @theme)` (no behavior change) |

**PR-H — print CSS + verification**

| File | Change | Responsibility |
| --- | --- | --- |
| `web/app/globals.css` | Modify | Add `@media print { ... }` block: hide chrome, drop backgrounds, letter-size margins, page breaks, preserve tabular-nums + right-align |
| `web/app/page.tsx:51-61,62` | Modify | Add `print:hidden` to AnchorSelect wrapper + WorkbookDownload Suspense wrapper (As-of timestamp stays — useful in PDF) |
| `web/components/ratio-matrix.tsx` | Modify | Add `print:hidden` to sort caret + collapse toggle interactive affordances; add `print:break-inside-avoid` to ratio rows so a single row doesn't split mid-cell |
| `web/components/anchor-select.tsx` | Modify | Wrap root in `print:hidden` (chrome) |
| `web/components/workbook-download.tsx` | Modify | Wrap root in `print:hidden` (chrome) |
| `web/app/ratio/[ratio_id]/page.tsx` | Modify | `print:break-before-page` on the 8-quarter trend `<section>` and peer-distribution `<section>` |
| `docs/operations.md` | Modify | Add "Print verification" subsection — procedure + acceptance criteria + how to regenerate the two screenshots |
| `docs/screenshots/print-summary.pdf` | Create | Letter-size print of `/` (matrix view) — committed as proof of DoD |
| `docs/screenshots/print-ratio-nim.pdf` | Create | Letter-size print of `/ratio/nim` — committed as proof of DoD |

---

## PR-G — Token + documentation cleanup

### Task G1: Verify the `text-section-header uppercase tracking-wide` string at `ratio-matrix.tsx:700` is unique before deciding eyebrow scope

**Files:**
- Read: `web/components/ratio-matrix.tsx:700`
- Grep: entire `web/` tree

- [ ] **Step 1: Grep for both patterns**

```bash
cd /Users/connortipton/Projects/Peerbench
grep -rn "text-table-data uppercase tracking-wide text-text-tertiary" web/ --include="*.tsx"
grep -rn "text-section-header.*uppercase.*tracking-wide" web/ --include="*.tsx"
```

Expected:
- `text-table-data` variant: 3 occurrences in `app/ratio/[ratio_id]/page.tsx` (lines 99, 114, 128)
- `text-section-header` variant: 1 occurrence in `components/ratio-matrix.tsx:700`

- [ ] **Step 2: Lock decision**

If the `text-section-header` variant is unique (1 site), do NOT add a second utility for it — replacing one usage with a utility class is churn without payoff. The `eyebrow-label` utility covers only the 3 `text-table-data` variant sites.

Add a comment to the plan record below if grep finds a 5th occurrence; the eyebrow utility expands to cover it.

### Task G2: Add the two anchor-tint tokens + eyebrow utility to `globals.css`

**Files:**
- Modify: `web/app/globals.css`

- [ ] **Step 1: Add tokens to `@theme` block**

Edit `web/app/globals.css`. Inside the `@theme { ... }` block, after `--color-text-tertiary`, add:

```css
  /* Anchor-cell tint — docs/design.md §Anchor highlighting.
     6% --color-primary blend over each zebra row tone. Tokenized so
     ratio-matrix.tsx and src/peerbench/export/style.py reference a
     single source of truth instead of inlining color-mix() twice. */
  --color-anchor-tint: color-mix(in srgb, var(--color-primary) 6%, var(--color-surface));
  --color-anchor-tint-alt: color-mix(in srgb, var(--color-primary) 6%, var(--color-surface-alt));
```

- [ ] **Step 2: Add the eyebrow utility class outside `@theme`**

Append to `web/app/globals.css`:

```css
/* Section-eyebrow label — 12px uppercase tertiary text used as H2 above
   definition / formula / notes blocks on drilldown pages. Tokenized per
   design-critic PR-E soft #4. */
.eyebrow-label {
  font-size: var(--text-table-data);
  text-transform: uppercase;
  letter-spacing: 0.05em; /* tracking-wide */
  color: var(--color-text-tertiary);
}
```

- [ ] **Step 3: Build to confirm Tailwind picks up the tokens**

Run:

```bash
cd /Users/connortipton/Projects/Peerbench/web
npm run build
```

Expected: build green; no Tailwind warnings about unknown utilities. The eyebrow rule lives in plain CSS, not `@utility`, because `.eyebrow-label` is a one-shot semantic class — not a Tailwind-variant utility.

- [ ] **Step 4: Commit**

```bash
git add web/app/globals.css
git commit -m "feat(web): add --color-anchor-tint tokens + .eyebrow-label utility

Two new @theme tokens encode the 6% --color-primary blend that
ratio-matrix.tsx currently inlines via color-mix() in two places.
.eyebrow-label collapses the 3-class repetition on the drilldown
page (design-critic PR-E soft #4).

No rendered-pixel change — composed color-mix resolves to the
same RGB; eyebrow class compiles to the identical declarations
as text-table-data uppercase tracking-wide text-text-tertiary.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task G3: Replace the two inline `color-mix` sites in `ratio-matrix.tsx` with the new tokens

**Files:**
- Modify: `web/components/ratio-matrix.tsx:340-344`
- Modify: `web/components/ratio-matrix.tsx:540-567`

- [ ] **Step 1: Replace the `<th>` background inline style (lines 340-344)**

Find:

```tsx
                    style={{
                      background: isAnchorCol
                        ? "color-mix(in srgb, var(--color-primary) 6%, var(--color-surface))"
                        : "var(--color-surface)",
                    }}
```

Replace with:

```tsx
                    style={{
                      background: isAnchorCol
                        ? "var(--color-anchor-tint)"
                        : "var(--color-surface)",
                    }}
```

- [ ] **Step 2: Update `composeCellBg` to read tokens (line 540 area)**

The current implementation computes the anchor base via `color-mix(in srgb, var(--color-primary) 6%, ${zebra})`. Since `zebra` is one of two values (`var(--color-surface)` or `var(--color-surface-alt)`), map directly to the matching token:

Find:

```tsx
  const base = isAnchorCol
    ? `color-mix(in srgb, var(--color-primary) 6%, ${zebra})`
    : zebra;
```

Replace with:

```tsx
  // Anchor tint comes from globals.css @theme tokens — one per zebra row tone.
  // Maintains a 1:1 mapping with the surface/surface-alt zebra to match the
  // unchanged 6% blend without inlining color-mix here.
  const base = isAnchorCol
    ? zebra === "var(--color-surface-alt)"
      ? "var(--color-anchor-tint-alt)"
      : "var(--color-anchor-tint)"
    : zebra;
```

- [ ] **Step 3: Run vitest + typecheck**

```bash
cd /Users/connortipton/Projects/Peerbench/web
npx tsc --noEmit
npx vitest run
```

Expected: tsc clean; 156 vitest tests pass (same count — no test changes).

- [ ] **Step 4: Visual smoke**

```bash
cd /Users/connortipton/Projects/Peerbench/web
npm run dev
```

Then open `http://localhost:3000` in a browser. Anchor column (MidFirst, Cert 4063) should still show the navy tint on every cell — both zebra row tones. Pixel-diff should be zero against pre-change but visual check confirms.

If a Chromium dev tool is available, sample the anchor column header pixel + a row-1 anchor cell + a row-2 anchor cell. RGB must match pre-change values (sample before committing G3 if uncertain).

- [ ] **Step 5: Commit**

```bash
git add web/components/ratio-matrix.tsx
git commit -m "refactor(web): replace inline color-mix anchor tint with @theme tokens

Two call sites in ratio-matrix.tsx (th background, composeCellBg)
now reference --color-anchor-tint / --color-anchor-tint-alt
instead of inlining color-mix(in srgb, var(--color-primary) 6%, …).
Closes the deferred anchor-tint cleanup carried since Sprint 2 PR-D.

Identical rendered pixels — the new tokens are the same color-mix
expression, just hoisted into @theme.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task G4: Collapse the 3 eyebrow-label className repetitions

**Files:**
- Modify: `web/app/ratio/[ratio_id]/page.tsx:99,114,128`

- [ ] **Step 1: Replace all three occurrences**

For each of the 3 `<h2>` tags (lines 99, 114, 128), replace:

```tsx
          <h2 className="mb-1 text-table-data uppercase tracking-wide text-text-tertiary">
```

With:

```tsx
          <h2 className="mb-1 eyebrow-label">
```

The `mb-1` stays as a Tailwind margin utility — it's positional, not typographic.

- [ ] **Step 2: Build + visual smoke**

```bash
cd /Users/connortipton/Projects/Peerbench/web
npm run build
npm run dev
```

Navigate to `http://localhost:3000/ratio/nim`. The three labels — "Definition", "Formula", "Notes" — should render byte-identical to before: 12px, uppercase, tertiary gray, `letter-spacing: 0.05em`.

- [ ] **Step 3: Commit**

```bash
git add web/app/ratio/[ratio_id]/page.tsx
git commit -m "refactor(web): use .eyebrow-label utility on drilldown H2s

Closes design-critic PR-E soft #4. Three drilldown section H2s
(Definition / Formula / Notes) collapse from a 4-class repetition
to a single semantic class defined once in globals.css. Identical
output.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task G5: Update `docs/design.md` — Recharts typography + anchor stroke + freeze-panes reconcile

**Files:**
- Modify: `docs/design.md`

- [ ] **Step 1: Append the Recharts typography line to §Typography**

Find the §Typography table (ends with `--text-superscript` row). After the table, before §Layout rules, add:

```markdown
**Recharts text bridge.** Recharts components need numeric `fontSize` props (can't read CSS vars). `web/lib/chart-tokens.ts` mirrors the typography tokens above as JS numbers — Recharts axis ticks use `--text-table-data` (12); axis labels use `--text-superscript` (10). Never inline a `fontSize` literal in chart code; import from `chart-tokens.ts`.
```

- [ ] **Step 2: Append the anchor trend-stroke line to §Anchor highlighting**

Find §Anchor highlighting. After the last bullet, add:

```markdown
- **Trend-chart anchor stroke.** On the `/ratio/<id>` 8-quarter trend chart, the anchor bank renders as a 2.5px stroke in `--color-accent`, drawn last so it sits on top of peer-line overlap. Peers render as 1px strokes in `--color-text-tertiary`. Strip-plot points (peer distribution panel): 6px anchor dot in `--color-accent`, 4px peer dots in `--color-text-tertiary`.
```

- [ ] **Step 3: Reconcile §Excel export design parity freeze-panes**

Find the bullet:

```markdown
- **Frozen panes:** top 2 rows + first column on Summary.
```

Replace with:

```markdown
- **Frozen panes (Summary tab):** top 2 rows + first 2 columns (openpyxl `freeze_panes = "C3"`). First column is the ratio category, second is the ratio name — both stay visible during horizontal scroll across peer columns. Other tabs use single-column or single-row freezes per tab semantics (see `src/peerbench/export/writer.py`).
```

- [ ] **Step 4: Commit**

```bash
git add docs/design.md
git commit -m "docs(design): document Recharts text bridge + anchor stroke + reconcile freeze_panes

Three deferred design-critic items from Sprint 2 PR-E and PR #19/#20
close here:

- §Typography gains a 'Recharts text bridge' paragraph documenting
  web/lib/chart-tokens.ts as the canonical JS mirror of @theme
  typography tokens.
- §Anchor highlighting gains a trend-chart stroke spec matching
  PR-E's chart implementation (2.5px accent anchor drawn last,
  1px tertiary peers).
- §Excel export design parity 'Frozen panes' line reconciles to
  C3 (2 cols + 2 rows) matching writer.py and documents the
  rationale (category + ratio name columns both pinned).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task G6: Mirror the freeze-panes reconcile in `PLAN.md`

**Files:**
- Modify: `PLAN.md:415`

- [ ] **Step 1: Replace the PLAN.md line**

Find the §Phase 4 Excel export "Formatting requirements" bullet:

```markdown
- **Frozen panes:** top 2 rows + first column on Summary.
```

Replace with:

```markdown
- **Frozen panes:** top 2 rows + first 2 columns on Summary (`freeze_panes = "C3"` — ratio category + name both pinned).
```

- [ ] **Step 2: Commit**

```bash
git add PLAN.md
git commit -m "docs(plan): reconcile Summary freeze_panes to C3 (matches writer + design.md)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task G7: Add a comment pointer in `src/peerbench/export/style.py` linking the dashboard token

**Files:**
- Modify: `src/peerbench/export/style.py:42`

- [ ] **Step 1: Annotate the line**

Find:

```python
ANCHOR_TINT_HEX = _tint(PRIMARY, 0.06)  # --color-primary /6 per HANDOFF
```

Replace with:

```python
# Matches dashboard --color-anchor-tint (web/app/globals.css :root).
# Both apply 6% --color-primary over the cell background. Keep in sync.
# (The token lives in :root rather than @theme because Tailwind v4 drops
# color-mix() with nested var() chains from theme-parse output.)
ANCHOR_TINT_HEX = _tint(PRIMARY, 0.06)
```

- [ ] **Step 2: Run pytest to confirm zero behavior change**

```bash
cd /Users/connortipton/Projects/Peerbench
uv run pytest -q
```

Expected: 162 tests pass (same count).

- [ ] **Step 3: Commit**

```bash
git add src/peerbench/export/style.py
git commit -m "docs(export): pointer comment linking ANCHOR_TINT_HEX to web token

No behavior change. Annotates the dashboard <-> Excel parity for
the 6% navy anchor tint so a future change to one side flags the
other.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task G8: PR-G — open + sub-agent review

- [ ] **Step 1: Push branch + open PR**

```bash
cd /Users/connortipton/Projects/Peerbench
git push -u origin <branch-name>
gh pr create --title "Phase 4.3 cleanup: anchor-tint tokens + eyebrow utility + design.md reconcile" \
  --body "$(cat <<'EOF'
## Summary

Closes the three deferred design cleanups carried since Sprint 2:

- **Anchor tint tokenized.** Two new `@theme` tokens (`--color-anchor-tint`, `--color-anchor-tint-alt`) replace the inlined `color-mix(in srgb, var(--color-primary) 6%, ...)` in `ratio-matrix.tsx` (two sites). Zero rendered-pixel change.
- **`.eyebrow-label` utility.** Drilldown H2s (Definition / Formula / Notes) collapse from a 4-class string to a single semantic class. design-critic PR-E soft #4.
- **`docs/design.md` reconcile.** §Typography gains the Recharts text-bridge paragraph; §Anchor highlighting documents the 2.5px accent trend stroke; §Excel export design parity freeze-panes spec moves from `first column` to `first 2 columns / C3` to match `writer.py`. `PLAN.md` mirrors the freeze-panes change; `style.py` gains a cross-reference comment.

No new tests — every change is either token rename (compile-time verified) or docs.

## Test plan

- [x] `npm run build` green
- [x] `npx tsc --noEmit` clean
- [x] `npx vitest run` — 156 pass (same count)
- [x] `uv run pytest -q` — 162 pass (same count)
- [x] Visual smoke at `localhost:3000` and `localhost:3000/ratio/nim` — anchor column tint unchanged, eyebrow labels identical
- [ ] Reviewer sub-agent PASS
- [ ] design-critic PASS

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Dispatch reviewer sub-agent**

Use the `Agent` tool with `subagent_type: "reviewer"`:

> Prompt: "Review the diff on this branch (PR-G, Phase 4.3 cleanup). Five commits: anchor-tint tokens added, ratio-matrix.tsx inline color-mix sites replaced, drilldown H2 eyebrow utility, design.md + PLAN.md + style.py docs reconcile. Verify (a) zero rendered-pixel change in the anchor column (sample `color-mix(in srgb, #0a1f3d 6%, #ffffff)` vs `var(--color-anchor-tint)` — same result?); (b) `composeCellBg` zebra→token mapping is still 1:1 with the prior color-mix expression; (c) the freeze-panes reconcile in design.md and PLAN.md matches the actual writer.py call; (d) no Tailwind warnings about unknown utilities. Report blocking vs soft findings."

- [ ] **Step 3: Dispatch design-critic sub-agent**

Use `Agent` with `subagent_type: "design-critic"`:

> Prompt: "Audit PR-G against `docs/design.md`. The PR adds 2 anchor-tint tokens, a `.eyebrow-label` utility, and three docs additions (Recharts text bridge, trend-chart anchor stroke, freeze_panes C3). Check: (1) tokens consistent with §Color palette opacity tiers; (2) eyebrow utility duplicates an existing token or correctly fills the gap; (3) design.md additions are positioned in the correct section and don't conflict with adjacent rules; (4) any inline-style / hardcoded-color regressions introduced. Report PASS / SOFT FAIL / FAIL with blocking and soft findings."

- [ ] **Step 4: Address findings on-branch**

For each blocking finding, fix on-branch and add a fix commit. For soft findings, fix if cheap; otherwise log in PR description as deferred follow-up.

- [ ] **Step 5: Merge after gates green**

```bash
gh pr merge --squash --delete-branch
git checkout main && git pull
```

---

## PR-H — Print CSS + verification

### Task H1: Audit which UI elements are chrome (hide) vs content (keep) in print

**Files:**
- Read: `web/app/page.tsx`, `web/app/ratio/[ratio_id]/page.tsx`, `web/components/anchor-select.tsx`, `web/components/workbook-download.tsx`, `web/components/ratio-matrix.tsx`

- [ ] **Step 1: Build the keep/hide list**

For a print-ready PDF, these are **chrome** and should `print:hidden`:
- `AnchorSelect` (interactive dropdown — useless on paper)
- `WorkbookDownload` link (no clicks on paper)
- `SortHeader` sort caret + button affordances (sort state should still be visible in column order, but the caret icon hides)
- Section-collapse toggle on the matrix (rows print expanded — collapsed rows would lose data)
- `← Matrix` back-link on drilldown

These are **content** and stay:
- `<h1>` page title
- `As of <date>` timestamp
- Ratio matrix `<table>` content (all rows visible — overriding collapsed state)
- Drilldown definition / formula / notes blocks
- Recharts SVG (8-quarter trend + peer distribution — they print as scalable vector)

- [ ] **Step 2: Lock the page-break strategy**

Matrix page (`/`):
- Page-break inside `<tr>` is forbidden (`print:break-inside-avoid` on each row so a cell never splits)
- Optional: page-break before each section row (category divider) so a category never starts at the bottom of a page. Tag the section row with `print:break-before-page` *except* the first one.

Drilldown page (`/ratio/<id>`):
- `<header>` stays on page 1
- Definition / Formula / Notes grid stays on page 1
- "8-quarter trend" `<section>` — `print:break-before-page` (gets its own page)
- "Peer distribution" `<section>` — `print:break-before-page` (gets its own page)

### Task H2: Add the `@media print` block to `globals.css`

**Files:**
- Modify: `web/app/globals.css`

- [ ] **Step 1: Append the print block**

After the existing `html, body { ... }` block, append:

```css
/*
 * Print CSS — docs/design.md §Print CSS.
 * Letter-size, 0.5in margins, black-on-white, no backgrounds, no tints.
 * Tabular-nums + right-align preserved (inherited from base body styles).
 * Verify on /  and /ratio/nim per docs/operations.md §Print verification.
 */
@page {
  size: letter;
  margin: 0.5in;
}

@media print {
  html,
  body {
    background: white;
    color: black;
    font-size: var(--text-table-data); /* 12px — tighter than screen body for density on paper */
  }

  /* Drop all conditional-formatting and anchor tints. design.md §Print CSS:
     "Black text on white. No background colors, no tints." */
  *,
  *::before,
  *::after {
    background: transparent !important;
    color: black !important;
    box-shadow: none !important;
  }

  /* Keep grid lines — they remain useful on paper for table readability.
     Re-assert with a true black border so it survives the wildcard color reset. */
  th,
  td {
    border-color: black !important;
  }

  /* Hide interactive chrome marked with the print:hidden utility. */
  .print\:hidden {
    display: none !important;
  }

  /* Section breaks — applied via the print:break-before-page utility on
     drilldown <section>s and matrix category rows. */
  .print\:break-before-page {
    break-before: page;
  }

  /* Prevent a single matrix row from splitting across a page boundary. */
  .print\:break-inside-avoid {
    break-inside: avoid;
  }

  /* Sticky headers turn into in-flow headers on paper — sticky positioning
     creates layout glitches in print. */
  .sticky {
    position: static !important;
  }

  /* Links: drop hover decoration, keep text. URLs not surfaced (designed
     for in-hand review, not for re-typing URLs). */
  a {
    text-decoration: none !important;
  }
}
```

- [ ] **Step 2: Build to confirm Tailwind compiles the `print:` variants**

```bash
cd /Users/connortipton/Projects/Peerbench/web
npm run build
```

Expected: green. Tailwind v4 supports `print:` variant out of the box.

- [ ] **Step 3: Commit**

```bash
git add web/app/globals.css
git commit -m "feat(web): add @media print block — letter-size, no backgrounds, page breaks

docs/design.md §Print CSS contract. Hides .print:hidden chrome,
drops every background/tint to satisfy 'black text on white,
no background colors,' converts sticky headers to in-flow,
preserves tabular-nums + right-align via inheritance from the
existing body styles. @page sets letter / 0.5in margins.

Component-side print:hidden / print:break-* class additions
land in follow-up commits.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task H3: Tag chrome with `print:hidden` on the matrix page

**Files:**
- Modify: `web/app/page.tsx`
- Modify: `web/components/anchor-select.tsx`
- Modify: `web/components/workbook-download.tsx`

- [ ] **Step 1: Wrap AnchorSelect + WorkbookDownload at the call site**

In `web/app/page.tsx`, find:

```tsx
        <div className="flex flex-col items-end gap-1">
          <span className="text-body text-text-secondary">
            As of {formatReportDate(data.quarter.report_date)}
          </span>
          <Suspense fallback={null}>
            <WorkbookDownload />
          </Suspense>
        </div>
```

Replace with:

```tsx
        <div className="flex flex-col items-end gap-1">
          <span className="text-body text-text-secondary">
            As of {formatReportDate(data.quarter.report_date)}
          </span>
          <Suspense fallback={null}>
            <div className="print:hidden">
              <WorkbookDownload />
            </div>
          </Suspense>
        </div>
```

And:

```tsx
      <div className="mb-4">
        <AnchorSelect institutions={data.institutions} anchorCert={anchorCert} />
      </div>
```

Replace with:

```tsx
      <div className="mb-4 print:hidden">
        <AnchorSelect institutions={data.institutions} anchorCert={anchorCert} />
      </div>
```

- [ ] **Step 2: Build + vitest**

```bash
cd /Users/connortipton/Projects/Peerbench/web
npm run build
npx vitest run
```

Expected: 156 vitest pass.

- [ ] **Step 3: Commit**

```bash
git add web/app/page.tsx
git commit -m "feat(web): print:hidden on AnchorSelect + WorkbookDownload chrome

Matrix page header keeps title + 'As of <date>' visible in print
PDFs; interactive chrome (anchor dropdown, workbook download link)
hides per docs/design.md §Print CSS.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task H4: Tag matrix rows + interactive affordances with print classes

**Files:**
- Modify: `web/components/ratio-matrix.tsx`

- [ ] **Step 1: Add `print:break-inside-avoid` to data row `<tr>`**

Find the data-row return (around line 378):

```tsx
            return (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => {
```

Replace with:

```tsx
            return (
              <tr key={row.id} className="print:break-inside-avoid">
                {row.getVisibleCells().map((cell) => {
```

- [ ] **Step 2: Force section rows to expand in print**

The current implementation hides collapsed-category rows entirely via the `collapsed` Set. For print, the user expects every ratio to show on paper regardless of UI collapse state. The cleanest fix: emit the rows in HTML always, and use CSS `display: none` to hide collapsed-state rows on screen — then unset that for print.

Locate the row-rendering loop (`table.getRowModel().rows.map(...)`). The current architecture filters collapsed rows OUT of the TanStack row model. **Confirm via the code whether collapsed rows are filtered at the data layer or hidden via CSS.** If filtered at data layer:

- [ ] **Step 2a: Run a grep to find the collapse implementation**

```bash
grep -n "collapsed\|isCollapsed\|filterRows\|rowModel" web/components/ratio-matrix.tsx | head -20
grep -n "collapsed\|isCollapsed" web/lib/collapse.ts
```

- [ ] **Step 2b: Decide handling**

If collapsed rows are filtered out of the row model: this is **out of scope for this PR**. Print fidelity for collapsed-category rows would require restructuring how the row model is built. Document as a deferred Phase 4.3 follow-up in the PR body — "Print currently mirrors the on-screen collapsed state; expanding collapsed categories in print is a separate change." Leave existing behavior; the user can manually expand categories before printing.

If collapsed rows are hidden via CSS class: add `print:!block` (or `print:table-row`) to override. Show that exact edit here once Step 2a confirms.

(Plan note: HANDOFF describes section collapse as `applyCollapse` → URL param state. The likely architecture filters; defer.)

- [ ] **Step 3: Add `print:hidden` to the section-toggle button**

Find the `SectionToggle` rendering inside the section row (around line 365). The `<button>` itself is chrome — its label content ("Profitability", "Capital", etc.) IS data. Hide the button affordance but keep the row's label visible.

Find the section-toggle markup (likely inside `components/ratio-matrix.tsx` near `SectionToggle`). Wrap the chevron / interactive affordance in `print:hidden`. Leave the category label visible.

If `SectionToggle` is a single button with chevron + label intermingled, refactor to put the label as plain text + the chevron inside a `print:hidden` span:

```tsx
<button ...>
  <span aria-hidden className="print:hidden">▾</span>
  <span>{label}</span>
</button>
```

(Plan note: confirm structure with a Read before editing.)

- [ ] **Step 4: Add `print:hidden` to sort carets**

Sort carets / direction indicators add no value on paper (the column order conveys sort). Find each rendered sort-indicator (likely a `<span>` with `↑` / `↓` / `▴` glyph) and append `print:hidden` to its className.

Use a grep to locate:

```bash
grep -n "sort.*[↑↓▴▾▼▲]\|asc\|desc.*indicator" web/components/ratio-matrix.tsx | head -10
```

Edit each match to add `print:hidden`.

- [ ] **Step 5: Build + vitest**

```bash
cd /Users/connortipton/Projects/Peerbench/web
npm run build
npx vitest run
```

Expected: 156 vitest pass.

- [ ] **Step 6: Commit**

```bash
git add web/components/ratio-matrix.tsx
git commit -m "feat(web): print:hidden on sort carets + section-toggle affordances; break-inside-avoid on data rows

Matrix prints with every data row intact (no mid-cell page splits)
and without interactive UI glyphs that have no meaning on paper.

Collapsed-category expansion in print is deferred to a follow-up
(row model filters at the data layer, not via CSS, so print
currently mirrors on-screen collapse state).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task H5: Tag drilldown chrome + section page-breaks

**Files:**
- Modify: `web/app/ratio/[ratio_id]/page.tsx`

- [ ] **Step 1: Hide the `← Matrix` back-link**

Find the `<Link href={matrixBackHref} ...>` element. Append `print:hidden` to its className:

```tsx
          <Link
            href={matrixBackHref}
            className="rounded-sm text-body text-text-secondary focus:outline-none focus-visible:outline-1 focus-visible:outline-accent hover:text-accent print:hidden"
          >
            ← Matrix
          </Link>
```

- [ ] **Step 2: Add page-break to trend + distribution sections**

Find the 8-quarter trend `<section>` (around line 136):

```tsx
      <section className="mb-6">
        <h2 className="mb-2 text-section-header font-semibold text-text">
          8-quarter trend
        </h2>
```

Add `print:break-before-page`:

```tsx
      <section className="mb-6 print:break-before-page">
        <h2 className="mb-2 text-section-header font-semibold text-text">
          8-quarter trend
        </h2>
```

Locate the peer-distribution `<section>` (Read the file to find the exact line). Apply the same `print:break-before-page` addition.

- [ ] **Step 3: Build + vitest**

```bash
cd /Users/connortipton/Projects/Peerbench/web
npm run build
npx vitest run
```

Expected: 156 vitest pass.

- [ ] **Step 4: Commit**

```bash
git add web/app/ratio/[ratio_id]/page.tsx
git commit -m "feat(web): print breaks on drilldown — header + grid on page 1, trend + distribution each on own page

← Matrix back-link hides in print (no clicks on paper). Trend
chart and peer distribution sections gain print:break-before-page
so each lands on a fresh page — large charts at full letter-size
read better than two squeezed onto a single page.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task H6: Capture print-PDF screenshots for `docs/screenshots/`

**Files:**
- Create: `docs/screenshots/print-summary.pdf`
- Create: `docs/screenshots/print-ratio-nim.pdf`
- Confirm: `docs/screenshots/` directory exists; if not, create it

- [ ] **Step 1: Start the dev server**

```bash
cd /Users/connortipton/Projects/Peerbench/web
npm run build
npm start  # production build — closer to Vercel's render path than `dev`
```

Server listens on `http://localhost:3000`.

- [ ] **Step 2: Print `/` to PDF**

This step is **manual** — automated print-to-PDF would require Playwright or Chromium headless, which the project doesn't have set up. Use the browser:

1. Open `http://localhost:3000` in Chromium or Safari
2. Cmd-P → Destination: Save as PDF → Paper size: US Letter → Margins: Default
3. Save as `/Users/connortipton/Projects/Peerbench/docs/screenshots/print-summary.pdf`

Acceptance criteria for the PDF:
- Page 1: header (`Peerbench` + `As of <date>`) visible at top; no AnchorSelect dropdown; no WorkbookDownload link; sort carets gone
- Table: all 30 ratios visible across N pages; no cell text overflowing column width; no row split across pages; grid lines visible
- Backgrounds: white only — no anchor navy tint, no green/red quartile tints, no amber/red regulatory tints
- Negatives still in parentheses; numerics right-aligned; tabular-nums spacing intact

- [ ] **Step 3: Print `/ratio/nim` to PDF**

1. Open `http://localhost:3000/ratio/nim`
2. Cmd-P → Save as PDF (same settings)
3. Save as `/Users/connortipton/Projects/Peerbench/docs/screenshots/print-ratio-nim.pdf`

Acceptance criteria:
- Page 1: ratio title + As-of timestamp + Definition / Formula / Notes grid (no `← Matrix` link)
- Page 2: "8-quarter trend" header + LineChart SVG, anchor (2.5px) still visible as a darker stroke even with `* { color: black !important }` — verify the SVG `stroke` property still applies. **Known risk:** if the wildcard `color: black !important` kills SVG stroke color, the chart will print as monochrome with no anchor distinction. Acceptable for v1 but document in operations.md as a known limitation. (Alternative: scope the `*` reset to exclude `svg *` if monochrome is unacceptable.)
- Page 3: "Peer distribution" header + ScatterChart SVG

- [ ] **Step 4: Inspect SVG stroke fallback**

If the chart pages render with no visual anchor distinction (all lines look the same shade), **scope the wildcard color reset to exclude SVG descendants**:

In `web/app/globals.css`, change:

```css
  *,
  *::before,
  *::after {
    background: transparent !important;
    color: black !important;
    box-shadow: none !important;
  }
```

To:

```css
  *:not(svg *),
  *::before,
  *::after {
    background: transparent !important;
    color: black !important;
    box-shadow: none !important;
  }
```

Re-print and re-verify.

- [ ] **Step 5: Commit PDFs**

```bash
git add docs/screenshots/print-summary.pdf docs/screenshots/print-ratio-nim.pdf
git commit -m "docs(screenshots): print-PDF proofs for / and /ratio/nim

Letter-size, 0.5in margins, no backgrounds, page breaks between
matrix categories and between drilldown sections. Phase 4 DoD
artifact under docs/screenshots/ for interview / README use.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task H7: Document the print verification procedure in `docs/operations.md`

**Files:**
- Modify: `docs/operations.md`

- [ ] **Step 1: Read the current operations doc to find the right insertion point**

```bash
cat docs/operations.md | head -40
grep -n "^#\|^##" docs/operations.md
```

Pick a section near "Hosting" or "Deploy" — print verification is an operational concern.

- [ ] **Step 2: Append the §Print verification subsection**

Add:

```markdown
## Print verification

Phase 4.3 DoD: the dashboard must print cleanly to letter-size PDF.
Verify on every PR touching `web/app/globals.css`, the matrix, or the
drilldown page.

### Procedure

```bash
cd web
npm run build
npm start  # serve production build on http://localhost:3000
```

1. Print `/` to PDF: Cmd-P → Save as PDF → US Letter → Default margins → save as `docs/screenshots/print-summary.pdf`.
2. Print `/ratio/nim` to PDF: same settings → save as `docs/screenshots/print-ratio-nim.pdf`.

### Acceptance criteria

- Letter size; 0.5in margins (set via `@page` rule in `globals.css`).
- Black text on white. No tints — anchor navy, quartile green/red, amber/red regulatory all dropped.
- No chrome: AnchorSelect, WorkbookDownload, sort carets, section-toggle chevrons, drilldown `← Matrix` link all hidden.
- All 30 ratios visible on the matrix print; no row split across pages.
- Drilldown trend + distribution charts each on their own page; SVG stroke colors retained (anchor distinguishable from peers).
- Negatives in parentheses; numerics right-aligned; tabular-nums spacing intact.

### Known limitation

The matrix prints in its current on-screen collapsed state. If categories are collapsed via the UI before printing, the collapsed ratios will be absent from the PDF. Print after expanding all categories to capture the full set.
```

- [ ] **Step 3: Commit**

```bash
git add docs/operations.md
git commit -m "docs(ops): document print verification procedure + acceptance criteria

Repeatable steps to regenerate the print-summary.pdf /
print-ratio-nim.pdf artifacts under docs/screenshots/. Documents
the on-screen-collapse limitation as a known caveat.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task H8: PR-H — open + sub-agent review

- [ ] **Step 1: Push branch + open PR**

```bash
cd /Users/connortipton/Projects/Peerbench
git push -u origin <branch-name>
gh pr create --title "Phase 4.3 print CSS — letter-size PDF for matrix + drilldown" \
  --body "$(cat <<'EOF'
## Summary

Closes Phase 4.3 DoD §Print CSS. The dashboard now prints cleanly to letter-size PDF.

- `@page` rule + `@media print` block in `web/app/globals.css` — letter, 0.5in margins, black-on-white, drops every background/tint, preserves grid lines + tabular-nums.
- `print:hidden` on AnchorSelect, WorkbookDownload, sort carets, section-toggle chevrons, drilldown `← Matrix` link.
- `print:break-inside-avoid` on every matrix data row (no mid-cell splits).
- `print:break-before-page` on drilldown trend + peer-distribution sections (each lands on its own page).
- `docs/screenshots/print-summary.pdf` and `docs/screenshots/print-ratio-nim.pdf` captured as DoD proof.
- `docs/operations.md` documents the regeneration procedure + acceptance criteria + the known on-screen-collapse limitation.

## Test plan

- [x] `npm run build` green
- [x] `npx tsc --noEmit` clean
- [x] `npx vitest run` — 156 pass (same count, no test changes)
- [x] Manual: print `/` to PDF — verifies header / no chrome / no tints / row integrity / right-align
- [x] Manual: print `/ratio/nim` to PDF — verifies page breaks, SVG stroke retention, no `← Matrix` chrome
- [ ] Reviewer sub-agent PASS
- [ ] design-critic PASS

## Out of scope (separate follow-ups)

- Expanding on-screen-collapsed categories in print output (would require row-model restructure).
- Sentry env-var split (config-only, tracked in HANDOFF.md).
- `cre_rbc_growth_36mo` pipeline ratio (Phase 4.1/4.2 work).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Dispatch reviewer sub-agent**

> Prompt: "Review the diff on PR-H (Phase 4.3 print CSS). Six commits: @media print block in globals.css, print:hidden on chrome (matrix + drilldown), break-inside-avoid on data rows, break-before-page on drilldown sections, PDF screenshots, operations.md procedure. Verify (a) the wildcard color reset doesn't break SVG stroke color in Recharts (charts on /ratio/nim should still distinguish anchor from peers); (b) sticky→static conversion doesn't break the on-screen sticky header; (c) print:hidden classes are scoped to chrome only (no data accidentally hidden); (d) @page rule lives outside the @media print block (Chrome quirk — confirm via build output)."

- [ ] **Step 3: Dispatch design-critic sub-agent**

> Prompt: "Audit PR-H against `docs/design.md` §Print CSS. Inspect the two PDFs under `docs/screenshots/` and report: (1) any backgrounds / tints that survive the wildcard reset; (2) any chrome elements visible in the PDF; (3) chart legibility under monochrome (if applicable); (4) page-break placement (sensible vs awkward); (5) any negative numbers rendered with a minus sign instead of parentheses. Report PASS / SOFT FAIL / FAIL."

- [ ] **Step 4: Address findings on-branch**

For blocking findings, fix on-branch (likely targets: wildcard reset scope, sticky-conversion edge cases, missed chrome). Re-export the affected PDF after each fix and re-commit.

- [ ] **Step 5: Merge after gates green**

```bash
gh pr merge --squash --delete-branch
git checkout main && git pull
```

### Task H9: Update HANDOFF.md — Phase 4.3 closed

**Files:**
- Modify: `HANDOFF.md`

- [ ] **Step 1: Add a new TL;DR block at the top describing PR-G / PR-H landings + Phase 4 DoD progress**

Mirror the structure of the existing post-PR-#20 TL;DR. Reference both PR numbers, the screenshots committed, and the deferred follow-ups (collapsed-row print, Sentry env split, growth gate).

- [ ] **Step 2: Update §Recommended first action**

Phase 4.3 closes here. Next sub-phase per `PLAN.md` v1.3 ordering is Phase 4.1 (insights generation) or Phase 4.4 (README + screenshots + Loom — which now has its DoD-proof PDFs to reference).

- [ ] **Step 3: Commit**

```bash
git add HANDOFF.md
git commit -m "docs(handoff): post-PR-#G/#H — Phase 4.3 banking design pass complete

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push
```

---

## Out of scope — explicit deferrals

- **Expanding collapsed categories in print output.** Print currently mirrors on-screen collapsed state because TanStack row-model filtering happens before render. Document in operations.md (Task H7) and leave for a follow-up if the limitation matters in practice.
- **Sentry `SENTRY_DSN` / `NEXT_PUBLIC_SENTRY_DSN` env-var split.** Config-only change; not a design-pass concern. Track in HANDOFF.md.
- **`cre_rbc_growth_36mo` pipeline ratio.** Phase 4.1 / 4.2 follow-up; unrelated to design pass.
- **Phase 4.2 deferred items 1–4 + 6–7 from HANDOFF.md.** Excel-export internals; bundle into a separate Excel-polish PR when next touching `src/peerbench/export/`.

---

## Self-review checklist (run before handing off to executor)

1. **Spec coverage** — every Phase 4.3 DoD bullet mapped:
   - "Tabular-nums everywhere" → already global per `globals.css:32-39`; explicitly preserved in @media print (Task H2) → covered.
   - "Conditional formatting on all tables" → dashboard via `composeCellBg` (PR-G token rename keeps behavior); Excel via `style.py` (PR-G comment pointer); design.md §Conditional formatting already documents — covered.
   - "Print CSS verified on Summary and Comp Sheet pages" → Task H6 prints `/` (Summary equivalent) + `/ratio/nim` (Comp Sheet equivalent — the dashboard's per-ratio drilldown is the closest analogue to the Excel comp-sheet tab; the workbook is verified separately). PDFs committed. Covered.
   - Carry-over: anchor 6% inline → Tasks G2 + G3.
   - Carry-over: design.md Recharts addendum → Task G5.
   - Carry-over: design.md anchor-stroke addendum → Task G5.
   - Carry-over: eyebrow rename → Tasks G2 + G4.
   - Carry-over: freeze_panes reconcile → Tasks G5 + G6.

2. **Placeholder scan** — none. Every code-change step shows the exact before/after.

3. **Type consistency** — `--color-anchor-tint` / `--color-anchor-tint-alt` names used identically in G2, G3, G7, and design.md. `.eyebrow-label` used identically in G2, G4. `print:hidden` / `print:break-before-page` / `print:break-inside-avoid` used consistently across H2–H5. PDF filenames `print-summary.pdf` + `print-ratio-nim.pdf` used identically in H6 and H7.
