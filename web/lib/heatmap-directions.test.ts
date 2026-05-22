import { describe, expect, it } from "vitest";

import {
  RATIO_DIRECTIONS,
  directionFor,
  type RatioDirection,
} from "@/lib/heatmap-directions";
import { RATIO_ORDER } from "@/lib/ratio-order";

describe("RATIO_DIRECTIONS", () => {
  it("covers every ratio in RATIO_ORDER 1:1", () => {
    const mapKeys = new Set(Object.keys(RATIO_DIRECTIONS));
    const orderSet = new Set(RATIO_ORDER);
    expect(mapKeys.size).toBe(orderSet.size);
    for (const id of RATIO_ORDER) {
      expect(mapKeys.has(id)).toBe(true);
    }
    for (const id of mapKeys) {
      expect(orderSet.has(id)).toBe(true);
    }
  });

  it("uses only the three documented direction values", () => {
    const valid: ReadonlySet<RatioDirection> = new Set([
      "higher_is_positive",
      "higher_is_negative",
      "neutral",
    ]);
    for (const [, dir] of Object.entries(RATIO_DIRECTIONS)) {
      expect(valid.has(dir)).toBe(true);
    }
  });

  it("flags concentration ratios (CRE, CD) as neutral — regulatory-only", () => {
    expect(RATIO_DIRECTIONS.cre_rbc).toBe("neutral");
    expect(RATIO_DIRECTIONS.cd_rbc).toBe("neutral");
  });

  it("flags funding-risk heuristics (uninsured, brokered, HTM loss) as higher_is_negative", () => {
    expect(RATIO_DIRECTIONS.uninsured_dep).toBe("higher_is_negative");
    expect(RATIO_DIRECTIONS.brokered_dep).toBe("higher_is_negative");
    expect(RATIO_DIRECTIONS.htm_loss_t1).toBe("higher_is_negative");
  });

  it("flags efficiency ratio + NPL + NCO + cost of funds as higher_is_negative", () => {
    expect(RATIO_DIRECTIONS.eff_ratio).toBe("higher_is_negative");
    expect(RATIO_DIRECTIONS.npl_ratio).toBe("higher_is_negative");
    expect(RATIO_DIRECTIONS.nco_ratio).toBe("higher_is_negative");
    expect(RATIO_DIRECTIONS.cost_funds).toBe("higher_is_negative");
  });

  it("flags profitability + capital ratios as higher_is_positive", () => {
    expect(RATIO_DIRECTIONS.nim).toBe("higher_is_positive");
    expect(RATIO_DIRECTIONS.roa).toBe("higher_is_positive");
    expect(RATIO_DIRECTIONS.roe).toBe("higher_is_positive");
    expect(RATIO_DIRECTIONS.tier1_lev).toBe("higher_is_positive");
    expect(RATIO_DIRECTIONS.tier1_rbc).toBe("higher_is_positive");
    expect(RATIO_DIRECTIONS.cet1).toBe("higher_is_positive");
  });
});

describe("directionFor", () => {
  it("returns the mapped direction for a known ratio_id", () => {
    expect(directionFor("nim")).toBe("higher_is_positive");
    expect(directionFor("eff_ratio")).toBe("higher_is_negative");
    expect(directionFor("cre_rbc")).toBe("neutral");
  });

  it("defaults to neutral for an unknown ratio_id", () => {
    expect(directionFor("does_not_exist")).toBe("neutral");
  });
});
