/**
 * Server-only fetcher for the daily-uploaded workbook manifest.
 *
 * Reads `latest.json` from the public Supabase Storage bucket. All failure
 * modes (404, timeout, network, malformed JSON, wrong shape) return null so
 * the dashboard renders gracefully on first-run and during outages.
 *
 * The bucket is uploaded to by the daily-ingest GitHub Action.
 */

import "server-only";

export type WorkbookManifest = {
  url: string;
  generatedAt: string; // ISO-8601 UTC
  quarterId: string;
  sizeBytes: number;
};

const BUCKET = "peerbench-exports";
const TIMEOUT_MS = 3000;

function manifestUrl(): string {
  const base = process.env.NEXT_PUBLIC_SUPABASE_URL?.replace(/\/$/, "");
  if (!base) throw new Error("NEXT_PUBLIC_SUPABASE_URL is not set");
  return `${base}/storage/v1/object/public/${BUCKET}/latest.json`;
}

function parseManifest(raw: unknown): WorkbookManifest | null {
  if (typeof raw !== "object" || raw === null) return null;
  const r = raw as Record<string, unknown>;
  if (
    typeof r.url !== "string" ||
    typeof r.generated_at !== "string" ||
    typeof r.quarter_id !== "string" ||
    typeof r.size_bytes !== "number"
  ) {
    return null;
  }
  return {
    url: r.url,
    generatedAt: r.generated_at,
    quarterId: r.quarter_id,
    sizeBytes: r.size_bytes,
  };
}

export async function fetchWorkbookManifest(): Promise<WorkbookManifest | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(manifestUrl(), {
      signal: controller.signal,
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    let body: unknown;
    try {
      body = await res.json();
    } catch (err) {
      console.error("workbook-manifest: failed to parse JSON", err);
      return null;
    }
    const parsed = parseManifest(body);
    if (!parsed) {
      console.error("workbook-manifest: response did not match expected shape", body);
    }
    return parsed;
  } catch (err) {
    // AbortError, TypeError (network), etc — degrade silently.
    if ((err as Error).name !== "AbortError") {
      console.error("workbook-manifest: fetch failed", err);
    }
    return null;
  } finally {
    clearTimeout(timer);
  }
}
