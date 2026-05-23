"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatRatio } from "@/lib/format";
import type { MatrixCell } from "@/lib/matrix-types";
import { buildTrendChartData } from "@/lib/ratio-series";
import type { Institution, Quarter } from "@/types/db";

type Props = {
  quarters: Quarter[];
  institutions: Institution[];
  /** Keyed by `${cert}|${quarter_id}` — same shape as `RatioSeries.values`. */
  values: Map<string, MatrixCell>;
  anchorCert: number;
};

/**
 * 8-quarter trend chart. One Recharts <Line> per peer. Anchor stroke uses
 * `--color-accent` at 2.5px; peer strokes use `--color-text-tertiary` at 1px
 * per the Sprint 2 PR-E spec. Lines render bottom-to-top so the anchor
 * sits visually on top of the peer pack regardless of value overlap.
 *
 * Animations are off (`isAnimationActive={false}`) — banking dashboards
 * privilege static, screenshot-stable visuals over chart entrances. Null
 * values are not interpolated (`connectNulls={false}`) so gaps from
 * pre-ingest history or partial quarters read as gaps, not as straight
 * lines across them.
 */
export function RatioTrendChart({
  quarters,
  institutions,
  values,
  anchorCert,
}: Props) {
  const data = buildTrendChartData(quarters, institutions, values);

  // Anchor renders last so its line draws on top of the peer pack. Sort key:
  // anchor goes to the end, peers retain their incoming order (already sorted
  // anchor-first by `sortInstitutions`, so we reverse to push anchor last).
  const drawOrder = [...institutions].sort((a, b) => {
    if (a.cert === anchorCert) return 1;
    if (b.cert === anchorCert) return -1;
    return 0;
  });

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 16, right: 24, left: 8, bottom: 8 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="2 4" />
        <XAxis
          dataKey="quarter_id"
          stroke="var(--color-text-secondary)"
          tick={{ fill: "var(--color-text-secondary)", fontSize: 12 }}
        />
        <YAxis
          tickFormatter={(v: number) => formatRatio(v)}
          stroke="var(--color-text-secondary)"
          tick={{ fill: "var(--color-text-secondary)", fontSize: 12 }}
          width={72}
        />
        <Tooltip
          formatter={(value) =>
            formatRatio(typeof value === "number" ? value : null)
          }
          contentStyle={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            fontSize: 12,
            color: "var(--color-text)",
          }}
          labelStyle={{ color: "var(--color-text-secondary)" }}
          itemStyle={{ color: "var(--color-text)" }}
        />
        <Legend
          iconType="line"
          wrapperStyle={{ fontSize: 12, color: "var(--color-text-secondary)" }}
        />
        {drawOrder.map((inst) => {
          const isAnchor = inst.cert === anchorCert;
          return (
            <Line
              key={inst.cert}
              type="monotone"
              dataKey={`cert_${inst.cert}`}
              name={inst.name}
              stroke={isAnchor ? "var(--color-accent)" : "var(--color-text-tertiary)"}
              strokeWidth={isAnchor ? 2.5 : 1}
              dot={{ r: isAnchor ? 3 : 2 }}
              activeDot={{ r: 4 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          );
        })}
      </LineChart>
    </ResponsiveContainer>
  );
}
