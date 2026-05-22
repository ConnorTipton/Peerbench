/*
 * Pure helpers for ratio category collapse/expand. The component
 * (ratio-matrix.tsx) owns the collapsed-set state + URL sync; this module is
 * intentionally framework-free so the parsers stay easy to reason about — and
 * easy to unit-test once a JS test runner lands in the web/ subproject.
 *
 * Sort + collapse interaction (locked Sprint 2 PR-C):
 *   - Sort runs over ALL data rows (including those hidden by a collapsed
 *     category) so that re-expanding a section shows its rows already in
 *     the active sort order — no jump or re-sort flicker.
 *   - Collapse is therefore a pure render-time filter applied AFTER
 *     `sortWithinSections` in ratio-matrix.tsx.
 *
 * URL serialization: canonical CATEGORY_ORDER, comma-separated. Stable
 * regardless of toggle order so deep links are diff-friendly.
 */

import { CATEGORY_ORDER } from "@/lib/ratio-order";
import type { RatioCategory } from "@/types/db";

const VALID_CATEGORIES: ReadonlySet<RatioCategory> = new Set(CATEGORY_ORDER);

export function parseCollapsedParam(
  raw: string | undefined,
): ReadonlySet<RatioCategory> {
  if (!raw) return new Set();
  const out = new Set<RatioCategory>();
  for (const part of raw.split(",")) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    if (VALID_CATEGORIES.has(trimmed as RatioCategory)) {
      out.add(trimmed as RatioCategory);
    }
  }
  return out;
}

export function serializeCollapsedParam(
  set: ReadonlySet<RatioCategory>,
): string | null {
  if (set.size === 0) return null;
  return CATEGORY_ORDER.filter((c) => set.has(c)).join(",");
}

export function toggleCategory(
  current: ReadonlySet<RatioCategory>,
  category: RatioCategory,
): ReadonlySet<RatioCategory> {
  const next = new Set(current);
  if (next.has(category)) {
    next.delete(category);
  } else {
    next.add(category);
  }
  return next;
}
