import Link from "next/link";
import { notFound } from "next/navigation";

import { RatioDistribution, type DistributionPoint } from "@/components/ratio-distribution";
import { RatioTrendChart } from "@/components/ratio-trend-chart";
import { formatReportDate } from "@/lib/format";
import { timeSeriesPointKey } from "@/lib/matrix-types";
import { getRatioTimeSeries } from "@/lib/queries";

const DEFAULT_ANCHOR_CERT = 4063; // MidFirst Bank

type SearchParams = {
  anchor?: string | string[];
};

function firstParam(raw: string | string[] | undefined): string | undefined {
  if (raw === undefined) return undefined;
  return Array.isArray(raw) ? raw[0] : raw;
}

export default async function RatioDrilldownPage({
  params,
  searchParams,
}: {
  params: Promise<{ ratio_id: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { ratio_id } = await params;
  const series = await getRatioTimeSeries(ratio_id);
  if (!series) notFound();

  const { anchor } = await searchParams;
  const anchorRaw = firstParam(anchor);
  const requested = anchorRaw ? Number.parseInt(anchorRaw, 10) : NaN;
  const anchorCert =
    Number.isFinite(requested) && series.institutions.some((i) => i.cert === requested)
      ? requested
      : DEFAULT_ANCHOR_CERT;

  const latestQuarter =
    series.quarters.length > 0
      ? series.quarters[series.quarters.length - 1]
      : null;

  // Suppressed cells (e.g. CBLR filers' tier1_rbc) are excluded from the
  // strip plot to match the heat-map quartile-cutoff exclusion — same
  // reasoning, same data semantics.
  const distributionPoints: DistributionPoint[] = latestQuarter
    ? series.institutions
        .map((inst): DistributionPoint | null => {
          const cell = series.values.get(
            timeSeriesPointKey(inst.cert, latestQuarter.quarter_id),
          );
          if (!cell || cell.value === null || cell.data_quality === "suppressed") {
            return null;
          }
          return {
            cert: inst.cert,
            name: inst.name,
            value: cell.value,
            isAnchor: inst.cert === anchorCert,
          };
        })
        .filter((p): p is DistributionPoint => p !== null)
    : [];

  const def = series.ratioDef;

  // Preserve the user's anchor selection on the back-trip to the matrix —
  // symmetric to the matrix-to-drilldown forwarding in `ratio-matrix.tsx`.
  // Only forward when the selection isn't the default; an empty `?anchor=`
  // is just visual noise in the URL.
  const matrixBackHref =
    anchorCert !== DEFAULT_ANCHOR_CERT
      ? `/?anchor=${anchorCert}`
      : "/";

  return (
    <main className="min-h-dvh px-6 py-6">
      <header className="mb-4 flex items-baseline justify-between gap-4">
        <div className="flex items-baseline gap-4">
          <Link
            href={matrixBackHref}
            className="rounded-sm text-body text-text-secondary focus:outline-none focus-visible:outline-1 focus-visible:outline-accent hover:text-accent"
          >
            ← Matrix
          </Link>
          <h1 className="text-page-title font-semibold text-primary">
            {def.display_name}
          </h1>
        </div>
        <span className="text-body text-text-secondary">
          {latestQuarter ? `As of ${formatReportDate(latestQuarter.report_date)}` : "No data"}
        </span>
      </header>

      <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <h2 className="mb-1 eyebrow-label">
            Definition
          </h2>
          <p className="text-body text-text">
            <span className="font-medium">{def.display_name}</span>
            {" · "}
            <span className="text-text-secondary">{def.category}</span>
            {". "}
            {def.annualize ? "Annualized. " : ""}
            {def.avg_or_eop === "AVG"
              ? "Quarter-average denominators."
              : "End-of-period denominators."}
          </p>
        </div>
        <div>
          <h2 className="mb-1 eyebrow-label">
            Formula
          </h2>
          <p className="text-body text-text">
            <span className="font-medium">Numerator:</span>{" "}
            <code className="text-text-secondary">{def.numerator_formula}</code>
          </p>
          <p className="text-body text-text">
            <span className="font-medium">Denominator:</span>{" "}
            <code className="text-text-secondary">{def.denominator_formula}</code>
          </p>
        </div>
        {def.notes && (
          <div className="md:col-span-2">
            <h2 className="mb-1 eyebrow-label">
              Notes
            </h2>
            <p className="text-body text-text-secondary">{def.notes}</p>
          </div>
        )}
      </section>

      <section className="mb-6">
        <h2 className="mb-2 text-section-header font-semibold text-text">
          8-quarter trend
        </h2>
        {series.quarters.length > 0 ? (
          <div className="border border-border bg-surface p-3">
            <RatioTrendChart
              quarters={series.quarters}
              institutions={series.institutions}
              values={series.values}
              anchorCert={anchorCert}
            />
          </div>
        ) : (
          <EmptyState />
        )}
      </section>

      <section className="mb-6">
        <h2 className="mb-2 text-section-header font-semibold text-text">
          Peer distribution
          {latestQuarter && (
            <span className="ml-2 text-body font-normal text-text-tertiary">
              · {latestQuarter.quarter_id}
            </span>
          )}
        </h2>
        {distributionPoints.length > 0 && latestQuarter ? (
          <div className="border border-border bg-surface p-3">
            <RatioDistribution
              points={distributionPoints}
              quarterLabel={latestQuarter.quarter_id}
            />
          </div>
        ) : (
          <EmptyState />
        )}
      </section>
    </main>
  );
}

function EmptyState() {
  return (
    <div className="border border-border bg-surface-alt p-6 text-center text-body text-text-secondary">
      No data available for this ratio in the current peer set.
    </div>
  );
}
