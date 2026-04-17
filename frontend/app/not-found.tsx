import Link from "next/link"

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="flex w-full max-w-[420px] flex-col items-center gap-6 text-center">

        <span className="text-8xl font-bold text-slate-100" aria-hidden>404</span>

        <div className="flex flex-col gap-1.5">
          <h1 className="text-xl font-semibold text-slate-900">Page not found</h1>
          <p className="text-sm text-slate-500">
            The page you&apos;re looking for doesn&apos;t exist or has expired.
          </p>
        </div>

        <Link
          href="/"
          className="inline-flex h-10 items-center justify-center rounded-lg bg-emerald-600 px-5 text-sm font-medium text-white hover:bg-emerald-700"
        >
          ← Back to search
        </Link>

      </div>
    </main>
  )
}
