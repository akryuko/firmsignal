import { cn } from "@/lib/utils"
import { AgentStatus } from "@/types"
import { CheckCircle, Circle, Loader2, UserCheck, XCircle } from "lucide-react"

interface Props {
  label:   string
  status:  AgentStatus
  log:     string
  isHitl?: boolean
}

const icons: Record<AgentStatus, React.ReactNode> = {
  pending: <Circle      className="h-5 w-5 text-slate-300" />,
  running: <Loader2     className="h-5 w-5 text-amber-500 animate-spin" />,
  done:    <CheckCircle className="h-5 w-5 text-emerald-500" />,
  error:   <XCircle     className="h-5 w-5 text-red-500" />,
}

const hitlIcons: Record<AgentStatus, React.ReactNode> = {
  pending: <Circle     className="h-5 w-5 text-slate-300" />,
  running: <UserCheck  className="h-5 w-5 text-amber-500" />,
  done:    <CheckCircle className="h-5 w-5 text-emerald-500" />,
  error:   <XCircle    className="h-5 w-5 text-red-500" />,
}

export function AgentCard({ label, status, log, isHitl = false }: Props) {
  return (
    <div className={cn(
      "flex items-start gap-4 rounded-xl border px-5 py-4 bg-white transition-all duration-300",
      status === "pending" && "border-slate-200 opacity-50",
      status === "running" && "border-amber-200 bg-amber-50/60 shadow-sm",
      status === "done"    && "border-emerald-200 bg-emerald-50/40",
      status === "error"   && "border-red-200 bg-red-50/40",
      isHitl && status === "running" && "border-amber-300 bg-amber-50 shadow-sm",
    )}>
      <div className="mt-0.5 shrink-0">
        {isHitl ? hitlIcons[status] : icons[status]}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className={cn(
            "text-base font-medium",
            status === "pending" ? "text-slate-400" : "text-slate-800",
          )}>
            {label}
          </p>
          {isHitl && status === "running" && (
            <span className="rounded-full border border-amber-300 bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
              waiting for you
            </span>
          )}
        </div>
        {log && (
          <p className="mt-1 truncate text-sm text-slate-500">{log}</p>
        )}
      </div>
    </div>
  )
}
