"use client"

import { useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { useRunStore } from "@/store/run"
import { useSSE } from "@/lib/useSSE"
import { AgentCard } from "@/components/AgentCard"
import { AgentStatus } from "@/types"

const AGENTS = [
  { key: "scout",       label: "🔍 The Scout — news & leadership" },
  { key: "accountant",  label: "💰 The Accountant — financials & price history" },
  { key: "skeptic",     label: "⚠️  The Skeptic — sentiment & risk signals" },
  { key: "hitl",        label: "👤 Human Review — review data & add instructions" },
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

  // Derive HITL status from surrounding agent states + screen
  function hitlStatus(): AgentStatus {
    const skepticDone = agents["skeptic"]?.status === "done"
    const synthStarted =
      agents["synthesizer"]?.status === "running" ||
      agents["synthesizer"]?.status === "done"
    if (synthStarted) return "done"
    if (skepticDone)  return "running"
    return "pending"
  }

  function hitlLog(): string {
    const s = hitlStatus()
    if (s === "running") return "Pipeline paused — review the data and add any instructions before the brief is generated"
    if (s === "done")    return "Review complete"
    return ""
  }

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
        {AGENTS.map(({ key, label }) => {
          const isHitl = key === "hitl"
          return (
            <AgentCard
              key={key}
              label={label}
              status={isHitl ? hitlStatus() : (agents[key]?.status ?? "pending")}
              log={isHitl ? hitlLog() : (agents[key]?.log ?? "")}
              isHitl={isHitl}
            />
          )
        })}
      </div>
    </main>
  )
}
