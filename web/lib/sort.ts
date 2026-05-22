/*
 * Pure helpers for per-peer column sort. The component (ratio-matrix.tsx)
 * owns sorting state + URL sync; this module is intentionally framework-free
 * so the partitioner and parsers stay easy to reason about — and easy to
 * unit-test once a JS test runner lands in the web/ subproject.
 *
 * Sort semantics (confirmed Sprint 2 PR-B):
 *   - Rows are ratios grouped by category. Columns are peer institutions.
 *   - Clicking a peer header sorts ratio rows by that peer's value, but
 *     section dividers act as barriers — sort happens within each section,
 *     not globally. Section ordering is preserved.
 *   - Cycle on the active column: asc → desc → none. Clicking a new column
 *     starts at asc (matches the locked Sprint 2 plan).
 *   - Nulls always sort to the bottom regardless of direction so blank /
 *     suppressed cells don't masquerade as 0 or huge.
 */

export type SortDir = "asc" | "desc";
export type SortState = { cert: number; dir: SortDir } | null;

const VALID_DIRS: ReadonlySet<string> = new Set(["asc", "desc"]);

export function parseSortParam(
  raw: string | undefined,
  validCerts: readonly number[],
): SortState {
  if (!raw) return null;
  const [certPart, dirPart] = raw.split(":");
  if (!certPart || !dirPart) return null;
  const cert = Number.parseInt(certPart, 10);
  if (!Number.isFinite(cert) || !validCerts.includes(cert)) return null;
  if (!VALID_DIRS.has(dirPart)) return null;
  return { cert, dir: dirPart as SortDir };
}

export function serializeSortParam(state: SortState): string | null {
  return state ? `${state.cert}:${state.dir}` : null;
}

export function nextSortState(current: SortState, cert: number): SortState {
  if (current?.cert !== cert) return { cert, dir: "asc" };
  if (current.dir === "asc") return { cert, dir: "desc" };
  return null;
}

export function compareValues(
  a: number | null,
  b: number | null,
  dir: SortDir,
): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return dir === "asc" ? a - b : b - a;
}

// Sorts data rows within each section block. Section rows act as barriers:
// section order is preserved, and data rows never cross a section boundary.
// Uses Array.prototype.sort which is guaranteed stable in ES2019+, so two
// data rows with equal compare values retain their input order.
export function sortWithinSections<R>(
  rows: readonly R[],
  isSection: (r: R) => boolean,
  getValue: (r: R) => number | null,
  dir: SortDir,
): R[] {
  const out: R[] = [];
  let buffer: R[] = [];
  const flush = () => {
    if (buffer.length === 0) return;
    buffer.sort((a, b) => compareValues(getValue(a), getValue(b), dir));
    out.push(...buffer);
    buffer = [];
  };
  for (const r of rows) {
    if (isSection(r)) {
      flush();
      out.push(r);
    } else {
      buffer.push(r);
    }
  }
  flush();
  return out;
}
