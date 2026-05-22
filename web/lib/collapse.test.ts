import { describe, expect, it } from "vitest";

import {
  parseCollapsedParam,
  serializeCollapsedParam,
  toggleCategory,
} from "@/lib/collapse";
import { CATEGORY_ORDER } from "@/lib/ratio-order";
import type { RatioCategory } from "@/types/db";

describe("parseCollapsedParam", () => {
  it("returns empty set for undefined", () => {
    expect(parseCollapsedParam(undefined).size).toBe(0);
  });

  it("returns empty set for empty string", () => {
    expect(parseCollapsedParam("").size).toBe(0);
  });

  it("parses a single valid category", () => {
    const out = parseCollapsedParam("profitability");
    expect([...out]).toEqual(["profitability"]);
  });

  it("parses multiple valid comma-separated categories", () => {
    const out = parseCollapsedParam("profitability,yields,capital");
    expect(out.has("profitability")).toBe(true);
    expect(out.has("yields")).toBe(true);
    expect(out.has("capital")).toBe(true);
    expect(out.size).toBe(3);
  });

  it("silently drops unknown slugs (defensive against URL hand-edits)", () => {
    const out = parseCollapsedParam("profitability,foo,yields");
    expect(out.has("profitability")).toBe(true);
    expect(out.has("yields")).toBe(true);
    expect(out.size).toBe(2);
  });

  it("ignores empty segments from trailing/leading commas", () => {
    const out = parseCollapsedParam(",profitability,,yields,");
    expect(out.size).toBe(2);
  });

  it("collapses duplicate categories", () => {
    const out = parseCollapsedParam("profitability,profitability");
    expect(out.size).toBe(1);
  });

  it("returns empty set when only invalid slugs present", () => {
    expect(parseCollapsedParam("foo,bar").size).toBe(0);
  });
});

describe("serializeCollapsedParam", () => {
  it("returns null for empty set", () => {
    expect(serializeCollapsedParam(new Set())).toBeNull();
  });

  it("serializes in canonical CATEGORY_ORDER regardless of insertion order", () => {
    const reverseInsert: ReadonlySet<RatioCategory> = new Set<RatioCategory>([
      "liquidity",
      "yields",
      "profitability",
    ]);
    // Canonical order is profitability → yields → liquidity (per CATEGORY_ORDER).
    expect(serializeCollapsedParam(reverseInsert)).toBe(
      "profitability,yields,liquidity",
    );
  });

  it("round-trips with parseCollapsedParam", () => {
    const original = new Set<RatioCategory>(["profitability", "capital"]);
    const serialized = serializeCollapsedParam(original);
    expect(serialized).not.toBeNull();
    const parsed = parseCollapsedParam(serialized ?? undefined);
    expect([...parsed].sort()).toEqual([...original].sort());
  });

  it("serializes single category", () => {
    expect(serializeCollapsedParam(new Set<RatioCategory>(["yields"]))).toBe(
      "yields",
    );
  });
});

describe("toggleCategory", () => {
  it("adds an absent category", () => {
    const next = toggleCategory(new Set(), "profitability");
    expect(next.has("profitability")).toBe(true);
  });

  it("removes a present category", () => {
    const start: ReadonlySet<RatioCategory> = new Set<RatioCategory>([
      "profitability",
    ]);
    const next = toggleCategory(start, "profitability");
    expect(next.has("profitability")).toBe(false);
    expect(next.size).toBe(0);
  });

  it("returns a new Set (does not mutate the input)", () => {
    const start = new Set<RatioCategory>(["profitability"]);
    const next = toggleCategory(start, "yields");
    expect(next).not.toBe(start);
    expect(start.size).toBe(1);
    expect(next.size).toBe(2);
  });

  it("leaves other entries untouched", () => {
    const start = new Set<RatioCategory>(["profitability", "yields"]);
    const next = toggleCategory(start, "capital");
    expect(next.has("profitability")).toBe(true);
    expect(next.has("yields")).toBe(true);
    expect(next.has("capital")).toBe(true);
  });
});

describe("CATEGORY_ORDER (invariants)", () => {
  it("contains exactly the 7 RatioCategory values with no duplicates", () => {
    expect(CATEGORY_ORDER.length).toBe(7);
    expect(new Set(CATEGORY_ORDER).size).toBe(CATEGORY_ORDER.length);
  });
});
