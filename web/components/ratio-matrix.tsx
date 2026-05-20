"use client";

import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { useMemo } from "react";

import { CATEGORY_LABELS } from "@/lib/ratio-order";
import {
  cellKey,
  restatementKey,
  type MatrixCell,
  type RatioGroup,
} from "@/lib/matrix-types";
import { EM_DASH, formatRatio } from "@/lib/format";
import type { Institution, Quarter, RatioCategory, RatioDef } from "@/types/db";

type Row =
  | { kind: "section"; category: RatioCategory }
  | { kind: "data"; def: RatioDef };

type Props = {
  institutions: Institution[];
  ratioGroups: RatioGroup[];
  cells: Map<string, MatrixCell>;
  restatedKeys: Set<string>;
  quarter: Quarter;
  anchorCert: number;
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
  restatedKeys,
  quarter,
  anchorCert,
}: Props) {
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

  const columns: ColumnDef<Row>[] = useMemo(() => {
    const ratioColumn: ColumnDef<Row> = {
      id: "ratio",
      header: "Ratio",
      cell: ({ row }) => {
        const r = row.original;
        if (r.kind === "section") {
          return (
            <span className="text-[length:var(--text-section-header)] font-semibold text-[color:var(--color-text)]">
              {CATEGORY_LABELS[r.category]}
            </span>
          );
        }
        return (
          <span className="text-[length:var(--text-table-data)] text-[color:var(--color-text)]">
            {r.def.display_name}
          </span>
        );
      },
    };
    const peerColumns: ColumnDef<Row>[] = institutions.map((inst) => ({
      id: `inst-${inst.cert}`,
      header: () => (
        <span className="block text-right text-[length:var(--text-table-data)] font-semibold">
          <span className="block text-[color:var(--color-text)]">{inst.name}</span>
          <span className="block text-[color:var(--color-text-tertiary)]">
            Cert {inst.cert}
          </span>
        </span>
      ),
      cell: ({ row }) => {
        const r = row.original;
        if (r.kind === "section") return null;
        const c = cells.get(cellKey(inst.cert, r.def.ratio_id));
        const restated = restatedKeys.has(restatementKey(inst.cert, quarter.quarter_id));
        return <DataCell cell={c} restated={restated} />;
      },
    }));
    return [ratioColumn, ...peerColumns];
  }, [institutions, cells, restatedKeys, quarter.quarter_id]);

  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel() });

  return (
    <div className="overflow-auto border border-[color:var(--color-border)]">
      <table className="border-collapse w-full">
        <thead className="bg-[color:var(--color-surface)]">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h, i) => {
                const isRatioCol = i === 0;
                const isAnchorCol = !isRatioCol && institutions[i - 1]?.cert === anchorCert;
                return (
                  <th
                    key={h.id}
                    scope="col"
                    className={[
                      "sticky top-0 p-2 border-b border-[color:var(--color-border)]",
                      isRatioCol
                        ? "left-0 z-30 text-left min-w-60 border-r border-[color:var(--color-border)]"
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
              return (
                <tr key={row.id}>
                  <td
                    colSpan={columns.length}
                    className="sticky left-0 p-2 border-y border-[color:var(--color-border)] bg-[color:var(--color-surface-alt)]"
                  >
                    <span className="text-[length:var(--text-section-header)] font-semibold uppercase tracking-wide text-[color:var(--color-text-secondary)]">
                      {CATEGORY_LABELS[r.category]}
                    </span>
                  </td>
                </tr>
              );
            }
            // Zebra alternation across data rows only.
            const zebra =
              rowIdx % 2 === 0 ? "var(--color-surface)" : "var(--color-surface-alt)";
            return (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell, i) => {
                  const isRatioCol = i === 0;
                  const isAnchorCol =
                    !isRatioCol && institutions[i - 1]?.cert === anchorCert;
                  const cellBg = isAnchorCol
                    ? "color-mix(in srgb, var(--color-primary) 6%, " + zebra + ")"
                    : zebra;
                  return (
                    <td
                      key={cell.id}
                      className={[
                        "py-1 px-2 border-b border-[color:var(--color-border)] text-[length:var(--text-table-data)]",
                        isRatioCol
                          ? "sticky left-0 z-10 text-left border-r border-[color:var(--color-border)]"
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

function DataCell({ cell, restated }: { cell: MatrixCell | undefined; restated: boolean }) {
  if (!cell) {
    return (
      <span className="text-[color:var(--color-text-tertiary)]">{EM_DASH}</span>
    );
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
        <sup
          title="Restated since first publication — see quality_log"
          className="ml-0.5 text-[color:var(--color-text-secondary)]"
        >
          r
        </sup>
      )}
      {cell.data_quality !== "ok" && (
        <span
          aria-label={DATA_QUALITY_LABEL[cell.data_quality]}
          title={DATA_QUALITY_LABEL[cell.data_quality]}
          className="ml-1 inline-block w-1.5 h-1.5 rounded-full align-middle bg-[color:var(--color-text-tertiary)]"
        />
      )}
    </span>
  );
}
