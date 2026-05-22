import { describe, expect, it } from "vitest";

import {
  EM_DASH,
  formatFactValue,
  formatRatio,
  formatReportDate,
} from "@/lib/format";

describe("formatRatio", () => {
  it("returns em-dash for null", () => {
    expect(formatRatio(null)).toBe(EM_DASH);
  });

  it("returns em-dash for undefined", () => {
    expect(formatRatio(undefined)).toBe(EM_DASH);
  });

  it("returns em-dash for NaN", () => {
    expect(formatRatio(Number.NaN)).toBe(EM_DASH);
  });

  it("returns em-dash for Infinity", () => {
    expect(formatRatio(Number.POSITIVE_INFINITY)).toBe(EM_DASH);
    expect(formatRatio(Number.NEGATIVE_INFINITY)).toBe(EM_DASH);
  });

  it("formats a positive fraction as a percentage with two decimals", () => {
    expect(formatRatio(0.1234)).toBe("12.34%");
  });

  it("formats zero as 0.00%", () => {
    expect(formatRatio(0)).toBe("0.00%");
  });

  it("wraps negatives in parentheses (no minus sign per design.md)", () => {
    expect(formatRatio(-0.1234)).toBe("(12.34%)");
    expect(formatRatio(-0.1234)).not.toContain("-");
  });

  it("rounds to two decimal places", () => {
    expect(formatRatio(0.12345)).toBe("12.35%");
    expect(formatRatio(0.12344)).toBe("12.34%");
  });
});

describe("formatFactValue", () => {
  it("returns em-dash for null/undefined/NaN", () => {
    expect(formatFactValue(null)).toBe(EM_DASH);
    expect(formatFactValue(undefined)).toBe(EM_DASH);
    expect(formatFactValue(Number.NaN)).toBe(EM_DASH);
  });

  it("formats positive integers with US thousands separators", () => {
    expect(formatFactValue(1234567)).toBe("1,234,567");
  });

  it("formats zero as 0", () => {
    expect(formatFactValue(0)).toBe("0");
  });

  it("wraps negatives in parentheses with no minus sign", () => {
    expect(formatFactValue(-1234567)).toBe("(1,234,567)");
    expect(formatFactValue(-1234567)).not.toContain("-");
  });

  it("rounds fractional inputs to whole numbers", () => {
    expect(formatFactValue(1234.6)).toBe("1,235");
    expect(formatFactValue(1234.4)).toBe("1,234");
  });
});

describe("formatReportDate", () => {
  it("returns the date portion of an ISO date string", () => {
    expect(formatReportDate("2025-12-31")).toBe("2025-12-31");
  });

  it("trims a timestamp to its date portion", () => {
    expect(formatReportDate("2025-12-31T00:00:00.000Z")).toBe("2025-12-31");
  });
});
