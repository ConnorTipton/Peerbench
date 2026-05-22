import { AnchorSelect } from "@/components/anchor-select";
import { RatioMatrix } from "@/components/ratio-matrix";
import { formatReportDate } from "@/lib/format";
import { getMatrixData } from "@/lib/queries";
import { parseSortParam } from "@/lib/sort";

const DEFAULT_ANCHOR_CERT = 4063; // MidFirst Bank

// Next.js represents repeated query-string keys as `string[]`. Acknowledge
// that at the type level and normalize to the first value at the boundary —
// downstream parsers stay pure (string | undefined).
type SearchParams = { anchor?: string | string[]; sort?: string | string[] };

function firstParam(raw: string | string[] | undefined): string | undefined {
  if (raw === undefined) return undefined;
  return Array.isArray(raw) ? raw[0] : raw;
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { anchor, sort } = await searchParams;
  const data = await getMatrixData();

  const anchorRaw = firstParam(anchor);
  const requested = anchorRaw ? Number.parseInt(anchorRaw, 10) : NaN;
  const anchorCert =
    Number.isFinite(requested) && data.institutions.some((i) => i.cert === requested)
      ? requested
      : DEFAULT_ANCHOR_CERT;

  const initialSort = parseSortParam(
    firstParam(sort),
    data.institutions.map((i) => i.cert),
  );

  return (
    <main className="flex h-dvh flex-col px-6 py-6">
      <header className="mb-4 flex items-baseline justify-between gap-4">
        <h1 className="text-page-title font-semibold text-primary">Peerbench</h1>
        <span className="text-body text-text-secondary">
          As of {formatReportDate(data.quarter.report_date)}
        </span>
      </header>
      <div className="mb-4">
        <AnchorSelect institutions={data.institutions} anchorCert={anchorCert} />
      </div>
      <RatioMatrix
        institutions={data.institutions}
        ratioGroups={data.ratioGroups}
        cells={data.cells}
        restatedDetails={data.restatedDetails}
        anchorCert={anchorCert}
        initialSort={initialSort}
      />
    </main>
  );
}
