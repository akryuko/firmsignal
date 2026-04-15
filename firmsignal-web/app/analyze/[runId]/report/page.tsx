"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useRunStore } from "@/store/run"
import { StockChart } from "@/components/StockChart"
import { CitedBrief } from "@/components/CitedBrief"
import { RiskBadge } from "@/components/RiskBadge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { ExternalLink } from "lucide-react"
import { cn } from "@/lib/utils"

const RANGES: Record<string, number> = { "1Y": 12, "3Y": 36, "5Y": 60 }

const SENT_EMOJI: Record<string, string> = {
  very_negative: "🔴",
  negative:      "🟠",
  neutral:       "⚪",
  positive:      "🟢",
  very_positive: "💚",
}

const REC_STYLES: Record<string, string> = {
  strongBuy:    "bg-emerald-600 text-white",
  buy:          "bg-emerald-100 text-emerald-800",
  hold:         "bg-amber-100  text-amber-800",
  underperform: "bg-orange-100 text-orange-800",
  sell:         "bg-red-100    text-red-700",
  strongSell:   "bg-red-600    text-white",
}

const REC_LABELS: Record<string, string> = {
  strongBuy:    "Strong Buy",
  buy:          "Buy",
  hold:         "Hold",
  underperform: "Underperform",
  sell:         "Sell",
  strongSell:   "Strong Sell",
}

function toCamel(s: string) {
  return s.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
}

