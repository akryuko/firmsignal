import { cn } from "@/lib/utils"
import { AgentStatus } from "@/types"
import { CheckCircle, Circle, Loader2, XCircle } from "lucide-react"

interface Props {
  label:  string
  status: AgentStatus
  log:    string
}

const icons: Record<AgentStatus, React.ReactNode> = {
  pending: <Circle      className="h-4 w-4 text-slate-300" />,
  running: <Loader2     className="h-4 w-4 text-amber-500 animate-spin" />,
  done:    <CheckCircle className="h-4 w-4 text-emerald-500" />,
  error:   <XCircle     className="h-4 w-4 text-red-500" />,
}

export function AgentCard({ label, status, log }: Props) {
  return (
    <div className={cn(
      "flex items-start gap-3 rounded-lg border px-4 py-3 transition-all duration-300",
      status === "pending" && "border-slate-200 opacity-40",
      status === "running" && "border-amber-200 bg-amber-50/50",
      status === "done"    && "border-emerald-200 bg-emerald-50/30",
      status === "error"   && "border-red-200 bg-red-50/30",
    )}>
      <div className="mt-0.5 shrink-0">{icons[status]}</div>
      <div className="min-w-0">
        <p className={cn(
          "text-sm font-medium",
          status === "pending" ? "text-slate-400" : "text-slate-800",
        )}>
          {label}
        </p>
        {log && (
          <p className="mt-0.5 truncate text-xs text-slate-500">{log}</p>
        )}
      </div>
    </div>
  )
}