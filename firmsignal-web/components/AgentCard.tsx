import { cn } from "@/lib/utils"
import { AgentStatus } from "@/types"
import { CheckCircle, Circle, Loader2, XCircle } from "lucide-react"

interface Props {
  label:  string
  status: AgentStatus
  log:    string
}

const icons: Record<AgentStatus, React.ReactNode> = {
  pending: <Circle      className="h-5 w-5 text-slate-300" />,
  running: <Loader2     className="h-5 w-5 text-amber-500 animate-spin" />,
  done:    <CheckCircle className="h-5 w-5 text-emerald-500" />,
  error:   <XCircle     className="h-5 w-5 text-red-500" />,
}

export function AgentCard({ label, status, log }: Props) {
  return (
    <div className={cn(
      "flex items-start gap-4 rounded-xl border px-5 py-4 bg-white transition-all duration-300",
      status === "pending" && "border-slate-200 opacity-50",
      status === "running" && "border-amber-200 bg-amber-50/60 shadow-sm",
      status === "done"    && "border-emerald-200 bg-emerald-50/40",
      status === "error"   && "border-red-200 bg-red-50/40",
    )}>
      <div className="mt-0.5 shrink-0">{icons[status]}</div>
      <div className="min-w-0">
        <p className={cn(
          "text-base font-medium",
          status === "pending" ? "text-slate-400" : "text-slate-800",
        )}>
          {label}
        </p>
        {log && (
          <p className="mt-1 truncate text-sm text-slate-500">{log}</p>
        )}
      </div>
    </div>
  )
}
