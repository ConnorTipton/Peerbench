"use client";

import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type RowData,
} from "@tanstack/react-table";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, useTransition } from "react";

import { CATEGORY_LABELS } from "@/lib/ratio-order";
import {
  cellKey,
  restatementKey,
  type MatrixCell,
  type RatioGroup,
  type RestatedDetail,
} from "@/lib/matrix-types";
import { EM_DASH, formatFactValue, formatRatio, formatReportDate } from "@/lib/format";
import {
  nextSortState,
  serializeSortParam,
  sortWithinSections,
  type SortDir,
  type SortState,
} from "@/lib/sort";
import {
  serializeCollapsedParam,
  toggleCategory,
} from "@/lib/collapse";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { Institution, RatioCategory, RatioDef } from "@/types/db";

// Carry the cert on each peer column so anchor-column detection doesn't
// depend on `institutions[i - 1]` — a positional read that silently breaks
// if column order changes (e.g. when a per-peer sort lands in Sprint 2).
declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    cert?: number;
  }
}

type Row =
  | { kind: "section"; category: RatioCategory }
  | { kind: "data"; def: RatioDef };

type Props = {
  institutions: Institution[];
  ratioGroups: RatioGroup[];
  cells: Map<string, MatrixCell>;
  restatedDetails: Map<string, RestatedDetail>;
  anchorCert: number;
  initialSort: SortState;
  initialCollapsed: ReadonlySet<RatioCategory>;
};

const DATA_QUALITY_LABEL: Record<MatrixCell["data_quality"], string> = {
  ok: "Computed cleanly",
  partial: "Underlying field missing or unavailable",
  suppressed: "Suppressed by policy (e.g. CBLR filer)",
  mismatch: "Computed value disagrees with FDIC pre-computed",
};

