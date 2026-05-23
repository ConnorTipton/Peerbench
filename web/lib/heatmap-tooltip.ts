/*
 * Quartile-cell tooltip copy generator. Pure helpers; no rendering.
 *
 * Used by ratio-matrix.tsx to compose the 3-line tooltip body on cells
 * that fall in the top or bottom quartile of the visible peer set
 * (Sprint 2 PR-F). Line 2 is composed in the component because it
 * needs render-time `formatRatio()` calls against the cell value and
 * peer median.
 *
 * Quartile-bucket semantics (mirrors `bucketForCell` in heatmap.ts):
 *   - "top" = green tint (value-direction-aware: above q3 when
 *     higher_is_positive, below q1 when higher_is_negative).
 *   - "bottom" = red tint (the inverse).
 *
 * Convention for the rank line: describe the RAW VALUE position
 * ("Top quartile by value" / "Bottom quartile by value"). This is what
 * an analyst expects to read off a ratio matrix. The directional
 * meaning of the tint is then explained on line 3.
 *
 * Translation table (bucket × direction → value position):
 *   top + higher_is_positive    → value in top quartile
 *   bottom + higher_is_positive → value in bottom quartile
 *   top + higher_is_negative    → value in bottom quartile (low = good)
 *   bottom + higher_is_negative → value in top quartile (high = bad)
 *
 * `direction === "neutral"` should not reach this function — neutral
 * ratios resolve to bucket "none" in `bucketForCell` and the matrix
 * never renders the indicator. Defensive fallback returns empty
 * strings so a misuse degrades to a silent (but valid) tooltip rather
 * than a runtime crash.
 */

import type { RatioDirection } from "@/lib/heatmap-directions";

export type QuartileBucket = "top" | "bottom";

export type RankDescription = {
  rankLine: string;
  directionLine: string;
};

export function describeRank(
  bucket: QuartileBucket,
  direction: RatioDirection,
  ratioName: string,
): RankDescription {
  const name = ratioName.trim();
  if (!name || direction === "neutral") {
    return { rankLine: "", directionLine: "" };
  }

  // Map (bucket, direction) → raw-value quartile position.
  const valueInTopQuartile =
    (bucket === "top" && direction === "higher_is_positive") ||
    (bucket === "bottom" && direction === "higher_is_negative");

  const rankLine = valueInTopQuartile
    ? `Top quartile for ${name}`
    : `Bottom quartile for ${name}`;

  const directionLine = composeDirectionLine(bucket, direction, name);
  return { rankLine, directionLine };
}

function composeDirectionLine(
  bucket: QuartileBucket,
  direction: RatioDirection,
  name: string,
): string {
  // The leading clause names the direction; the trailing clause explains
  // what the tint says about the cell's value relative to the visible
  // peer set. "75% of the visible peer set" matches the per-render
  // quartile cutoff semantics (top quartile = strictly above q3 across
  // the non-suppressed peer values).
  if (direction === "higher_is_positive") {
    return bucket === "top"
      ? `Higher ${name} is positive — green tint means stronger than at least 75% of the visible peer set.`
      : `Higher ${name} is positive — red tint means weaker than at least 75% of the visible peer set.`;
  }
  // higher_is_negative
  return bucket === "top"
    ? `Higher ${name} is negative — green tint means lower than at least 75% of the visible peer set (better).`
    : `Higher ${name} is negative — red tint means higher than at least 75% of the visible peer set (worse).`;
}
