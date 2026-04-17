"use client"

import {
  Area, AreaChart, CartesianGrid,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts"
import { PricePoint } from "@/types"

interface Props {
  data:   PricePoint[]
  ticker: string
}

export function StockChart({ data, ticker }: Props) {
  if (!data.length) return null

  return (
    <div>
      <p className="mb-2 text-xs text-slate-500">
        {ticker} — Stock Price (USD, monthly close)
      </p>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#10b981" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            orientation="right"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `$${v.toFixed(2)}`}
            width={60}
          />
          <Tooltip
            formatter={(v) => [`$${Number(v).toFixed(2)}`, "Stock Price (USD)"]}
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: "1px solid rgba(0,0,0,0.08)",
            }}
          />
          <Area
            type="monotone"
            dataKey="close"
            stroke="#10b981"
            strokeWidth={1.5}
            fill="url(#priceGrad)"
            dot={false}
            activeDot={{ r: 4, fill: "#10b981" }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}