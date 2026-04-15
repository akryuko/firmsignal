import { cn } from "@/lib/utils"

interface Props {
  severity: "low" | "medium" | "high"
}

const styles: Record<string, string> = {
  high:   "bg-red-100   text-red-700   border-red-200",
  medium: "bg-amber-100 text-amber-700 border-amber-200",
  low:    "bg-blue-100  text-blue-700  border-blue-200",
}

export function RiskBadge({ severity }: Props) {
  return (
    <span className={cn(
      "inline-flex items-center rounded-md border px-2 py-0.5",
      "text-xs font-semibold uppercase tracking-wide",
      styles[severity],
    )}>
      {severity}
    </span>
  )
}