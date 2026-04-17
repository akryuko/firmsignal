"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { startAnalysis } from "@/lib/api"
import { useRunStore } from "@/store/run"
import { validateCompanyInput, getLiveError } from "@/lib/validation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Loader2, ArrowRight, Building2 } from "lucide-react"

const AGENTS = [
  { label: "Scout",        color: "default" },
  { label: "Accountant",   color: "default" },
  { label: "Skeptic",      color: "default" },
  { label: "Human Review", color: "amber"   },
  { label: "Synthesizer",  color: "default" },
] as const

const FEATURES = [
  { icon: "🔍", label: "News & Leadership"       },
  { icon: "💰", label: "Financials & Price History" },
  { icon: "⚠️", label: "Risk Analysis"            },
]

export default function HomePage() {
  const [company, setCompany] = useState("")
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const router   = useRouter()
  const startRun = useRunStore((s) => s.startRun)

  const liveError = getLiveError(company)

  async function handleSubmit() {
    if (loading) return

    const validation = validateCompanyInput(company)
    if (!validation.valid) {
      setError(validation.error)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const { run_id, company: resolved } = await startAnalysis(company.trim())
      startRun(run_id, resolved)
      router.push(`/analyze/${run_id}`)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not connect to backend",
      )
      setLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">

      {/* ── Search card ── */}
      <div className="w-full max-w-xl">

        {/* Logo / title */}
        <div className="mb-10 flex flex-col items-center gap-2 text-center">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-slate-100 text-emerald-600">
              <Building2 className="h-5 w-5" />
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-slate-900">
              FirmSignal
            </h1>
          </div>
          <p className="mt-1 text-sm text-slate-500 leading-relaxed">
            Multi-agent company intelligence.{" "}
            <span className="text-slate-400">Powered by LangGraph + Claude.</span>
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border bg-white p-6 shadow-sm">

          <form onSubmit={(e) => { e.preventDefault(); handleSubmit() }} className="flex flex-col gap-3 sm:flex-row">
            <Input
              value={company}
              onChange={(e) => { setCompany(e.target.value); if (error) setError(null) }}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              placeholder="e.g. Nvidia, Boeing, AAPL, Stripe..."
              className={`h-11 flex-1 rounded-lg ${liveError || error ? "border-red-400 focus-visible:ring-red-400" : ""}`}
              disabled={loading}
              autoFocus
            />
            <Button
              type="submit"
              disabled={loading || !company.trim() || !!liveError}
              className="h-11 min-w-[110px] rounded-lg bg-emerald-600 px-5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <span className="flex items-center gap-1.5">
                  Analyse
                  <ArrowRight className="h-4 w-4" />
                </span>
              )}
            </Button>
          </form>

          {liveError ? (
            <p className="mt-1.5 text-sm text-red-600">{liveError}</p>
          ) : error ? (
            <p className="mt-1.5 text-sm text-red-600">{error}</p>
          ) : (
            <p className="mt-2.5 text-xs text-slate-400">
              Supports misspellings, ticker symbols, and informal names
            </p>
          )}
        </div>

        {/* Feature pills */}
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {FEATURES.map(({ icon, label }) => (
            <span
              key={label}
              className="inline-flex items-center gap-1.5 rounded-full border bg-white px-3 py-1 text-xs text-slate-500"
            >
              <span>{icon}</span>
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* ── Agent pipeline footer ── */}
      <footer className="mt-16 flex flex-wrap items-center justify-center gap-1.5 px-4">
        {AGENTS.map(({ label, color }, i) => (
          <span key={label} className="flex items-center gap-1.5">
            {color === "amber" ? (
              <span className="inline-flex items-center rounded-md border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                {label}
              </span>
            ) : (
              <span className="inline-flex items-center rounded-md border bg-slate-50 px-2.5 py-0.5 text-xs font-medium text-slate-500">
                {label}
              </span>
            )}
            {i < AGENTS.length - 1 && (
              <ArrowRight className="h-3 w-3 text-slate-300 shrink-0" />
            )}
          </span>
        ))}
      </footer>

    </main>
  )
}
