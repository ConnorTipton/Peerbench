import { AnchorSelect } from "@/components/anchor-select";
import { RatioMatrix } from "@/components/ratio-matrix";
import { formatReportDate } from "@/lib/format";
import { getMatrixData } from "@/lib/queries";

const DEFAULT_ANCHOR_CERT = 4063; // MidFirst Bank

type SearchParams = { anchor?: string };

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { anchor } = await searchParams;
  const data = await getMatrixData();

  const requested = anchor ? Number.parseInt(anchor, 10) : NaN;
  const anchorCert =
    Number.isFinite(requested) && data.institutions.some((i) => i.cert === requested)
      ? requested
      : DEFAULT_ANCHOR_CERT;

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
        restatedKeys={data.restatedKeys}
        anchorCert={anchorCert}
      />
    </main>
  );
}
