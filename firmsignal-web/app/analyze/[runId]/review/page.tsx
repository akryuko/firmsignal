"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { useRunStore } from "@/store/run"
import { resumeRun } from "@/lib/api"
import { useSSE } from "@/lib/useSSE"
import { StockChart } from "@/components/StockChart"
import { RiskBadge } from "@/components/RiskBadge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { ExternalLink, Loader2 } from "lucide-react"

const SENT_EMOJI: Record<string, string> = {
  very_negative: "🔴", negative: "🟠",
  neutral: "⚪", positive: "🟢", very_positive: "💚",
}

export default function ReviewPage() {
  const params  = useParams()
  const router  = useRouter()
  const runId   = params.runId as string

  const [note,     setNote]     = useState("")
  const [resuming, setResuming] = useState(false)

  const company        = useRunStore((s) => s.company)
  const correctionNote = useRunStore((s) => s.correctionNote)
  const hitlPayload    = useRunStore((s) => s.hitlPayload)
  const outputs        = useRunStore((s) => s.outputs)
  const priceHistory   = useRunStore((s) => s.priceHistory)
  const ticker         = useRunStore((s) => s.ticker)
  const screen         = useRunStore((s) => s.screen)

  // Keep SSE open — receives synthesizer events after resume
  useSSE(runId)

  useEffect(() => {
    if (screen === "report") {
      router.push(`/analyze/${runId}/report`)
    }
  }, [screen, runId, router])

  if (screen === "report") return null

  const scout = outputs.scout
  const acc   = outputs.accountant
  const skep  = hitlPayload

  async function handleApprove() {
    setResuming(true)
    try {
      await resumeRun(runId, true, note.trim() || null)
    } catch (err) {
      console.error(err)
      setResuming(false)
    }
  }

  async function handleAbort() {
    await resumeRun(runId, false)
    router.push("/")
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">

      <div className="mb-6">
        <h1 className="text-xl font-semibold text-slate-900">
          📡 {company} — Review Required
        </h1>
        {correctionNote && (
          <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            🔄 {correctionNote}
          </div>
        )}
      </div>

      {/* Scout + Accountant */}
      <div className="grid gap-6 md:grid-cols-2 mb-6">

        <div className="rounded-lg border p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">
            🔍 Recent News
          </h2>
          {scout?.news_items.slice(0, 4).map((item, i) => (
            <div key={i} className="mb-3 last:mb-0">
              <p className="text-sm font-medium text-slate-800 leading-snug">
                {item.headline}
              </p>
              <div className="mt-0.5 flex items-center gap-2">
                <span className="text-xs text-slate-400">{item.date}</span>
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-0.5 text-xs text-emerald-600 hover:underline"
                >
                  Source <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
          ))}
          {(scout?.leadership_changes?.length ?? 0) > 0 && (
            <>
              <Separator className="my-3" />
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Leadership Changes
              </h3>
              {scout!.leadership_changes.map((c, i) => (
                <p key={i} className="text-sm text-slate-700">
                  {c.name} ({c.role}) —{" "}
                  <Badge variant="outline" className="text-xs">
                    {c.change_type}
                  </Badge>
                </p>
              ))}
            </>
          )}
        </div>

        <div className="rounded-lg border p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">
            💰 Financial Snapshot
          </h2>
          {acc?.is_public ? (
            <>
              <div className="grid grid-cols-3 gap-3 mb-4">
                {[
                  { label: "Price",      value: `$${acc.current_price}` },
                  { label: "Market Cap", value: acc.market_cap_formatted ?? "N/A" },
                  { label: "P/E Ratio",  value: acc.pe_ratio ?? "N/A" },
                  { label: "Revenue",    value: acc.revenue_formatted ?? "N/A" },
                  {
                    label: "1Y Return",
                    value: acc.price_change_1y != null
                      ? `${acc.price_change_1y > 0 ? "▲" : "▼"} ${Math.abs(acc.price_change_1y).toFixed(1)}%`
                      : "N/A",
                  },
                  {
                    label: "5Y Return",
                    value: acc.price_change_5y != null
                      ? `${acc.price_change_5y > 0 ? "▲" : "▼"} ${Math.abs(acc.price_change_5y).toFixed(1)}%`
                      : "N/A",
                  },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <p className="text-xs text-slate-500">{label}</p>
                    <p className="text-sm font-semibold text-slate-800">
                      {String(value)}
                    </p>
                  </div>
                ))}
              </div>
              {priceHistory.length > 0 && ticker && (
                <StockChart data={priceHistory} ticker={ticker} />
              )}
            </>
          ) : (
            <p className="text-sm text-slate-500">
              Private company — no public market data available.
            </p>
          )}
        </div>
      </div>

      <Separator className="my-6" />

      {/* Skeptic */}
      {skep && (
        <div className="mb-6">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">
            🔎 Skeptic Analysis
          </h2>

          <div className="mb-4 flex items-center gap-3">
            <span className="text-2xl font-bold text-slate-900">
              {skep.sentiment_score != null
                ? `${skep.sentiment_score > 0 ? "+" : ""}${skep.sentiment_score.toFixed(2)}`
                : "N/A"}
            </span>
            <span className="text-sm text-slate-600">
              {SENT_EMOJI[skep.sentiment_label ?? ""] ?? "⚪"}{" "}
              {skep.sentiment_label?.replace(/_/g, " ")}
            </span>
            <span className="ml-auto text-xs text-slate-400">
              {skep.sources_analyzed} sources analysed
            </span>
          </div>

          <div className="space-y-3 mb-4">
            {skep.risk_flags.map((flag, i) => (
              <div key={i} className="rounded-lg border px-4 py-3">
                <div className="flex items-start gap-2 mb-1">
                  <RiskBadge severity={flag.severity} />
                  <span className="text-sm font-medium text-slate-800">
                    {flag.category}
                  </span>
                </div>
                <p className="text-sm text-slate-600">{flag.description}</p>
                {flag.source_url && (
                  <a
                    href={flag.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 inline-flex items-center gap-0.5 text-xs text-emerald-600 hover:underline"
                  >
                    View source <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            ))}
          </div>

          {skep.positive_signals.length > 0 && (
            <div className="mb-4">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Positive Signals
              </h3>
              {skep.positive_signals.map((sig, i) => (
                <p key={i} className="text-sm text-slate-700">✅ {sig}</p>
              ))}
            </div>
          )}

          <div className="rounded-md bg-slate-50 border px-4 py-3 text-sm text-slate-700">
            {skep.summary}
          </div>
        </div>
      )}

      <Separator className="my-6" />

      {/* Decision */}
      <div>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">
          Your Decision
        </h2>
        <Textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Optional analyst note — e.g. 'Focus on the legal risk, downplay the culture flag'"
          className="mb-4 h-20 resize-none text-sm"
          disabled={resuming}
        />
        <div className="flex gap-3">
          <Button
            onClick={handleApprove}
            disabled={resuming}
            className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {resuming ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Generating report...</>
            ) : (
              "✅ Approve & Generate Report"
            )}
          </Button>
          <Button
            variant="outline"
            onClick={handleAbort}
            disabled={resuming}
            className="text-red-600 hover:text-red-700 hover:border-red-300"
          >
            Abort
          </Button>
        </div>
      </div>
    </main>
  )
}