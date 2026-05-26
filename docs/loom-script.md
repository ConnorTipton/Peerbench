# Loom walkthrough — Peerbench

**Target:** 5 minutes. Interview audience (Summer 2026 FP&A internship). Goal is to show (a) the analytical product, (b) the engineering choices behind it, and (c) the anchor-vs-peer story on a real ratio.

**Pre-recording setup:**

- Browser at https://peerbench-web.vercel.app, second tab on the GitHub repo `README.md`.
- Window at 1440×900 (matches the screenshots in `docs/screenshots/`).
- Close all other tabs, hide bookmarks bar.
- Cursor speed slow; have one or two pauses queued so the viewer can read.
- Mic test: speak in complete sentences. No "umm." Re-record if you trip.

---

## Beat sheet

### 0:00 — 0:20 · Open

**Screen:** Matrix view (`/`). Cursor parked off-page.

**Say:**
> "Hi, this is Peerbench. It's a quarterly bank peer-benchmarking dashboard I built on FDIC Call Report data. It tracks MidFirst Bank against four peer banks across 29 ratios — profitability, yields, balance sheet mix, asset quality, capital, concentration, and liquidity. The goal was to build something I could actually use at MidFirst — something an analyst would open on a Monday morning before diving into a credit deck."

---

### 0:20 — 1:00 · Matrix orientation

**Screen:** Hover the *Anchor* dropdown (top left, shows "MidFirst Bank (4063)"). Don't click — just point.

**Say:**
> "MidFirst is the anchor — that's the first data column, tinted to mark it as the bank you care about most. The four columns to the right are the peer banks: Bank OZK, BOK Financial, First-Citizens, and Frost. I picked them as Tier 1 peers — similar asset size, similar regional footprint, all OCC-chartered."

**Do:** Move cursor down to highlight the first three category headers (Profitability, Yields & Costs, Balance Sheet Mix).

**Say:**
> "Each row is one ratio. The heat-map coloring is quartile-based — red is the bottom quartile across the peer set, green is the top, with the directional sign baked in per ratio. So for Return on Assets, green means higher; for Cost of Funds, green means lower."

---

### 1:00 — 2:00 · Anchor story on NIM

**Screen:** Hover the *Net Interest Margin* row, MidFirst cell. It should read around 2.89% with a small `r` superscript.

**Say:**
> "Let me walk through one ratio. Net Interest Margin — that's net interest income over average earning assets, annualized. MidFirst is at 2.89%, which is the lowest in this peer group. Frost Bank is at 3.62%; Bank OZK is at 4.33%. That's a real spread."

**Do:** Hover over the `r` superscript so the tooltip appears.

**Say:**
> "The little `r` is a restatement marker — FDIC re-published the underlying NIM input for this quarter, and the dashboard caught it on the next nightly ingest. The tooltip shows the old and new values. That's important for analysts — you don't want to anchor a credit memo on a number that was silently revised."

**Do:** Click the *Net Interest Margin* row name to open the drilldown.

---

### 2:00 — 3:10 · Drilldown trend

**Screen:** `/ratio/nim`. Pause for the chart to settle.

**Say:**
> "This is the per-ratio drilldown. The definition and formula are right there at the top — MidFirst's display is non-tax-equivalent. The UBPR version is tax-equivalent; expect a 5 to 15 basis point gap depending on muni mix."

**Do:** Move cursor to the trend chart.

**Say:**
> "The trend chart shows eight quarters. MidFirst is the heavier blue line on the bottom; the four peers are the thinner gray lines above. You can see MidFirst's NIM has been stable around 2.85 to 2.95% — basically flat through the rate cycle. The peer band moved more — Frost especially compressed about 20 basis points from 2024-Q1 to 2025-Q4 as deposit costs caught up."

**Do:** Scroll to the peer distribution strip plot.

**Say:**
> "Below the trend is a peer distribution strip plot for the latest quarter. Each dot is one bank. MidFirst is the dark blue dot on the far left — fifth out of five on NIM. That's the kind of thing you want to surface explicitly in a peer review, not bury in a footnote."

---

### 3:10 — 3:40 · Workbook download

**Do:** Click *← Matrix* to go back. Point at the *Download workbook (.xlsx)* link in the top right.

**Say:**
> "There's also an Excel comp workbook download. It regenerates every night from the same source data — anchor versus peer tabs, one sheet per ratio category, a restatement log, methodology notes. The point is that analysts live in Excel; the dashboard is for the quick read, the workbook is for the deep dive."

---

### 3:40 — 4:35 · Engineering tour

**Do:** Switch to the GitHub repo tab. Scroll to the `ARCHITECTURE.md` system diagram.

**Say:**
> "On the engineering side — the pipeline is Python, the dashboard is Next.js, the database is Supabase Postgres, and it's all wired through GitHub Actions for the nightly ingest. One design choice I want to call out: every ratio has two sources of truth that have to stay in lock-step — a row in the `ratio_defs` table for the human-readable spec, and a Python handler for the executable code. A contract test walks the registry every CI run and fails if they drift. That means I can't ship a ratio that's documented but not computed, or computed but not documented."

**Do:** Scroll down to the *Restatement detector* section in ARCHITECTURE.md.

**Say:**
> "The other thing worth calling out — the restatement detector you saw earlier. When FDIC re-publishes a quarter, the ingest compares incoming values against what's stored, flips a `restated` flag on the affected rows, and writes an audit row to `quality_log`. The dashboard joins those server-side and renders the `r` superscript automatically. No manual flagging."

---

### 4:35 — 5:00 · Close

**Do:** Switch back to the matrix tab. Cursor off-screen.

**Say:**
> "That's Peerbench. Source is on GitHub at github.com/ConnorTipton/Peerbench — README has a live link and install instructions if you want to clone it. Thanks for watching."

---

## After recording

- Trim head/tail silence.
- Add a 1-frame title card if Loom UI doesn't already overlay the title.
- Replace this script's reference in `README.md` with the Loom URL (search for "TODO Loom" — there isn't one yet; add when you're happy with the take).
- Once the Loom is shareable, add the URL to the "Live demo" section of `README.md`.

## Reshoot triggers

If any of these change, the script needs a refresh:

- Ratio count changes (currently 29 visible after the `top_loan_cat` hide).
- Anchor changes from MidFirst.
- Peer set changes (currently Bank OZK, BOK Financial, First-Citizens, Frost).
- Heat-map coloring rules change (currently quartile-based with per-ratio direction).
- The `r` superscript story breaks (the live demo currently shows a restatement on MidFirst NIM 2025-Q4 from a 2026-05-20 ingest).
