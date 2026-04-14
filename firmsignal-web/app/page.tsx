"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { startAnalysis } from "@/lib/api"
import { useRunStore } from "@/store/run"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Loader2 } from "lucide-react"

export default function HomePage() {
  const [company, setCompany] = useState("")
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const router   = useRouter()
  const startRun = useRunStore((s) => s.startRun)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!company.trim()) return
    setLoading(true)
    setError(null)
    try {
      const { run_id, company: resolved } = await startAnalysis(company.trim())
      startRun(run_id, resolved)
      router.push(`/analyze/${run_id}`)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not connect to backend",
      )
      setLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
            📡 FirmSignal
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Multi-agent company intelligence · LangGraph + Claude
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Nvidia, Boeing, AAPL, Googlee..."
            className="h-11 text-base"
            disabled={loading}
            autoFocus
          />
          <Button
            type="submit"
            disabled={loading || !company.trim()}
            className="h-11 px-6 bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {loading
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : "Analyse →"
            }
          </Button>
        </form>

        {error && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
            <p className="mt-1 text-xs text-red-500">
              Make sure the backend is running:{" "}
              <code>uvicorn firmsignal.api.app:app --port 8000</code>
            </p>
          </div>
        )}

        <p className="mt-3 text-center text-xs text-slate-400">
          Supports misspellings, ticker symbols, and informal names
        </p>
      </div>
    </main>
  )
}