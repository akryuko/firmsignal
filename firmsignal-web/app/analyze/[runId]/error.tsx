"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useRunStore } from "@/store/run"
import { Button } from "@/components/ui/button"

export default function AnalyzeError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string }
  unstable_retry: () => void
}) {
  const router = useRouter()
  const reset  = useRunStore((s) => s.reset)

  useEffect(() => {
    console.error(error)
  }, [error])

  function handleNewSearch() {
    reset()
    router.push("/")
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="flex w-full max-w-[420px] flex-col items-center gap-6 text-center">

        <span className="text-4xl text-slate-300" aria-hidden>⚠</span>

        <div className="flex flex-col gap-1.5">
          <h1 className="text-xl font-semibold text-slate-900">Analysis failed</h1>
          <p className="text-sm text-slate-500">
            An error occurred while running the analysis.
          </p>
        </div>

        {error.message && (
          <div className="w-full rounded-lg bg-slate-100 px-3 py-2 text-left text-xs font-mono text-slate-600 break-all">
            {error.message}
          </div>
        )}

        <div className="flex w-full gap-3">
          <Button
            onClick={unstable_retry}
            className="h-10 flex-1 rounded-lg bg-emerald-600 text-sm font-medium text-white hover:bg-emerald-700"
          >
            Try again
          </Button>
          <Button
            onClick={handleNewSearch}
            className="h-10 flex-1 rounded-lg border border-slate-200 bg-white text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            ← New search
          </Button>
        </div>

      </div>
    </main>
  )
}
