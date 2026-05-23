/*
 * Pure helpers for the conditional-formatting heat map. The component
 * (ratio-matrix.tsx) owns the cell render path; this module is intentionally
 * framework-free so the quartile math + bucketing stay easy to reason about
 * and golden-testable.
 *
 * Heat-map semantics (locked Sprint 2 PR-D, per docs/design.md §Conditional formatting):
 *   - Quartile cutoffs are computed per ratio across the currently visible
 *     peer set. Direction-aware: higher NIM = top (green), higher efficiency
 *     ratio = bottom (red).
 *   - Quartile cutoffs MUST exclude data_quality === "suppressed" cells
 *     (e.g. a CBLR filer's tier1_rbc). Callers filter before passing values
 *     in — this module is value-agnostic.
 *   - Cells in the middle two quartiles get no tint.
 *   - Neutral-direction ratios (e.g. CRE concentration under regulatory-only
 *     flagging) never receive a quartile tint regardless of position.
 *
 * Boundary semantics: top quartile is strictly `> q3`; bottom is strictly
 * `< q1`. Values equal to a cutoff are middle — they bound the quartile but
 * are not inside it.
 *
 * MIN_VALUES_FOR_QUARTILES = 4. With <4 non-suppressed values (e.g. an all-
 * CBLR peer set queried for tier1_rbc), no cutoffs are produced and no
 * quartile tint renders. The matrix still shows regulatory amber/red where
 * applicable.
 */

export type Direction = "higher_is_positive" | "higher_is_negative" | "neutral";

export type Bucket = "top" | "middle" | "bottom" | "none";

export type QuartileCutoffs = {
  q1: number;
  median: number;
  q3: number;
};

const MIN_VALUES_FOR_QUARTILES = 4;

// Type-7 quartile (R default, equivalent to Excel's QUARTILE.INC):
// q-th quantile = sorted[ floor( (n-1)*q ) ] linearly interpolated to
// sorted[ ceil( (n-1)*q ) ].
// Median is q2 and travels alongside q1/q3 so the tooltip layer can read
// "vs peer median" without a second pass over the visible peer set.
export function computeQuartileCutoffs(
  values: readonly number[],
): QuartileCutoffs | null {
  const filtered = values.filter((v) => Number.isFinite(v));
  if (filtered.length < MIN_VALUES_FOR_QUARTILES) return null;
  const sorted = [...filtered].sort((a, b) => a - b);
  return {
    q1: quantile(sorted, 0.25),
    median: quantile(sorted, 0.5),
    q3: quantile(sorted, 0.75),
  };
}

function quantile(sorted: readonly number[], q: number): number {
  const idx = (sorted.length - 1) * q;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

export function bucketForCell(
  value: number | null,
  cutoffs: QuartileCutoffs | null,
  direction: Direction,
): Bucket {
  if (value === null || cutoffs === null || direction === "neutral") {
    return "none";
  }
  if (!Number.isFinite(value)) return "none";

  const isAboveQ3 = value > cutoffs.q3;
  const isBelowQ1 = value < cutoffs.q1;

  if (!isAboveQ3 && !isBelowQ1) return "middle";

  if (direction === "higher_is_positive") {
    return isAboveQ3 ? "top" : "bottom";
  }
  return isAboveQ3 ? "bottom" : "top";
}
