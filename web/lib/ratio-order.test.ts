import { describe, expect, it } from "vitest";

import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  RATIO_ORDER,
} from "@/lib/ratio-order";

describe("CATEGORY_ORDER", () => {
  it("contains the 7 RatioCategory values in the analyst-facing order", () => {
    expect(CATEGORY_ORDER).toEqual([
      "profitability",
      "yields",
      "balance_sheet",
      "asset_quality",
      "capital",
      "concentration",
      "liquidity",
    ]);
  });

  it("has no duplicates", () => {
    expect(new Set(CATEGORY_ORDER).size).toBe(CATEGORY_ORDER.length);
  });
});

describe("CATEGORY_LABELS", () => {
  it("has a label for every category in CATEGORY_ORDER", () => {
    for (const cat of CATEGORY_ORDER) {
      expect(CATEGORY_LABELS[cat]).toBeTruthy();
    }
  });

  it("has the same number of keys as CATEGORY_ORDER", () => {
    expect(Object.keys(CATEGORY_LABELS)).toHaveLength(CATEGORY_ORDER.length);
  });
});

describe("RATIO_ORDER", () => {
  it("contains 30 ratio ids (the full Phase 1 ratio set)", () => {
    expect(RATIO_ORDER).toHaveLength(30);
  });

  it("has no duplicates", () => {
    expect(new Set(RATIO_ORDER).size).toBe(RATIO_ORDER.length);
  });

  it("uses post-CECL nomenclature: acl_* (never alll_*)", () => {
    for (const id of RATIO_ORDER) {
      expect(id).not.toMatch(/^alll/);
    }
    expect(RATIO_ORDER).toContain("acl_loans");
    expect(RATIO_ORDER).toContain("acl_npl");
  });
});
