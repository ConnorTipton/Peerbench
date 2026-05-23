import { describe, expect, it } from "vitest";

import {
  bucketForCell,
  computeQuartileCutoffs,
  type QuartileCutoffs,
} from "@/lib/heatmap";

describe("computeQuartileCutoffs", () => {
  it("returns null for empty array", () => {
    expect(computeQuartileCutoffs([])).toBeNull();
  });

  it("returns null for fewer than 4 finite values", () => {
    expect(computeQuartileCutoffs([10])).toBeNull();
    expect(computeQuartileCutoffs([10, 20])).toBeNull();
    expect(computeQuartileCutoffs([10, 20, 30])).toBeNull();
  });

  it("filters non-finite values before counting", () => {
    expect(computeQuartileCutoffs([10, 20, 30, Number.NaN])).toBeNull();
    expect(
      computeQuartileCutoffs([10, 20, 30, 40, Number.POSITIVE_INFINITY]),
    ).toEqual({ q1: 17.5, median: 25, q3: 32.5 });
  });

  it("computes q1=20, median=30, q3=40 for the canonical 5-value fixture [10,20,30,40,50]", () => {
    expect(computeQuartileCutoffs([10, 20, 30, 40, 50])).toEqual({
      q1: 20,
      median: 30,
      q3: 40,
    });
  });

  it("handles unsorted input", () => {
    expect(computeQuartileCutoffs([50, 10, 30, 20, 40])).toEqual({
      q1: 20,
      median: 30,
      q3: 40,
    });
  });

  it("uses Type-7 linear interpolation for 4 values [10,20,30,40]", () => {
    expect(computeQuartileCutoffs([10, 20, 30, 40])).toEqual({
      q1: 17.5,
      median: 25,
      q3: 32.5,
    });
  });

  it("handles all-equal values (q1 === median === q3)", () => {
    expect(computeQuartileCutoffs([5, 5, 5, 5])).toEqual({
      q1: 5,
      median: 5,
      q3: 5,
    });
  });
});

describe("bucketForCell", () => {
  const cutoffs: QuartileCutoffs = { q1: 20, median: 30, q3: 40 };

  describe("higher_is_positive (e.g., NIM, ROA, Tier 1 RBC)", () => {
    it("classifies value above q3 as top (green)", () => {
      expect(bucketForCell(50, cutoffs, "higher_is_positive")).toBe("top");
    });

    it("classifies value below q1 as bottom (red)", () => {
      expect(bucketForCell(10, cutoffs, "higher_is_positive")).toBe("bottom");
    });

    it("classifies q3 boundary as middle (strict >)", () => {
      expect(bucketForCell(40, cutoffs, "higher_is_positive")).toBe("middle");
    });

    it("classifies q1 boundary as middle (strict <)", () => {
      expect(bucketForCell(20, cutoffs, "higher_is_positive")).toBe("middle");
    });

    it("classifies the middle value as middle", () => {
      expect(bucketForCell(30, cutoffs, "higher_is_positive")).toBe("middle");
    });
  });

  describe("higher_is_negative (e.g., efficiency ratio, NPL, NCO)", () => {
    it("classifies value above q3 as bottom (red — high is bad)", () => {
      expect(bucketForCell(50, cutoffs, "higher_is_negative")).toBe("bottom");
    });

    it("classifies value below q1 as top (green — low is good)", () => {
      expect(bucketForCell(10, cutoffs, "higher_is_negative")).toBe("top");
    });
  });

  describe("neutral (e.g., CRE concentration, balance-sheet mix)", () => {
    it("returns none regardless of where value sits", () => {
      expect(bucketForCell(50, cutoffs, "neutral")).toBe("none");
      expect(bucketForCell(10, cutoffs, "neutral")).toBe("none");
      expect(bucketForCell(30, cutoffs, "neutral")).toBe("none");
    });
  });

  describe("edge cases", () => {
    it("returns none for null value", () => {
      expect(bucketForCell(null, cutoffs, "higher_is_positive")).toBe("none");
    });

    it("returns none for null cutoffs", () => {
      expect(bucketForCell(50, null, "higher_is_positive")).toBe("none");
    });

    it("returns none for non-finite value", () => {
      expect(
        bucketForCell(Number.NaN, cutoffs, "higher_is_positive"),
      ).toBe("none");
    });
  });
});

// Mandatory golden test per the locked Sprint 2 plan, PR-D lines 213–216:
// fixture of 5 values × 3 directions × inclusion of one suppressed cell →
// expected bucket per case. This is the cheapest defense against a silent
// direction flip later in the file.
describe("heat map golden — 5 peer cells, one suppressed, all 3 directions", () => {
  // Scenario: tier1_rbc across 5 peers. One peer is a CBLR filer whose cell is
  // suppressed (data_quality === "suppressed"). The matrix render path filters
  // suppressed cells out before computing quartile cutoffs — feeding them in
  // would skew the distribution (e.g. a sentinel NaN or stale prior value
  // would land in the wrong bucket).
  type Cell = {
    cert: number;
    value: number;
    data_quality: "ok" | "suppressed";
  };
  const peerCells: Cell[] = [
    { cert: 1001, value: 10, data_quality: "ok" },
    { cert: 1002, value: 20, data_quality: "ok" },
    { cert: 1003, value: 30, data_quality: "ok" },
    { cert: 1004, value: 40, data_quality: "ok" },
    { cert: 1005, value: 999, data_quality: "suppressed" }, // would skew if included
  ];

  const valuesForQuartile = peerCells
    .filter((c) => c.data_quality !== "suppressed")
    .map((c) => c.value);

  const cutoffs = computeQuartileCutoffs(valuesForQuartile);

  it("excludes the suppressed cell from cutoffs (4 non-suppressed values)", () => {
    expect(cutoffs).toEqual({ q1: 17.5, median: 25, q3: 32.5 });
  });

  it("higher_is_positive: highest peer is top, lowest is bottom, q-boundaries are middle", () => {
    expect(bucketForCell(40, cutoffs, "higher_is_positive")).toBe("top");
    expect(bucketForCell(30, cutoffs, "higher_is_positive")).toBe("middle");
    expect(bucketForCell(20, cutoffs, "higher_is_positive")).toBe("middle");
    expect(bucketForCell(10, cutoffs, "higher_is_positive")).toBe("bottom");
  });

  it("higher_is_negative: highest peer is bottom, lowest is top (inverse)", () => {
    expect(bucketForCell(40, cutoffs, "higher_is_negative")).toBe("bottom");
    expect(bucketForCell(30, cutoffs, "higher_is_negative")).toBe("middle");
    expect(bucketForCell(20, cutoffs, "higher_is_negative")).toBe("middle");
    expect(bucketForCell(10, cutoffs, "higher_is_negative")).toBe("top");
  });

  it("neutral: never tints regardless of position", () => {
    for (const v of [10, 20, 30, 40]) {
      expect(bucketForCell(v, cutoffs, "neutral")).toBe("none");
    }
  });
});
