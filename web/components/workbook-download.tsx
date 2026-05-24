/**
 * Header download surface for the daily-regenerated Excel comp workbook.
 *
 * Server component — fetches the manifest at request time, returns null when
 * absent (first-run, outage, malformed) so the dashboard degrades to today's
 * behavior. Verified by workbook-manifest.test.ts.
 */

import { formatRelativeDate } from "@/lib/format";
import { fetchWorkbookManifest } from "@/lib/workbook-manifest";

export async function WorkbookDownload() {
  const manifest = await fetchWorkbookManifest();
  if (!manifest) return null;
  return (
    <div className="flex flex-col items-end gap-0.5">
      <a
        href={manifest.url}
        className="text-table-data text-accent hover:underline"
        download
      >
        Download workbook (.xlsx)
      </a>
      <span className="text-table-data text-text-tertiary">
        Updated {formatRelativeDate(manifest.generatedAt)}
      </span>
    </div>
  );
}
