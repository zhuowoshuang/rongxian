"use client";

import React, { useMemo } from "react";
import {
  ComposedChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export interface CandleData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface CandlestickChartProps {
  data: CandleData[];
}

function formatVolume(v: number): string {
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(0)}万`;
  return v.toFixed(0);
}

// ---- Candle shape ----

function CandleShape(props: any) {
  const { x, y, width, height, payload } = props;
  const { open, close, high, low } = payload;

  const barWidth = Math.max(width - 2, 0.5);
  const centerX = x + width / 2;
  const isUp = close >= open;
  const color = isUp ? "#ef4444" : "#22c55e"; // Chinese convention: red up, green down

  // Flat candle (high === low) or degenerate case
  if (!high || !low || high <= low || height <= 0) {
    return (
      <line
        x1={centerX - 3}
        y1={y}
        x2={centerX + 3}
        y2={y}
        stroke={color}
        strokeWidth={2}
      />
    );
  }

  const range = high - low;
  const scale = height / range;

  // Body top = position of max(open, close); body bottom = position of min(open, close)
  const bodyTop = y + (high - Math.max(open, close)) * scale;
  const bodyBottom = y + (high - Math.min(open, close)) * scale;
  const bodyHeight = Math.max(bodyBottom - bodyTop, 1);

  // Wick: full vertical line from high to low
  const wickY1 = y; // high
  const wickY2 = y + height; // low

  return (
    <g>
      {/* Wick */}
      <line
        x1={centerX}
        y1={wickY1}
        x2={centerX}
        y2={wickY2}
        stroke={color}
        strokeWidth={1}
      />
      {/* Body */}
      <rect
        x={x + 1}
        y={bodyTop}
        width={barWidth}
        height={bodyHeight}
        fill={color}
        stroke={color}
        strokeWidth={0.5}
      />
    </g>
  );
}

// ---- Volume bar below chart ----

function VolumeBarShape(props: any) {
  const { x, y, width, height, payload } = props;
  const isUp = payload.close >= payload.open;
  const color = isUp ? "#ef4444" : "#22c55e";
  const barWidth = Math.max(width - 2, 0.5);
  return (
    <rect
      x={x + 1}
      y={y}
      width={barWidth}
      height={Math.max(height, 0)}
      fill={color}
      opacity={0.35}
    />
  );
}

// ---- Tooltip ----

function CandleTooltip({ active, payload }: any) {
  if (active && payload && payload.length > 0) {
    const data = payload[0]?.payload;
    if (!data) return null;
    return (
      <div className="rounded-lg border border-white/10 bg-[#1e293b] px-3 py-2 shadow-xl backdrop-blur-xl text-white text-xs">
        <p className="text-slate-400 mb-1">{data.date}</p>
        <div className="space-y-0.5 font-mono">
          <p>
            开盘: <span className="font-bold">{data.open?.toFixed(2)}</span>
          </p>
          <p>
            最高:{" "}
            <span className="font-bold text-red-400">{data.high?.toFixed(2)}</span>
          </p>
          <p>
            最低:{" "}
            <span className="font-bold text-green-400">{data.low?.toFixed(2)}</span>
          </p>
          <p>
            收盘:{" "}
            <span className="font-bold">{data.close?.toFixed(2)}</span>
          </p>
          <p>
            成交量: <span className="font-bold">{formatVolume(data.volume)}</span>
          </p>
        </div>
      </div>
    );
  }
  return null;
}

// ---- Main component ----

export default function CandlestickChart({ data }: CandlestickChartProps) {
  const chartData = useMemo(() => {
    return data.map((d) => ({
      ...d,
      range: d.high - d.low,
      color: d.close >= d.open ? "#ef4444" : "#22c55e",
    }));
  }, [data]);

  const yDomain = useMemo(() => {
    const lows = data.map((d) => d.low);
    const highs = data.map((d) => d.high);
    const min = Math.min(...lows);
    const max = Math.max(...highs);
    const padding = (max - min) * 0.08;
    return [
      Math.max(0, min - padding),
      max + padding,
    ] as [number, number];
  }, [data]);

  const maxVolume = useMemo(() => Math.max(...data.map((d) => d.volume)), [data]);

  return (
    <div>
      {/* K-line chart */}
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={yDomain}
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            tickFormatter={(v: number) => v.toFixed(2)}
          />
          <Tooltip content={<CandleTooltip />} />
          {/* Invisible bar to offset stack; range bar renders on top */}
          <Bar
            dataKey="low"
            stackId="candle"
            fill="transparent"
            isAnimationActive={false}
          />
          <Bar
            dataKey="range"
            stackId="candle"
            shape={<CandleShape />}
            isAnimationActive={false}
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>

      {/* Volume bars */}
      <ResponsiveContainer width="100%" height={60}>
        <ComposedChart data={chartData}>
          <YAxis
            domain={[0, maxVolume * 1.15]}
            hide
          />
          <Tooltip
            content={({ active, payload }: any) => {
              if (active && payload?.length) {
                const d = payload[0]?.payload;
                return (
                  <div className="rounded-lg border border-white/10 bg-[#1e293b] px-3 py-2 shadow-xl backdrop-blur-xl text-white text-xs">
                    成交量: <span className="font-bold font-mono">{formatVolume(d?.volume ?? 0)}</span>
                  </div>
                );
              }
              return null;
            }}
          />
          <Bar
            dataKey="volume"
            shape={<VolumeBarShape />}
            isAnimationActive={false}
          >
            {chartData.map((entry, index) => (
              <Cell key={`vol-cell-${index}`} fill={entry.color} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
