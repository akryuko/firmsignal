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

        <div className="mb-10 text-center">
          <div className="mb-4 inline-flex items-center gap-3">
            <span className="text-4xl">📡</span>
            <h1 className="text-4xl font-bold tracking-tight text-slate-900">
              FirmSignal
            </h1>
          </div>
          <p className="text-lg text-slate-500 leading-relaxed">
            Multi-agent company intelligence
          </p>
          <p className="mt-1 text-sm text-slate-400">
            LangGraph · Claude · Real-time signals
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex gap-3">
          <Input
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Nvidia, Boeing, AAPL..."
            className="h-12 text-base rounded-xl border-slate-200 bg-white shadow-sm"
            disabled={loading}
            autoFocus
          />
          <Button
            type="submit"
            disabled={loading || !company.trim()}
            className="h-12 px-7 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl shadow-sm text-base font-medium"
          >
            {loading
              ? <Loader2 className="h-5 w-5 animate-spin" />
              : "Analyse →"
            }
          </Button>
        </form>

        {error && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
            <p className="mt-1 text-xs text-red-500">
              Make sure the backend is running:{" "}
              <code className="font-mono">uvicorn firmsignal.api.app:app --port 8000</code>
            </p>
          </div>
        )}

        <p className="mt-4 text-center text-sm text-slate-400">
          Supports company names, ticker symbols, and common misspellings
        </p>

      </div>
    </main>
  )
}
