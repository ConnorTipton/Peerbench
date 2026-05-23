import { describe, expect, test } from "vitest";

import { timeSeriesPointKey, type MatrixCell } from "@/lib/matrix-types";
import { buildTrendChartData, selectRecentQuarterIds } from "@/lib/ratio-series";
import type { Institution, Quarter } from "@/types/db";

describe("selectRecentQuarterIds", () => {
  test("dedupes a per-(cert, quarter) descending stream and caps at n", () => {
    // Realistic input: ordered DESC by quarter_id, one row per (cert, quarter).
    const rows = [
      { quarter_id: "2025-Q4" },
      { quarter_id: "2025-Q4" },
      { quarter_id: "2025-Q4" },
      { quarter_id: "2025-Q4" },
      { quarter_id: "2025-Q4" },
      { quarter_id: "2025-Q3" },
      { quarter_id: "2025-Q3" },
      { quarter_id: "2025-Q3" },
      { quarter_id: "2025-Q2" },
      { quarter_id: "2025-Q1" },
      { quarter_id: "2024-Q4" },
      { quarter_id: "2024-Q3" },
      { quarter_id: "2024-Q2" },
      { quarter_id: "2024-Q1" },
    ];
    expect(selectRecentQuarterIds(rows, 8)).toEqual([
      "2025-Q4",
      "2025-Q3",
      "2025-Q2",
      "2025-Q1",
      "2024-Q4",
      "2024-Q3",
      "2024-Q2",
      "2024-Q1",
    ]);
  });

  test("returns fewer than n distinct ids when input has fewer", () => {
    const rows = [
      { quarter_id: "2025-Q4" },
      { quarter_id: "2025-Q3" },
    ];
    expect(selectRecentQuarterIds(rows, 8)).toEqual(["2025-Q4", "2025-Q3"]);
  });

  test("returns empty array on empty input", () => {
    expect(selectRecentQuarterIds([], 8)).toEqual([]);
  });

  test("returns empty array when n=0", () => {
    const rows = [{ quarter_id: "2025-Q4" }];
    expect(selectRecentQuarterIds(rows, 0)).toEqual([]);
  });

  test("preserves first-seen order even with interleaved duplicates", () => {
    // Defensive: even if the caller violated the DESC contract, dedupe
    // semantics are first-seen — the assertion is documented to be the
    // caller's responsibility, not this helper's.
    const rows = [
      { quarter_id: "2025-Q3" },
      { quarter_id: "2025-Q4" },
      { quarter_id: "2025-Q3" },
    ];
    expect(selectRecentQuarterIds(rows, 8)).toEqual(["2025-Q3", "2025-Q4"]);
  });
});

describe("buildTrendChartData", () => {
  // Minimal quarters + institutions for shape tests. Only the fields the
  // builder actually reads are populated.
  function makeQuarter(quarter_id: string): Quarter {
    return {
      quarter_id,
      year: Number(quarter_id.slice(0, 4)),
      quarter: Number(quarter_id.slice(-1)),
      report_date: `${quarter_id.slice(0, 4)}-03-31`,
      ingest_at: "2025-01-01T00:00:00Z",
      source: "fdic_api",
    };
  }
  function makeInst(cert: number, name: string): Institution {
    return {
      cert,
      rssd: null,
      name,
      charter: null,
      state: null,
      hq_city: null,
      asset_band: null,
      peer_tier: null,
      active: true,
      acquired_by: null,
    };
  }
  function makeCell(value: number | null): MatrixCell {
    return { value, data_quality: "ok" };
  }

  test("returns one row per quarter with a cert column per institution", () => {
    const quarters = [makeQuarter("2025-Q3"), makeQuarter("2025-Q4")];
    const institutions = [makeInst(4063, "MidFirst"), makeInst(8888, "Peer A")];
    const values = new Map<string, MatrixCell>([
      [timeSeriesPointKey(4063, "2025-Q3"), makeCell(0.034)],
      [timeSeriesPointKey(4063, "2025-Q4"), makeCell(0.036)],
      [timeSeriesPointKey(8888, "2025-Q3"), makeCell(0.029)],
      [timeSeriesPointKey(8888, "2025-Q4"), makeCell(0.031)],
    ]);
    expect(buildTrendChartData(quarters, institutions, values)).toEqual([
      { quarter_id: "2025-Q3", cert_4063: 0.034, cert_8888: 0.029 },
      { quarter_id: "2025-Q4", cert_4063: 0.036, cert_8888: 0.031 },
    ]);
  });

  test("missing cells render as null (chart treats null as a gap)", () => {
    const quarters = [makeQuarter("2025-Q3"), makeQuarter("2025-Q4")];
    const institutions = [makeInst(4063, "MidFirst")];
    const values = new Map<string, MatrixCell>([
      [timeSeriesPointKey(4063, "2025-Q4"), makeCell(0.036)],
    ]);
    expect(buildTrendChartData(quarters, institutions, values)).toEqual([
      { quarter_id: "2025-Q3", cert_4063: null },
      { quarter_id: "2025-Q4", cert_4063: 0.036 },
    ]);
  });

  test("cells with value=null render as null (suppressed / partial states)", () => {
    const quarters = [makeQuarter("2025-Q4")];
    const institutions = [makeInst(4063, "MidFirst"), makeInst(8888, "Peer A")];
    const values = new Map<string, MatrixCell>([
      [timeSeriesPointKey(4063, "2025-Q4"), makeCell(null)],
      [
        timeSeriesPointKey(8888, "2025-Q4"),
        { value: null, data_quality: "suppressed" },
      ],
    ]);
    expect(buildTrendChartData(quarters, institutions, values)).toEqual([
      { quarter_id: "2025-Q4", cert_4063: null, cert_8888: null },
    ]);
  });

  test("preserves quarter order from input (caller decides asc vs desc)", () => {
    const quarters = [makeQuarter("2025-Q4"), makeQuarter("2025-Q1")];
    const institutions = [makeInst(4063, "MidFirst")];
    const values = new Map<string, MatrixCell>([
      [timeSeriesPointKey(4063, "2025-Q1"), makeCell(0.030)],
      [timeSeriesPointKey(4063, "2025-Q4"), makeCell(0.036)],
    ]);
    expect(buildTrendChartData(quarters, institutions, values).map(r => r.quarter_id))
      .toEqual(["2025-Q4", "2025-Q1"]);
  });

  test("returns empty array on empty quarters input", () => {
    expect(
      buildTrendChartData([], [makeInst(4063, "MidFirst")], new Map()),
    ).toEqual([]);
  });
});
