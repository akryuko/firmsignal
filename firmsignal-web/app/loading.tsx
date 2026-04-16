export default function Loading() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-5 px-4">

      <div className="flex w-48 flex-col gap-2.5">
        <div className="h-2.5 w-full animate-pulse rounded-full bg-slate-200" />
        <div className="h-2.5 w-3/4 animate-pulse rounded-full bg-slate-200" />
        <div className="h-2.5 w-1/2 animate-pulse rounded-full bg-slate-200" />
      </div>

      <p className="text-xs text-slate-400">Loading FirmSignal...</p>

    </main>
  )
}
