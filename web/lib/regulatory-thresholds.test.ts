import { describe, expect, it } from "vitest";

import {
  CRE_GROWTH_GATE_FOOTNOTE,
  REGULATORY_CITATIONS,
  resolveThreshold,
} from "@/lib/regulatory-thresholds";
import type { RatioDef } from "@/types/db";

function makeDef(
  overrides: Partial<RatioDef> & Pick<RatioDef, "ratio_id">,
): RatioDef {
  return {
    ratio_id: overrides.ratio_id,
    display_name: overrides.display_name ?? overrides.ratio_id,
    category: overrides.category ?? "concentration",
    numerator_formula: overrides.numerator_formula ?? "",
    denominator_formula: overrides.denominator_formula ?? "",
    annualize: overrides.annualize ?? false,
    avg_or_eop: overrides.avg_or_eop ?? "EOP",
    fdic_precomputed_code: overrides.fdic_precomputed_code ?? null,
    ubpr_concept: overrides.ubpr_concept ?? null,
    regulatory_threshold: overrides.regulatory_threshold ?? null,
    suppress_when: overrides.suppress_when ?? null,
    notes: overrides.notes ?? null,
  };
}

describe("resolveThreshold — cre_rbc two-tier", () => {
  const cre = makeDef({
    ratio_id: "cre_rbc",
    regulatory_threshold: {
      amber_pct: 300,
      red_pct: 400,
      amber_growth_pct_36mo: 50,
    },
  });

  it("returns null when value is below amber (e.g., 2.50 = 250%)", () => {
    expect(resolveThreshold(cre, 2.5)).toBeNull();
  });

  it("returns amber when value equals the 300% boundary (3.00)", () => {
    expect(resolveThreshold(cre, 3.0)).toEqual({
      level: "amber",
      threshold_pct: 300,
      citation: REGULATORY_CITATIONS.cre_rbc,
      footnote: CRE_GROWTH_GATE_FOOTNOTE,
    });
  });

  it("returns amber when value is between 300% and 400%", () => {
    expect(resolveThreshold(cre, 3.5)?.level).toBe("amber");
  });

  it("returns red when value equals the 400% boundary (4.00)", () => {
    expect(resolveThreshold(cre, 4.0)).toEqual({
      level: "red",
      threshold_pct: 400,
      citation: REGULATORY_CITATIONS.cre_rbc,
      footnote: CRE_GROWTH_GATE_FOOTNOTE,
    });
  });

  it("returns red for values above 400%", () => {
    expect(resolveThreshold(cre, 4.5)?.level).toBe("red");
  });

  it("attaches the cre_rbc growth-gate footnote on both amber and red", () => {
    expect(resolveThreshold(cre, 3.5)?.footnote).toBe(CRE_GROWTH_GATE_FOOTNOTE);
    expect(resolveThreshold(cre, 4.5)?.footnote).toBe(CRE_GROWTH_GATE_FOOTNOTE);
  });
});

describe("resolveThreshold — single-tier amber ratios", () => {
  const cases: { ratioId: string; amberPct: number; tripValue: number }[] = [
    { ratioId: "cd_rbc", amberPct: 100, tripValue: 1.0 },
    { ratioId: "brokered_dep", amberPct: 10, tripValue: 0.1 },
    { ratioId: "uninsured_dep", amberPct: 50, tripValue: 0.5 },
    { ratioId: "htm_loss_t1", amberPct: 25, tripValue: 0.25 },
  ];

  for (const { ratioId, amberPct, tripValue } of cases) {
    it(`${ratioId}: trips amber at exactly ${amberPct}%`, () => {
      const def = makeDef({
        ratio_id: ratioId,
        regulatory_threshold: { amber_pct: amberPct },
      });
      expect(resolveThreshold(def, tripValue)).toEqual({
        level: "amber",
        threshold_pct: amberPct,
        citation: REGULATORY_CITATIONS[ratioId],
        footnote: undefined,
      });
    });

    it(`${ratioId}: stays null just below threshold`, () => {
      const def = makeDef({
        ratio_id: ratioId,
        regulatory_threshold: { amber_pct: amberPct },
      });
      expect(resolveThreshold(def, tripValue - 0.001)).toBeNull();
    });

    it(`${ratioId}: never escalates to red (no red_pct key)`, () => {
      const def = makeDef({
        ratio_id: ratioId,
        regulatory_threshold: { amber_pct: amberPct },
      });
      // Even at 10x the amber threshold, single-tier ratios stay amber.
      expect(resolveThreshold(def, tripValue * 10)?.level).toBe("amber");
    });
  }
});

describe("resolveThreshold — capital ratios are intentionally not flagged", () => {
  // Capital ratios carry min_well_capitalized JSONB but no amber_pct — by
  // design they don't participate in the concentration-risk amber/red layer.
  const tier1 = makeDef({
    ratio_id: "tier1_rbc",
    category: "capital",
    regulatory_threshold: { min_well_capitalized: 8.0 },
  });
  it("returns null even at very low capital ratios", () => {
    expect(resolveThreshold(tier1, 0.04)).toBeNull();
  });
});

describe("resolveThreshold — defensive cases", () => {
  it("returns null when value is null", () => {
    const def = makeDef({
      ratio_id: "cre_rbc",
      regulatory_threshold: { amber_pct: 300, red_pct: 400 },
    });
    expect(resolveThreshold(def, null)).toBeNull();
  });

  it("returns null when value is NaN", () => {
    const def = makeDef({
      ratio_id: "cre_rbc",
      regulatory_threshold: { amber_pct: 300 },
    });
    expect(resolveThreshold(def, Number.NaN)).toBeNull();
  });

  it("returns null when regulatory_threshold is missing", () => {
    const def = makeDef({
      ratio_id: "cre_rbc",
      regulatory_threshold: null,
    });
    expect(resolveThreshold(def, 5.0)).toBeNull();
  });

  it("returns null when ratio_id has no citation entry", () => {
    const def = makeDef({
      ratio_id: "nim",
      regulatory_threshold: { amber_pct: 5 },
    });
    expect(resolveThreshold(def, 0.1)).toBeNull();
  });

  it("ignores non-numeric values in the JSONB", () => {
    const def = makeDef({
      ratio_id: "cre_rbc",
      regulatory_threshold: { amber_pct: "not a number", red_pct: 400 },
    });
    expect(resolveThreshold(def, 3.5)).toBeNull();
    expect(resolveThreshold(def, 4.5)?.level).toBe("red");
  });
});
