"use client"

import { useRouter } from "next/navigation"
import { useRunStore } from "@/store/run"
import { Button } from "@/components/ui/button"

// Shared inline error view for any screen === "error" state.
// Not a route — app/analyze/[runId]/error.tsx is a Next.js error
// *boundary* (catches thrown render errors), not a navigable page, so
// pipeline-reported errors (delivered via SSE, not a thrown exception)
// render this directly instead of router.push-ing to a nonexistent URL.
export function ErrorState() {
  const router   = useRouter()
  const reset    = useRunStore((s) => s.reset)
  const errorMsg = useRunStore((s) => s.errorMsg)

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

        {errorMsg && (
          <div className="w-full rounded-lg bg-slate-100 px-3 py-2 text-left text-xs font-mono text-slate-600 break-all">
            {errorMsg}
          </div>
        )}

        <Button
          onClick={handleNewSearch}
          className="h-10 w-full rounded-lg bg-emerald-600 text-sm font-medium text-white hover:bg-emerald-700"
        >
          ← New search
        </Button>

      </div>
    </main>
  )
}
