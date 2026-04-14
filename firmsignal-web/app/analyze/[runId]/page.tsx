"use client"

import { useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { useRunStore } from "@/store/run"
import { useSSE } from "@/lib/useSSE"
import { AgentCard } from "@/components/AgentCard"

const AGENTS = [
  { key: "scout",       label: "🔍 The Scout — news & leadership" },
  { key: "accountant",  label: "💰 The Accountant — financials & price history" },
  { key: "skeptic",     label: "🔎 The Skeptic — sentiment & risk signals" },
  { key: "synthesizer", label: "✍️  The Synthesizer — cited intelligence brief" },
]

export default function AnalyzePage() {
  const params  = useParams()
  const router  = useRouter()
  const runId   = params.runId as string
  const screen  = useRunStore((s) => s.screen)
  const company = useRunStore((s) => s.company)
  const agents  = useRunStore((s) => s.agents)

  useSSE(runId)

  useEffect(() => {
    if (screen === "hitl")   router.push(`/analyze/${runId}/review`)
    if (screen === "report") router.push(`/analyze/${runId}/report`)
    if (screen === "error")  router.push(`/analyze/${runId}/error`)
    if (screen === "search") router.push("/")
  }, [screen, runId, router])

  return (
    <main className="mx-auto max-w-xl px-4 py-16">
      <div className="mb-10">
        <h1 className="text-2xl font-bold text-slate-900">
          Analysing{" "}
          <span className="text-emerald-600">{company}</span>
        </h1>
        <p className="mt-2 text-base text-slate-500">
          Pipeline running — each agent reports when complete
        </p>
      </div>

      <div className="space-y-3">
        {AGENTS.map(({ key, label }) => (
          <AgentCard
            key={key}
            label={label}
            status={agents[key]?.status ?? "pending"}
            log={agents[key]?.log ?? ""}
          />
        ))}
      </div>
    </main>
  )
}
