import { describe, expect, it } from "vitest";

import { describeRank } from "@/lib/heatmap-tooltip";

describe("describeRank — higher_is_positive (e.g., NIM, ROA, Tier 1 RBC)", () => {
  it("top bucket → top-quartile rank + positive direction line (green)", () => {
    const out = describeRank("top", "higher_is_positive", "NIM");
    expect(out.rankLine).toBe("Top quartile for NIM");
    expect(out.directionLine).toBe(
      "Higher NIM is positive — green tint means stronger than at least 75% of the visible peer set.",
    );
  });

  it("bottom bucket → bottom-quartile rank + positive direction line (red)", () => {
    const out = describeRank("bottom", "higher_is_positive", "ROA");
    expect(out.rankLine).toBe("Bottom quartile for ROA");
    expect(out.directionLine).toBe(
      "Higher ROA is positive — red tint means weaker than at least 75% of the visible peer set.",
    );
  });
});

describe("describeRank — higher_is_negative (e.g., efficiency ratio, NPL, NCO)", () => {
  it("top bucket → BOTTOM-quartile rank (low values are good) + negative direction line (green)", () => {
    const out = describeRank("top", "higher_is_negative", "Efficiency ratio");
    expect(out.rankLine).toBe("Bottom quartile for Efficiency ratio");
    expect(out.directionLine).toBe(
      "Higher Efficiency ratio is negative — green tint means lower than at least 75% of the visible peer set (better).",
    );
  });

  it("bottom bucket → TOP-quartile rank (high values are bad) + negative direction line (red)", () => {
    const out = describeRank("bottom", "higher_is_negative", "Efficiency ratio");
    expect(out.rankLine).toBe("Top quartile for Efficiency ratio");
    expect(out.directionLine).toBe(
      "Higher Efficiency ratio is negative — red tint means higher than at least 75% of the visible peer set (worse).",
    );
  });
});

describe("describeRank — defensive fallbacks", () => {
  it("returns empty strings for neutral direction (should never reach here in practice)", () => {
    expect(describeRank("top", "neutral", "CRE / RBC")).toEqual({
      rankLine: "",
      directionLine: "",
    });
    expect(describeRank("bottom", "neutral", "CRE / RBC")).toEqual({
      rankLine: "",
      directionLine: "",
    });
  });

  it("returns empty strings for empty ratio name", () => {
    expect(describeRank("top", "higher_is_positive", "")).toEqual({
      rankLine: "",
      directionLine: "",
    });
  });

  it("returns empty strings for whitespace-only ratio name", () => {
    expect(describeRank("bottom", "higher_is_negative", "   ")).toEqual({
      rankLine: "",
      directionLine: "",
    });
  });

  it("trims surrounding whitespace from the ratio name", () => {
    const out = describeRank("top", "higher_is_positive", "  NIM  ");
    expect(out.rankLine).toBe("Top quartile for NIM");
    expect(out.directionLine).toContain("Higher NIM is positive");
  });
});

// Mandatory golden test mirrors the PR-D pattern in heatmap.test.ts:
// exhaustive 2 buckets × 2 active directions matrix, one assertion per cell
// of the truth table. Catches a silent positive/negative wording flip.
describe("describeRank golden — 2 buckets × 2 directions truth table", () => {
  const cases: Array<{
    bucket: "top" | "bottom";
    direction: "higher_is_positive" | "higher_is_negative";
    expectedRank: string;
    expectedTint: "green" | "red";
    expectedComparator: "stronger" | "weaker" | "lower" | "higher";
  }> = [
    {
      bucket: "top",
      direction: "higher_is_positive",
      expectedRank: "Top quartile for X",
      expectedTint: "green",
      expectedComparator: "stronger",
    },
    {
      bucket: "bottom",
      direction: "higher_is_positive",
      expectedRank: "Bottom quartile for X",
      expectedTint: "red",
      expectedComparator: "weaker",
    },
    {
      bucket: "top",
      direction: "higher_is_negative",
      expectedRank: "Bottom quartile for X",
      expectedTint: "green",
      expectedComparator: "lower",
    },
    {
      bucket: "bottom",
      direction: "higher_is_negative",
      expectedRank: "Top quartile for X",
      expectedTint: "red",
      expectedComparator: "higher",
    },
  ];

  for (const c of cases) {
    it(`${c.bucket} + ${c.direction} → ${c.expectedRank} / ${c.expectedTint} tint / "${c.expectedComparator}" comparator`, () => {
      const out = describeRank(c.bucket, c.direction, "X");
      expect(out.rankLine).toBe(c.expectedRank);
      expect(out.directionLine).toContain(`${c.expectedTint} tint`);
      expect(out.directionLine).toContain(c.expectedComparator);
    });
  }
});