export function RatioMatrix({
  institutions,
  ratioGroups,
  cells,
  restatedDetails,
  anchorCert,
  initialSort,
  initialCollapsed,
}: Props) {
  const [sort, setSort] = useState<SortState>(initialSort);
  const [collapsed, setCollapsed] =
    useState<ReadonlySet<RatioCategory>>(initialCollapsed);
  const router = useRouter();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();

  // Resync local sort when the server-derived initialSort changes (e.g. user
  // hits back/forward, or another control rewrites `?sort=`). Compared on
  // primitive cert/dir to avoid re-firing on referentially-new-but-equal
  // SortState objects from the server.
  useEffect(() => {
    setSort((prev) => {
      if (prev?.cert === initialSort?.cert && prev?.dir === initialSort?.dir) {
        return prev;
      }
      return initialSort;
    });
  }, [initialSort?.cert, initialSort?.dir, initialSort]);

  // Resync collapsed set on back/forward nav (same shape as the sort resync).
  // Compared by canonical serialization so a referentially-new Set with the
  // same members is a no-op.
  const initialCollapsedSerialized = serializeCollapsedParam(initialCollapsed);
  useEffect(() => {
    setCollapsed((prev) => {
      if (serializeCollapsedParam(prev) === initialCollapsedSerialized) {
        return prev;
      }
      return initialCollapsed;
    });
  }, [initialCollapsedSerialized, initialCollapsed]);

  const applySort = useCallback(
    (cert: number) => {
      const next = nextSortState(sort, cert);
      setSort(next);
      const params = new URLSearchParams(searchParams.toString());
      const serialized = serializeSortParam(next);
      if (serialized) {
        params.set("sort", serialized);
      } else {
        params.delete("sort");
      }
      const qs = params.toString();
      startTransition(() => {
        router.replace(qs ? `?${qs}` : "?", { scroll: false });
      });
    },
    [sort, router, searchParams],
  );

  const applyCollapse = useCallback(
    (category: RatioCategory) => {
      const next = toggleCategory(collapsed, category);
      setCollapsed(next);
      const params = new URLSearchParams(searchParams.toString());
      const serialized = serializeCollapsedParam(next);
      if (serialized) {
        params.set("collapsed", serialized);
      } else {
        params.delete("collapsed");
      }
      const qs = params.toString();
      startTransition(() => {
        router.replace(qs ? `?${qs}` : "?", { scroll: false });
      });
    },
    [collapsed, router, searchParams],
  );

  const rows: Row[] = useMemo(() => {
    const out: Row[] = [];
    for (const group of ratioGroups) {
      out.push({ kind: "section", category: group.category });
      for (const def of group.defs) {
        out.push({ kind: "data", def });
      }
    }
    return out;
  }, [ratioGroups]);

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    return sortWithinSections(
      rows,
      (r) => r.kind === "section",
      (r) => (r.kind === "data" ? cells.get(cellKey(sort.cert, r.def.ratio_id))?.value ?? null : null),
      sort.dir,
    );
  }, [rows, sort, cells]);

  // Hide data rows under collapsed categories. Section rows always render
  // (they're the toggle target). Filter runs AFTER sort, so hidden rows
  // retain the active sort order and re-expanding shows them in place.
  const visibleRows = useMemo(() => {
    if (collapsed.size === 0) return sortedRows;
    return sortedRows.filter(
      (r) => r.kind === "section" || !collapsed.has(r.def.category),
    );
  }, [sortedRows, collapsed]);

  const columns: ColumnDef<Row>[] = useMemo(() => {
    const ratioColumn: ColumnDef<Row> = {
      id: "ratio",
      header: "Ratio",
      cell: ({ row }) => {
        const r = row.original;
        if (r.kind === "section") {
          return (
            <span className="text-section-header font-semibold text-text">
              {CATEGORY_LABELS[r.category]}
            </span>
          );
        }
        return (
          <span className="text-table-data text-text">
            {r.def.display_name}
          </span>
        );
      },
    };
    const peerColumns: ColumnDef<Row>[] = institutions.map((inst) => ({
      id: `inst-${inst.cert}`,
      meta: { cert: inst.cert },
      header: () => (
        <SortHeader
          name={inst.name}
          cert={inst.cert}
          dir={sort?.cert === inst.cert ? sort.dir : null}
          onClick={() => applySort(inst.cert)}
        />
      ),
      cell: ({ row }) => {
        const r = row.original;
        if (r.kind === "section") return null;
        const c = cells.get(cellKey(inst.cert, r.def.ratio_id));
        const restated = restatedDetails.get(restatementKey(inst.cert, r.def.ratio_id));
        return <DataCell cell={c} restated={restated} />;
      },
    }));
    return [ratioColumn, ...peerColumns];
  }, [institutions, cells, restatedDetails, sort, applySort]);

  const table = useReactTable({
    data: visibleRows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="flex-1 min-h-0 overflow-auto border border-border">
      <table className="border-separate border-spacing-0 w-full">
        <thead className="bg-surface">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => {
                const isRatioCol = h.column.id === "ratio";
                const cert = h.column.columnDef.meta?.cert;
                const isAnchorCol = !isRatioCol && cert === anchorCert;
                const ariaSort: "ascending" | "descending" | "none" | undefined =
                  isRatioCol || cert === undefined
                    ? undefined
                    : sort?.cert === cert
                      ? sort.dir === "asc"
                        ? "ascending"
                        : "descending"
                      : "none";
                return (
                  <th
                    key={h.id}
                    scope="col"
                    aria-sort={ariaSort}
                    className={[
                      "sticky top-0 p-2 border-b border-border",
                      isRatioCol
                        ? "left-0 z-30 text-left min-w-60 border-r border-border"
                        : "z-20 text-right min-w-40",
                    ].join(" ")}
                    style={{
                      background: isAnchorCol
                        ? "color-mix(in srgb, var(--color-primary) 6%, var(--color-surface))"
                        : "var(--color-surface)",
                    }}
                  >
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row, rowIdx) => {
            const r = row.original;
            if (r.kind === "section") {
              const isCollapsed = collapsed.has(r.category);
              const label = CATEGORY_LABELS[r.category];
              return (
                <tr key={row.id}>
                  <td
                    colSpan={columns.length}
                    className="sticky left-0 p-0 border-b border-border bg-surface-alt"
                  >
                    <SectionToggle
                      label={label}
                      isCollapsed={isCollapsed}
                      onClick={() => applyCollapse(r.category)}
                    />
                  </td>
                </tr>
              );
            }
            // Zebra alternation across data rows only.
            const zebra =
              rowIdx % 2 === 0 ? "var(--color-surface)" : "var(--color-surface-alt)";
            return (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => {
                  const isRatioCol = cell.column.id === "ratio";
                  const isAnchorCol =
                    !isRatioCol && cell.column.columnDef.meta?.cert === anchorCert;
                  const cellBg = isAnchorCol
                    ? "color-mix(in srgb, var(--color-primary) 6%, " + zebra + ")"
                    : zebra;
                  return (
                    <td
                      key={cell.id}
                      className={[
                        "py-1 px-2 border-b border-border text-table-data",
                        isRatioCol
                          ? "sticky left-0 z-10 text-left border-r border-border"
                          : "text-right",
                      ].join(" ")}
                      style={{ background: cellBg }}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DataCell({
  cell,
  restated,
}: {
  cell: MatrixCell | undefined;
  restated: RestatedDetail | undefined;
}) {
  if (!cell) {
    return <span className="text-text-tertiary">{EM_DASH}</span>;
  }
  const formatted = formatRatio(cell.value);
  const isNegative = cell.value !== null && cell.value < 0;
  return (
    <span
      style={{
        color: isNegative ? "var(--color-negative)" : "var(--color-text)",
      }}
    >
      {formatted}
      {restated && (
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              className="ml-0.5 cursor-help align-super text-[10px] leading-none text-text-secondary rounded-sm focus:outline-none focus-visible:outline-1 focus-visible:outline-accent"
              aria-label={`Underlying input ${restated.field_code} restated since first publication`}
            >
              r
            </button>
          </TooltipTrigger>
          <TooltipContent side="top" align="center">
            <RestatementTooltipBody detail={restated} />
          </TooltipContent>
        </Tooltip>
      )}
      {cell.data_quality !== "ok" && (
        <span
          aria-label={DATA_QUALITY_LABEL[cell.data_quality]}
          title={DATA_QUALITY_LABEL[cell.data_quality]}
          className="ml-1 inline-block w-1.5 h-1.5 rounded-full align-middle bg-text-tertiary"
        />
      )}
    </span>
  );
}

// Fields where old_value/new_value are NOT dollar amounts. Today only
// CBLRIND (Community Bank Leverage Ratio election flag, 0/1). Add to the
// set when new non-dollar fields enter the handler dependency graph.
const NON_DOLLAR_FIELDS = new Set<string>(["CBLRIND"]);

function RestatementTooltipBody({ detail }: { detail: RestatedDetail }) {
  const showThousandsLabel = !NON_DOLLAR_FIELDS.has(detail.field_code);
  return (
    <div className="space-y-0.5">
      <div>
        <span className="font-medium">{detail.field_code}</span>: was{" "}
        <span className="font-medium">{formatFactValue(detail.old_value)}</span>, now{" "}
        <span className="font-medium">{formatFactValue(detail.new_value)}</span>
      </div>
      <div className="text-text-secondary">
        Restated {formatReportDate(detail.detected_at)}
        {showThousandsLabel ? " · values in thousands" : ""}
      </div>
    </div>
  );
}

function SectionToggle({
  label,
  isCollapsed,
  onClick,
}: {
  label: string;
  isCollapsed: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={!isCollapsed}
      aria-label={`${isCollapsed ? "Expand" : "Collapse"} ${label} section`}
      className="flex w-full cursor-pointer items-baseline gap-2 p-2 text-left focus:outline-none focus-visible:outline-1 focus-visible:outline-accent"
    >
      <span
        aria-hidden="true"
        className="inline-block w-3 text-text-tertiary"
      >
        {isCollapsed ? "▸" : "▾"}
      </span>
      <span className="text-section-header font-semibold uppercase tracking-wide text-text-secondary">
        {label}
      </span>
    </button>
  );
}

function SortHeader({
  name,
  cert,
  dir,
  onClick,
}: {
  name: string;
  cert: number;
  dir: SortDir | null;
  onClick: () => void;
}) {
  const indicator = dir === "asc" ? "↑" : dir === "desc" ? "↓" : "↕";
  return (
    <button
      type="button"
      onClick={onClick}
      className="block w-full cursor-pointer rounded-sm text-right text-table-data font-semibold transition-colors duration-200 ease-in-out focus:outline-none focus-visible:outline-1 focus-visible:outline-accent"
      aria-label={`Sort by ${name}`}
    >
      <span className="flex items-baseline justify-end gap-1 text-text">
        <span>{name}</span>
        <span
          aria-hidden="true"
          className={dir ? "text-accent" : "text-text-tertiary"}
        >
          {indicator}
        </span>
      </span>
      <span className="block text-text-tertiary">Cert {cert}</span>
    </button>
  );
}
