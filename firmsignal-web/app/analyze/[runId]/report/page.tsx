"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useRunStore } from "@/store/run"
import { downloadPdf } from "@/lib/api"
import { StockChart } from "@/components/StockChart"
import { CitedBrief } from "@/components/CitedBrief"
import { RiskBadge } from "@/components/RiskBadge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { ExternalLink, FileDown, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { RiskFlag, Source } from "@/types"

// ─── Constants ────────────────────────────────────────────────────────────────

const RANGES: Record<string, number> = { "1Y": 12, "3Y": 36, "5Y": 60 }

const SEVERITY_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 }

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

// ─── Helpers ──────────────────────────────────────────────────────────────────

function toCamel(s: string) {
  return s.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
}

function stripSources(brief: string): string {
  const cutoff = brief.search(/^---\s*\n### Sources/m)
  if (cutoff !== -1) return brief.slice(0, cutoff).trim()
  const cutoff2 = brief.search(/^### Sources/m)
  return cutoff2 === -1 ? brief : brief.slice(0, cutoff2).trim()
}

function extractKeyInsight(brief: string): { insight: string; rest: string } {
  const idx = brief.indexOf("## Recent Developments")
  if (idx === -1) return { insight: "", rest: brief }
  const raw     = brief.slice(0, idx).trim()
  const insight = raw.replace(/^##\s+Executive Summary\s*\n+/i, "").trim()
  return { insight, rest: brief.slice(idx).trim() }
}

function fmtChange(val: number | null | undefined): React.ReactNode {
  if (val == null) return <span className="text-slate-800">N/A</span>
  return (
    <span className={val >= 0 ? "text-emerald-600" : "text-red-500"}>
      {val >= 0 ? "▲" : "▼"}{Math.abs(val).toFixed(1)}%
    </span>
  )
}

// ─── Sub-components ───────────────────────────────────────────────────────────

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

function SentimentMeter({ score, label, sourcesAnalyzed }: {
  score: number
  label: string
  sourcesAnalyzed: number
}) {
  const clamped = Math.max(-1, Math.min(1, score))
  const pct     = Math.round(((clamped + 1) / 2) * 100)
  const isNeg   = score < -0.1
  const isPos   = score > 0.1

  return (
    <div>
      <div className="relative h-7 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={cn(
            "absolute top-0 h-full rounded-full",
            isNeg ? "bg-red-400" : isPos ? "bg-emerald-500" : "bg-slate-400",
          )}
          style={{ width: `${pct}%` }}
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xs font-bold text-slate-700 drop-shadow-sm">
            {score > 0 ? "+" : ""}{score.toFixed(2)}&ensp;·&ensp;
            <span className="font-normal capitalize">{label.replace(/_/g, " ")}</span>
          </span>
        </div>
      </div>
      <div className="mt-1.5 flex justify-between text-xs text-slate-400">
        <span>Bearish</span>
        <span>{sourcesAnalyzed} sources analysed</span>
        <span>Bullish</span>
      </div>
    </div>
  )
}

function RiskTable({ flags }: { flags: RiskFlag[] }) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const sorted = [...flags].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9),
  )

  function toggle(i: number) {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  return (
    <div className="overflow-hidden rounded-xl border">
      <div className="grid grid-cols-[88px_1fr] gap-3 border-b bg-slate-50 px-4 py-2 text-xs font-semibold uppercase tracking-widest text-slate-400 sm:grid-cols-[88px_1fr_72px]">
        <span>Severity</span>
        <span>Risk</span>
        <span className="hidden sm:block">Source</span>
      </div>

      {sorted.map((flag, i) => (
        <div
          key={i}
          className={cn(
            "grid grid-cols-[88px_1fr] gap-3 px-4 py-3 sm:grid-cols-[88px_1fr_72px]",
            i % 2 === 1 ? "bg-slate-50/50" : "bg-white",
            i < sorted.length - 1 && "border-b border-slate-100",
          )}
        >
          <div className="flex items-start pt-0.5">
            <RiskBadge severity={flag.severity} />
          </div>

          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-700">{flag.category}</p>
            <p className={cn(
              "mt-0.5 text-sm leading-relaxed text-slate-500",
              !expanded.has(i) && "line-clamp-2",
            )}>
              {flag.description}
            </p>
            {flag.description.length > 120 && (
              <button
                onClick={() => toggle(i)}
                className="mt-0.5 cursor-pointer text-xs text-slate-400 hover:text-slate-600"
              >
                {expanded.has(i) ? "show less" : "show more"}
              </button>
            )}
            {flag.source_url && (
              <a
                href={flag.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-xs text-emerald-600 hover:underline sm:hidden"
              >
                Source <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>

          <div className="hidden items-start pt-0.5 sm:flex">
            {flag.source_url ? (
              <a
                href={flag.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-emerald-600 hover:underline"
              >
                Link <ExternalLink className="h-3 w-3" />
              </a>
            ) : (
              <span className="text-xs text-slate-300">—</span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function SourcesDetails({ sources }: { sources: Source[] }) {
  const seen   = new Set<string>()
  const unique = sources.filter((s) => {
    if (!s.url || seen.has(s.url)) return false
    seen.add(s.url)
    return true
  })

  const numbered = unique.map((s, i) => ({ ...s, n: i + 1 }))

  const agentOrder: string[] = []
  const grouped: Record<string, typeof numbered> = {}
  for (const s of numbered) {
    if (!grouped[s.agent]) {
      agentOrder.push(s.agent)
      grouped[s.agent] = []
    }
    grouped[s.agent].push(s)
  }

  const countLine = agentOrder
    .map((a) => `${a[0].toUpperCase()}${a.slice(1)} (${grouped[a].length})`)
    .join(" · ")

  return (
    <details className="mt-8">
      <summary className="cursor-pointer text-sm font-medium text-slate-500 hover:text-slate-800">
        📚 {unique.length} sources — {countLine}
      </summary>
      <div className="mt-4 space-y-5">
        {agentOrder.map((agent) => (
          <div key={agent}>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-400">
              {agent}
            </p>
            <div className="space-y-1.5">
              {grouped[agent].map((s) => {
                const raw   = s.title || s.url
                const title = raw.length > 60 ? raw.slice(0, 60) + "…" : raw
                return (
                  <div key={s.url} className="flex items-start gap-2 text-sm">
                    <span className="w-5 shrink-0 text-right text-slate-400">{s.n}.</span>
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-emerald-600 hover:underline"
                    >
                      {title}
                      <ExternalLink className="h-3 w-3 shrink-0" />
                    </a>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </details>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ReportPage() {
  const router              = useRouter()
  const [range, setRange]   = useState("5Y")
  const [exporting, setExporting] = useState(false)

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

  const { insight, rest } = finalBrief
    ? extractKeyInsight(stripSources(finalBrief))
    : { insight: "", rest: "" }

  const upside =
    acc?.target_price_mean != null && acc?.current_price != null
      ? (((acc.target_price_mean - acc.current_price) / acc.current_price) * 100).toFixed(1)
      : null

  const sortedFlags = skep?.risk_flags
    ? [...skep.risk_flags].sort(
        (a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9),
      )
    : []

  const brightSpots = skep?.positive_signals?.slice(0, 3) ?? []

  const recKey        = acc?.analyst_recommendation ? toCamel(acc.analyst_recommendation) : null
  const hasDivergence = (skep?.sentiment_score ?? 0) < 0 && (recKey === "buy" || recKey === "strongBuy")

  const today = new Date().toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  })

  function handleNewSearch() {
    reset()
    router.push("/")
  }

  async function handleExport() {
    setExporting(true)
    try {
      const blob = await downloadPdf({
        company:         company,
        brief:           finalBrief,
        accountant:      acc ?? null,
        skeptic:         skep ?? null,
        sources:         finalSources,
        ticker:          ticker ?? null,
        correction_note: correctionNote ?? null,
      })
      const url = URL.createObjectURL(blob)
      const a   = document.createElement("a")
      a.href     = url
      a.download = `${company.replace(/\s+/g, "-")}-FirmSignal.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      // fallback: browser print dialog
      window.print()
    } finally {
      setExporting(false)
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{company}</h1>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            {acc?.ticker && (
              <span className="rounded-md bg-slate-800 px-2 py-0.5 text-sm font-semibold text-white">
                {acc.ticker}
              </span>
            )}
            {acc?.sector && (
              <span className="text-sm text-slate-500">
                {acc.sector}{acc.industry ? ` · ${acc.industry}` : ""}
              </span>
            )}
          </div>

          {correctionNote && (
            <p className="mt-1 text-sm text-amber-700">🔄 {correctionNote}</p>
          )}

          <p className="mt-2 text-xs text-slate-400">
            Generated {today}
            {finalSources.length > 0 && ` · ${finalSources.length} sources`}
          </p>
        </div>

        <div className="flex shrink-0 gap-2 print:hidden">
          <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting}>
            {exporting
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <FileDown className="h-3.5 w-3.5" />}
            {exporting ? "Generating…" : "Export PDF"}
          </Button>
          <Button variant="outline" size="sm" onClick={handleNewSearch}>
            ← New search
          </Button>
        </div>
      </div>

      <Separator className="mb-8" />

      {/* ── Chart + Stat Grid (two-column) ──────────────────────────────────── */}
      {acc && acc.is_public && (
        <>
          <div className="mb-8 flex flex-col gap-5 lg:flex-row">

            {/* Chart — 60% */}
            {sliced.length > 0 && ticker && (
              <div className="w-full rounded-xl border bg-white p-5 lg:w-[60%]">
                <div className="mb-4 flex gap-2 print:hidden">
                  {Object.keys(RANGES).map((r) => (
                    <button
                      key={r}
                      onClick={() => setRange(r)}
                      className={cn(
                        "cursor-pointer rounded-lg px-4 py-1.5 text-sm font-medium",
                        r === range
                          ? "bg-emerald-600 text-white"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200",
                      )}
                    >
                      {r}
                    </button>
                  ))}
                </div>
                <div className="h-[180px] sm:h-[240px]">
                  <StockChart data={sliced} ticker={ticker} />
                </div>
              </div>
            )}

            {/* Stat Grid — 40% */}
            <div className="w-full divide-y divide-slate-100 overflow-hidden rounded-xl border bg-white lg:w-[40%]">

              {/* Row 1 */}
              <div className="grid grid-cols-2 divide-x divide-slate-100">
                <div className="px-4 py-4">
                  <p className="text-xs text-slate-400">Stock Price</p>
                  <p className="mt-1 text-base font-semibold text-slate-800">
                    {acc.current_price != null ? `$${acc.current_price}` : "N/A"}
                    {acc.current_price != null && (
                      <span className="ml-1 text-sm font-normal text-slate-400">{acc.currency}</span>
                    )}
                  </p>
                </div>
                <div className="px-4 py-4">
                  <p className="text-xs text-slate-400">Market Cap</p>
                  <p className="mt-1 text-base font-semibold text-slate-800">
                    {acc.market_cap_formatted ?? "N/A"}
                  </p>
                </div>
              </div>

              {/* Row 2 */}
              <div className="grid grid-cols-2 divide-x divide-slate-100">
                <div className="px-4 py-4">
                  <p className="text-xs text-slate-400">Revenue TTM</p>
                  <p className="mt-1 text-base font-semibold text-slate-800">
                    {acc.revenue_formatted ?? "N/A"}
                  </p>
                </div>
                <div className="px-4 py-4">
                  <p className="text-xs text-slate-400">P/E Ratio</p>
                  <p className="mt-1 text-base font-semibold text-slate-800">
                    {acc.pe_ratio ?? "N/A"}
                  </p>
                </div>
              </div>

              {/* Row 3 */}
              <div className="grid grid-cols-2 divide-x divide-slate-100">
                <div className="px-4 py-4">
                  <p className="text-xs text-slate-400">Gross Margin</p>
                  <p className="mt-1 text-base font-semibold text-slate-800">
                    {acc.gross_margin_pct != null ? `${acc.gross_margin_pct}%` : "N/A"}
                  </p>
                </div>
                <div className="px-4 py-4">
                  <p className="text-xs text-slate-400">1Y / 5Y Return</p>
                  <p className="mt-1 flex items-center gap-1.5 text-base font-semibold">
                    {fmtChange(acc.price_change_1y)}
                    <span className="text-slate-300">/</span>
                    {fmtChange(acc.price_change_5y)}
                  </p>
                </div>
              </div>

            </div>
          </div>

          <Separator className="mb-8" />
        </>
      )}

      {/* ── Key Insight ─────────────────────────────────────────────────────── */}
      {insight && (
        <>
          <div className="mb-8 rounded-r-xl border-l-4 border-emerald-500 bg-emerald-50/30 px-6 py-5">
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-emerald-600">
              Key Insight
            </p>
            <CitedBrief brief={insight} sources={finalSources} />
          </div>
          <Separator className="mb-8" />
        </>
      )}

      {/* ── Sentiment vs Analyst View ───────────────────────────────────────── */}
      {(skep || acc?.analyst_recommendation) && (
        <>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
            Sentiment vs Analyst View
          </p>
          <div className="mb-8 overflow-hidden rounded-xl border bg-white">
            <div className={cn(
              "grid divide-slate-100",
              skep && acc?.analyst_recommendation
                ? "sm:grid-cols-2 sm:divide-x divide-y sm:divide-y-0"
                : "grid-cols-1",
            )}>

              {/* Left — Market Sentiment */}
              {skep && (
                <div className="px-5 py-5">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
                    Market Sentiment
                  </p>
                  <SentimentMeter
                    score={skep.sentiment_score}
                    label={skep.sentiment_label}
                    sourcesAnalyzed={skep.sources_analyzed}
                  />
                </div>
              )}

              {/* Right — Analyst Consensus */}
              {acc?.analyst_recommendation && (
                <div className="px-5 py-5">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
                    Analyst Consensus
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <RecBadge rec={acc.analyst_recommendation} />
                    {acc.analyst_count && (
                      <span className="text-sm text-slate-400">{acc.analyst_count} analysts</span>
                    )}
                  </div>
                  {acc.target_price_mean != null && (
                    <p className="mt-3 text-sm text-slate-600">
                      Target{" "}
                      <strong className="text-slate-800">${acc.target_price_mean}</strong>
                      {upside && (
                        <span className={cn(
                          "ml-1 text-xs font-medium",
                          Number(upside) >= 0 ? "text-emerald-600" : "text-red-500",
                        )}>
                          ({Number(upside) >= 0 ? "+" : ""}{upside}% vs current)
                        </span>
                      )}
                    </p>
                  )}
                  {acc.target_price_low != null && acc.target_price_high != null && (
                    <p className="mt-1 text-xs text-slate-400">
                      Range ${acc.target_price_low} — ${acc.target_price_high}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Divergence note */}
            {hasDivergence && (
              <div className="border-t border-amber-100 bg-amber-50/60 px-5 py-3">
                <p className="text-sm text-amber-800">
                  <span className="font-semibold">⚡ Potential catalyst signal —</span>{" "}
                  Market sentiment is negative while analysts rate this a{" "}
                  <span className="font-medium">
                    {REC_LABELS[recKey!] ?? acc!.analyst_recommendation!.replace(/_/g, " ")}
                  </span>
                  . This divergence can precede a reversal if market sentiment shifts.
                </p>
              </div>
            )}
          </div>

          <Separator className="mb-8" />
        </>
      )}

      {/* ── Risk Flags ──────────────────────────────────────────────────────── */}
      {sortedFlags.length > 0 && (
        <>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
            Risk Flags
          </p>
          <div className="mb-8">
            <RiskTable flags={sortedFlags} />
          </div>
        </>
      )}

      {/* ── Bright Spots ────────────────────────────────────────────────────── */}
      {brightSpots.length > 0 && (
        <>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
            Bright Spots
          </p>
          <div className="mb-8 space-y-2">
            {brightSpots.map((sig, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-emerald-500" />
                <p className="text-sm text-slate-700">{sig}</p>
              </div>
            ))}
          </div>
          <Separator className="mb-8" />
        </>
      )}

      {/* ── Market Opinions ─────────────────────────────────────────────────── */}
      {(skep?.public_sentiment || skep?.employee_sentiment) && (
        <>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
            Market Opinions
          </p>
          <div className="mb-8 grid gap-4 md:grid-cols-2">
            {skep?.public_sentiment && (
              <div className="rounded-xl border bg-white p-5">
                <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-400">
                  Investors &amp; Public
                </p>
                <p className="text-sm leading-relaxed text-slate-700">{skep.public_sentiment}</p>
              </div>
            )}
            {skep?.employee_sentiment && (
              <div className="rounded-xl border bg-white p-5">
                <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-400">
                  Employee Sentiment
                </p>
                <p className="text-sm leading-relaxed text-slate-700">{skep.employee_sentiment}</p>
              </div>
            )}
          </div>
          <Separator className="mb-8" />
        </>
      )}

      {/* ── Brief (remaining sections) ──────────────────────────────────────── */}
      {rest && (
        <div className="pb-4">
          <CitedBrief brief={rest} sources={finalSources} />
        </div>
      )}

      {/* ── Sources ─────────────────────────────────────────────────────────── */}
      {finalSources.length > 0 && (
        <SourcesDetails sources={finalSources} />
      )}

    </main>
  )
}
