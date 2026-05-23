"use client";

import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART_FONT_SIZE } from "@/lib/chart-tokens";
import { formatRatio } from "@/lib/format";

export type DistributionPoint = {
  cert: number;
  name: string;
  value: number;
  isAnchor: boolean;
};

type Props = {
  points: DistributionPoint[];
  quarterLabel: string;
};

/**
 * Strip plot: peers as dots on a single horizontal axis (the ratio value).
 * Anchor dot is larger and in `--color-accent`; peers in
 * `--color-text-tertiary`. Hovering a dot reveals the peer name + value.
 *
 * Chosen over a box plot because N=5 peers makes quartile boxes statistically
 * misleading (one observation per quartile). If peer tiers widen past N=10
 * in Phase 4, revisit. See plan §"Open decisions" item 3.
 */
export function RatioDistribution({ points, quarterLabel }: Props) {
  // All dots sit at y=0.5 on a hidden axis — the strip plot is a single
  // horizontal row. If two peers' values collide visually, the tooltip still
  // distinguishes them; at N=5 the collision rate is negligible.
  const stripped = points.map((p) => ({ ...p, y: 0.5 }));
  const anchorPoints = stripped.filter((p) => p.isAnchor);
  const peerPoints = stripped.filter((p) => !p.isAnchor);

  return (
    <ResponsiveContainer width="100%" height={120}>
      <ScatterChart margin={{ top: 16, right: 24, left: 8, bottom: 8 }}>
        <CartesianGrid
          stroke="var(--color-border)"
          strokeDasharray="2 4"
          vertical={true}
          horizontal={false}
        />
        <XAxis
          dataKey="value"
          type="number"
          tickFormatter={(v: number) => formatRatio(v)}
          stroke="var(--color-text-secondary)"
          tick={{ fill: "var(--color-text-secondary)", fontSize: CHART_FONT_SIZE.tableData }}
          domain={["dataMin", "dataMax"]}
          label={{
            value: quarterLabel,
            position: "insideBottom",
            offset: -4,
            fill: "var(--color-text-tertiary)",
            fontSize: CHART_FONT_SIZE.superscript,
          }}
        />
        <YAxis dataKey="y" type="number" domain={[0, 1]} hide />
        <Tooltip
          cursor={{ stroke: "var(--color-border)", strokeDasharray: "2 4" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload as DistributionPoint;
            return (
              <div
                style={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  fontSize: CHART_FONT_SIZE.tableData,
                  color: "var(--color-text)",
                  padding: "6px 8px",
                }}
              >
                <div style={{ fontWeight: 500 }}>{p.name}</div>
                <div>{formatRatio(p.value)}</div>
              </div>
            );
          }}
        />
        <Scatter
          data={peerPoints}
          shape={PeerDot}
          isAnimationActive={false}
        />
        <Scatter
          data={anchorPoints}
          shape={AnchorDot}
          isAnimationActive={false}
        />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function PeerDot(props: { cx?: number; cy?: number }) {
  return (
    <circle
      cx={props.cx}
      cy={props.cy}
      r={4}
      fill="var(--color-text-tertiary)"
    />
  );
}

function AnchorDot(props: { cx?: number; cy?: number }) {
  return (
    <circle
      cx={props.cx}
      cy={props.cy}
      r={6}
      fill="var(--color-accent)"
    />
  );
}
