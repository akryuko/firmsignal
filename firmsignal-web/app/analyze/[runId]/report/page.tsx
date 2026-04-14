"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useRunStore } from "@/store/run"
import { StockChart } from "@/components/StockChart"
import { CitedBrief } from "@/components/CitedBrief"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { ExternalLink } from "lucide-react"

const RANGES: Record<string, number> = { "1Y": 12, "3Y": 36, "5Y": 60 }

export default function ReportPage() {
  const router    = useRouter()
  const [range, setRange] = useState("5Y")

  const company        = useRunStore((s) => s.company)
  const correctionNote = useRunStore((s) => s.correctionNote)
  const outputs        = useRunStore((s) => s.outputs)
  const priceHistory   = useRunStore((s) => s.priceHistory)
  const ticker         = useRunStore((s) => s.ticker)
  const finalBrief     = useRunStore((s) => s.finalBrief)
  const finalSources   = useRunStore((s) => s.finalSources)
  const reset          = useRunStore((s) => s.reset)

  const acc    = outputs.accountant
  const sliced = priceHistory.slice(-RANGES[range])

  const metrics = acc?.is_public ? [
    { label: "Stock Price",  value: `$${acc.current_price} ${acc.currency}` },
    { label: "Market Cap",   value: acc.market_cap_formatted ?? "N/A" },
    { label: "Revenue TTM",  value: acc.revenue_formatted ?? "N/A" },
    { label: "P/E Ratio",    value: String(acc.pe_ratio ?? "N/A") },
    { label: "Gross Margin", value: acc.gross_margin_pct != null ? `${acc.gross_margin_pct}%` : "N/A" },
    {
      label: "1Y / 5Y",
      value: [acc.price_change_1y, acc.price_change_5y]
        .map((p) =>
          p != null
            ? `${p > 0 ? "▲" : "▼"}${Math.abs(p).toFixed(1)}%`
            : "N/A",
        )
        .join(" / "),
    },
  ] : []

  const uniqueSources = (() => {
    const seen = new Set<string>()
    return finalSources.filter((s) => {
      if (!s.url || seen.has(s.url)) return false
      seen.add(s.url)
      return true
    })
  })()

  function handleNewSearch() {
    reset()
    router.push("/")
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">

      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            📡 {company} — Intelligence Brief
          </h1>
          {correctionNote && (
            <p className="mt-1 text-sm text-amber-700">🔄 {correctionNote}</p>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={handleNewSearch}>
          ← New search
        </Button>
      </div>

      {/* Metrics */}
      {acc?.is_public && (
        <>
          <div className="mb-4 grid grid-cols-3 gap-3 sm:grid-cols-6">
            {metrics.map(({ label, value }) => (
              <div key={label} className="rounded-lg border px-3 py-2">
                <p className="text-xs text-slate-500">{label}</p>
                <p className="mt-0.5 text-sm font-semibold text-slate-800">
                  {value}
                </p>
              </div>
            ))}
          </div>

          {sliced.length > 0 && ticker && (
            <div className="mb-6 rounded-lg border p-4">
              <div className="mb-3 flex gap-2">
                {Object.keys(RANGES).map((r) => (
                  <button
                    key={r}
                    onClick={() => setRange(r)}
                    className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                      range === r
                        ? "bg-emerald-600 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>
              <StockChart data={sliced} ticker={ticker} />
            </div>
          )}

          <Separator className="my-6" />
        </>
      )}

      {/* Brief */}
      {finalBrief && (
        <CitedBrief brief={finalBrief} sources={finalSources} />
      )}

      {/* Sources */}
      {uniqueSources.length > 0 && (
        <>
          <Separator className="my-6" />
          <details>
            <summary className="cursor-pointer text-sm font-medium text-slate-600 hover:text-slate-900">
              📚 All sources ({uniqueSources.length})
            </summary>
            <div className="mt-3 space-y-2">
              {uniqueSources.map((s, i) => (
                <div key={i} className="flex items-start gap-2 text-sm">
                  <span className="shrink-0 text-slate-400">{i + 1}.</span>
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-emerald-600 hover:underline"
                  >
                    {s.title || s.url}
                    <ExternalLink className="h-3 w-3 shrink-0" />
                  </a>
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
                    {s.agent}
                  </span>
                </div>
              ))}
            </div>
          </details>
        </>
      )}
    </main>
  )
}