import { describe, expect, it } from "vitest";

import {
  compareValues,
  nextSortState,
  parseSortParam,
  serializeSortParam,
  sortWithinSections,
  type SortState,
} from "@/lib/sort";

const VALID_CERTS = [4063, 4214, 5510, 6384, 24387] as const;

describe("parseSortParam", () => {
  it("returns null for undefined", () => {
    expect(parseSortParam(undefined, VALID_CERTS)).toBeNull();
  });

  it("returns null for empty string", () => {
    expect(parseSortParam("", VALID_CERTS)).toBeNull();
  });

  it("parses a valid cert:asc pair", () => {
    expect(parseSortParam("4063:asc", VALID_CERTS)).toEqual({
      cert: 4063,
      dir: "asc",
    });
  });

  it("parses a valid cert:desc pair", () => {
    expect(parseSortParam("4214:desc", VALID_CERTS)).toEqual({
      cert: 4214,
      dir: "desc",
    });
  });

  it("returns null for an unknown cert", () => {
    expect(parseSortParam("9999:asc", VALID_CERTS)).toBeNull();
  });

  it("returns null for an invalid direction", () => {
    expect(parseSortParam("4063:sideways", VALID_CERTS)).toBeNull();
  });

  it("returns null for malformed input (no colon)", () => {
    expect(parseSortParam("4063asc", VALID_CERTS)).toBeNull();
  });

  it("returns null for non-numeric cert", () => {
    expect(parseSortParam("foo:asc", VALID_CERTS)).toBeNull();
  });

  it("returns null for missing cert side", () => {
    expect(parseSortParam(":asc", VALID_CERTS)).toBeNull();
  });

  it("returns null for missing dir side", () => {
    expect(parseSortParam("4063:", VALID_CERTS)).toBeNull();
  });
});

describe("serializeSortParam", () => {
  it("returns null for null state", () => {
    expect(serializeSortParam(null)).toBeNull();
  });

  it("serializes a state to cert:dir", () => {
    expect(serializeSortParam({ cert: 4063, dir: "desc" })).toBe("4063:desc");
  });

  it("round-trips with parseSortParam", () => {
    const original: SortState = { cert: 4063, dir: "asc" };
    const serialized = serializeSortParam(original);
    expect(serialized).not.toBeNull();
    expect(parseSortParam(serialized ?? undefined, VALID_CERTS)).toEqual(
      original,
    );
  });
});

describe("nextSortState", () => {
  it("none → asc on first click", () => {
    expect(nextSortState(null, 4063)).toEqual({ cert: 4063, dir: "asc" });
  });

  it("asc → desc on second click on same column", () => {
    expect(nextSortState({ cert: 4063, dir: "asc" }, 4063)).toEqual({
      cert: 4063,
      dir: "desc",
    });
  });

  it("desc → none on third click on same column", () => {
    expect(nextSortState({ cert: 4063, dir: "desc" }, 4063)).toBeNull();
  });

  it("clicking a different column restarts at asc on that column", () => {
    expect(nextSortState({ cert: 4063, dir: "desc" }, 4214)).toEqual({
      cert: 4214,
      dir: "asc",
    });
  });
});

describe("compareValues", () => {
  it("both null sort equal", () => {
    expect(compareValues(null, null, "asc")).toBe(0);
  });

  it("null sorts after a value in asc", () => {
    // Positive return → first argument sorts after second.
    expect(compareValues(null, 5, "asc")).toBeGreaterThan(0);
    expect(compareValues(5, null, "asc")).toBeLessThan(0);
  });

  it("null sorts after a value in desc too (nulls always last)", () => {
    expect(compareValues(null, 5, "desc")).toBeGreaterThan(0);
    expect(compareValues(5, null, "desc")).toBeLessThan(0);
  });

  it("asc orders ascending numeric", () => {
    expect(compareValues(1, 2, "asc")).toBeLessThan(0);
    expect(compareValues(2, 1, "asc")).toBeGreaterThan(0);
    expect(compareValues(1, 1, "asc")).toBe(0);
  });

  it("desc orders descending numeric", () => {
    expect(compareValues(1, 2, "desc")).toBeGreaterThan(0);
    expect(compareValues(2, 1, "desc")).toBeLessThan(0);
  });
});

describe("sortWithinSections", () => {
  type Row =
    | { kind: "section"; id: string }
    | { kind: "data"; id: string; value: number | null };

  const isSection = (r: Row) => r.kind === "section";
  const getValue = (r: Row) => (r.kind === "data" ? r.value : null);

  it("preserves section barriers; sorts within sections only", () => {
    const rows: Row[] = [
      { kind: "section", id: "s1" },
      { kind: "data", id: "a", value: 3 },
      { kind: "data", id: "b", value: 1 },
      { kind: "section", id: "s2" },
      { kind: "data", id: "c", value: 4 },
      { kind: "data", id: "d", value: 2 },
    ];
    const out = sortWithinSections(rows, isSection, getValue, "asc");
    expect(out.map((r) => r.id)).toEqual(["s1", "b", "a", "s2", "d", "c"]);
  });

  it("sorts desc within sections", () => {
    const rows: Row[] = [
      { kind: "section", id: "s1" },
      { kind: "data", id: "a", value: 3 },
      { kind: "data", id: "b", value: 1 },
      { kind: "data", id: "c", value: 5 },
    ];
    const out = sortWithinSections(rows, isSection, getValue, "desc");
    expect(out.map((r) => r.id)).toEqual(["s1", "c", "a", "b"]);
  });

  it("places nulls at the bottom of each section regardless of direction", () => {
    const rows: Row[] = [
      { kind: "section", id: "s1" },
      { kind: "data", id: "a", value: 3 },
      { kind: "data", id: "b", value: null },
      { kind: "data", id: "c", value: 1 },
    ];
    expect(
      sortWithinSections(rows, isSection, getValue, "asc").map((r) => r.id),
    ).toEqual(["s1", "c", "a", "b"]);
    expect(
      sortWithinSections(rows, isSection, getValue, "desc").map((r) => r.id),
    ).toEqual(["s1", "a", "c", "b"]);
  });

  it("preserves input order for equal values (stable sort)", () => {
    const rows: Row[] = [
      { kind: "section", id: "s1" },
      { kind: "data", id: "a", value: 1 },
      { kind: "data", id: "b", value: 1 },
      { kind: "data", id: "c", value: 1 },
    ];
    expect(
      sortWithinSections(rows, isSection, getValue, "asc").map((r) => r.id),
    ).toEqual(["s1", "a", "b", "c"]);
  });

  it("handles a section with no data rows", () => {
    const rows: Row[] = [
      { kind: "section", id: "s1" },
      { kind: "section", id: "s2" },
      { kind: "data", id: "a", value: 1 },
    ];
    expect(
      sortWithinSections(rows, isSection, getValue, "asc").map((r) => r.id),
    ).toEqual(["s1", "s2", "a"]);
  });

  it("handles an empty list", () => {
    expect(sortWithinSections<Row>([], isSection, getValue, "asc")).toEqual([]);
  });

  it("handles data rows before any section (initial buffer flushes correctly)", () => {
    const rows: Row[] = [
      { kind: "data", id: "a", value: 2 },
      { kind: "data", id: "b", value: 1 },
      { kind: "section", id: "s1" },
      { kind: "data", id: "c", value: 3 },
    ];
    expect(
      sortWithinSections(rows, isSection, getValue, "asc").map((r) => r.id),
    ).toEqual(["b", "a", "s1", "c"]);
  });
});