function RecBadge({ rec }: { rec: string }) {
  const key = toCamel(rec)
  return (
    <span className={cn(
      "inline-flex items-center rounded-md px-2.5 py-1",
      "text-sm font-bold uppercase tracking-wide",
      REC_STYLES[key] ?? "bg-slate-100 text-slate-700",
    )}>
      {REC_LABELS[key] ?? REC_LABELS[rec] ?? rec.replace(/_/g, " ")}
    </span>
  )
}

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
  const skep   = outputs.skeptic
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

  const upside =
    acc?.target_price_mean != null && acc?.current_price != null
      ? (((acc.target_price_mean - acc.current_price) / acc.current_price) * 100).toFixed(1)
      : null

  function handleNewSearch() {
    reset()
    router.push("/")
  }

  const hasIntelligence = skep || acc?.analyst_recommendation
  const hasOpinions     = skep?.public_sentiment || skep?.employee_sentiment

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            📡 {company} — Intelligence Brief
          </h1>
          {acc?.is_public && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {acc.ticker && (
                <span className="rounded-md bg-slate-800 px-2 py-0.5 text-sm font-semibold text-white">
                  {acc.ticker}
                </span>
              )}
              {acc.sector && (
                <span className="text-sm text-slate-500">
                  {acc.sector}{acc.industry ? ` · ${acc.industry}` : ""}
                </span>
              )}
            </div>
          )}
          {correctionNote && (
            <p className="mt-2 text-base text-amber-700">🔄 {correctionNote}</p>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={handleNewSearch} className="shrink-0">
          ← New search
        </Button>
      </div>

      {/* ── Financial metrics + chart ───────────────────────────────────────── */}
      {acc?.is_public && (
        <>
          <div className="mb-5 grid grid-cols-3 gap-3 sm:grid-cols-6">
            {metrics.map(({ label, value }) => (
              <div key={label} className="rounded-xl border bg-white px-3 py-3">
                <p className="text-sm text-slate-500">{label}</p>
                <p className="mt-0.5 text-base font-semibold text-slate-800">{value}</p>
              </div>
            ))}
          </div>

          {sliced.length > 0 && ticker && (
            <div className="mb-6 rounded-xl border bg-white p-5">
              <div className="mb-4 flex gap-2">
                {Object.keys(RANGES).map((r) => (
                  <button
                    key={r}
                    onClick={() => setRange(r)}
                    className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
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

          <Separator className="my-8" />
        </>
      )}

      {/* ── Market Intelligence ─────────────────────────────────────────────── */}
      {hasIntelligence && (
        <>
          <h2 className="mb-5 text-lg font-semibold text-slate-800">📊 Market Intelligence</h2>

          {/* Sentiment + Analyst Consensus side by side */}
          <div className="mb-5 grid gap-4 md:grid-cols-2">

            {skep && (
              <div className="rounded-xl border bg-white p-5">
                <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
                  Market Sentiment
                </p>
                <div className="flex items-center gap-3">
                  <span className="text-3xl font-bold text-slate-900">
                    {skep.sentiment_score > 0 ? "+" : ""}
                    {skep.sentiment_score.toFixed(2)}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-xl">
                      {SENT_EMOJI[skep.sentiment_label] ?? "⚪"}
                    </span>
                    <span className="text-base capitalize text-slate-600">
                      {skep.sentiment_label.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>
                <p className="mt-2 text-sm text-slate-400">
                  {skep.sources_analyzed} sources analysed
                </p>
              </div>
            )}

            {acc?.analyst_recommendation && (
              <div className="rounded-xl border bg-white p-5">
                <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
                  Analyst Consensus
                </p>
                <div className="mb-2.5 flex items-center gap-2.5">
                  <RecBadge rec={acc.analyst_recommendation} />
                  {acc.analyst_count && (
                    <span className="text-sm text-slate-400">
                      {acc.analyst_count} analysts
                    </span>
                  )}
                </div>
                {acc.target_price_mean != null && (
                  <p className="text-base text-slate-700">
                    Target{" "}
                    <strong className="text-slate-900">${acc.target_price_mean}</strong>
                    {upside && (
                      <span className={cn(
                        "ml-1.5 text-sm font-medium",
                        Number(upside) >= 0 ? "text-emerald-600" : "text-red-500",
                      )}>
                        ({Number(upside) >= 0 ? "+" : ""}{upside}% vs current)
                      </span>
                    )}
                  </p>
                )}
                {acc.target_price_low != null && acc.target_price_high != null && (
                  <p className="mt-1 text-sm text-slate-400">
                    Range ${acc.target_price_low} — ${acc.target_price_high}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Risk flags */}
          {(skep?.risk_flags.length ?? 0) > 0 && (
            <div className="mb-4">
              <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
                Risk Flags
              </p>
              <div className="space-y-2.5">
                {skep!.risk_flags.map((flag, i) => (
                  <div key={i} className="flex items-start gap-3 rounded-xl border bg-white px-4 py-3.5">
                    <div className="mt-0.5 shrink-0">
                      <RiskBadge severity={flag.severity} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-700">{flag.category}</p>
                      <p className="mt-0.5 text-sm leading-relaxed text-slate-500">
                        {flag.description}
                      </p>
                      {flag.source_url && (
                        <a
                          href={flag.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-1.5 inline-flex items-center gap-1 text-xs text-emerald-600 hover:underline"
                        >
                          Source <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Positive signals */}
          {(skep?.positive_signals.length ?? 0) > 0 && (
            <div className="mb-5 rounded-xl border border-emerald-100 bg-emerald-50/60 px-5 py-4">
              <p className="mb-2.5 text-xs font-semibold uppercase tracking-widest text-slate-400">
                Positive Signals
              </p>
              <div className="space-y-1.5">
                {skep!.positive_signals.map((sig, i) => (
                  <p key={i} className="text-sm text-slate-700">✅ {sig}</p>
                ))}
              </div>
            </div>
          )}

          <Separator className="my-8" />
        </>
      )}

      {/* ── Market Opinions ─────────────────────────────────────────────────── */}
      {hasOpinions && (
        <>
          <h2 className="mb-5 text-lg font-semibold text-slate-800">💬 Market Opinions</h2>
          <div className="mb-8 grid gap-4 md:grid-cols-2">
            {skep?.public_sentiment && (
              <div className="rounded-xl border bg-white p-5">
                <p className="mb-2.5 text-xs font-semibold uppercase tracking-widest text-slate-400">
                  Investors &amp; Public
                </p>
                <p className="text-base leading-relaxed text-slate-700">
                  {skep.public_sentiment}
                </p>
              </div>
            )}
            {skep?.employee_sentiment && (
              <div className="rounded-xl border bg-white p-5">
                <p className="mb-2.5 text-xs font-semibold uppercase tracking-widest text-slate-400">
                  Employee Sentiment
                </p>
                <p className="text-base leading-relaxed text-slate-700">
                  {skep.employee_sentiment}
                </p>
              </div>
            )}
          </div>
          <Separator className="my-8" />
        </>
      )}

      {/* ── Intelligence Brief ──────────────────────────────────────────────── */}
      {finalBrief && (
        <>
          <h2 className="mb-5 text-lg font-semibold text-slate-800">📝 Intelligence Brief</h2>
          <div className="rounded-xl border bg-white p-6 md:p-8">
            <CitedBrief brief={finalBrief} sources={finalSources} />
          </div>
        </>
      )}

      {/* ── Sources ─────────────────────────────────────────────────────────── */}
      {uniqueSources.length > 0 && (
        <>
          <Separator className="my-8" />
          <details>
            <summary className="cursor-pointer text-base font-medium text-slate-600 hover:text-slate-900">
              📚 All sources ({uniqueSources.length})
            </summary>
            <div className="mt-4 space-y-2.5">
              {uniqueSources.map((s, i) => (
                <div key={i} className="flex items-start gap-2 text-base">
                  <span className="shrink-0 text-slate-400">{i + 1}.</span>
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-emerald-600 hover:underline"
                  >
                    {s.title || s.url}
                    <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                  </a>
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-sm text-slate-500">
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
