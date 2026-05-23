import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchWorkbookManifest } from "./workbook-manifest";

const VALID_MANIFEST = {
  url: "https://abc.supabase.co/storage/v1/object/public/peerbench-exports/latest.xlsx",
  generated_at: "2026-05-23T03:07:42Z",
  quarter_id: "2025-Q4",
  anchor_cert: 4063,
  size_bytes: 62513,
};

describe("fetchWorkbookManifest", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://abc.supabase.co");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("returns parsed manifest on 200", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(VALID_MANIFEST), { status: 200 }),
    );
    const m = await fetchWorkbookManifest();
    expect(m).toEqual({
      url: VALID_MANIFEST.url,
      generatedAt: VALID_MANIFEST.generated_at,
      quarterId: VALID_MANIFEST.quarter_id,
      sizeBytes: VALID_MANIFEST.size_bytes,
    });
  });

  it("returns null on 404", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("", { status: 404 }));
    expect(await fetchWorkbookManifest()).toBeNull();
  });

  it("returns null on AbortError (timeout)", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(global, "fetch").mockRejectedValue(
      Object.assign(new Error("aborted"), { name: "AbortError" }),
    );
    expect(await fetchWorkbookManifest()).toBeNull();
  });

  it("returns null on network error", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(global, "fetch").mockRejectedValue(new TypeError("fetch failed"));
    expect(await fetchWorkbookManifest()).toBeNull();
  });

  it("returns null on malformed JSON", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response("not json", { status: 200 }),
    );
    expect(await fetchWorkbookManifest()).toBeNull();
  });

  it("returns null when required field is missing", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { generated_at: _generated_at, ...incomplete } = VALID_MANIFEST;
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(incomplete), { status: 200 }),
    );
    expect(await fetchWorkbookManifest()).toBeNull();
  });
});
