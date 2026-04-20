export type AgentStatus = "pending" | "running" | "done" | "error"

export type Screen =
  | "search"
  | "running"
  | "hitl"
  | "report"
  | "error"

export interface NewsItem {
  headline: string
  url: string
  date: string
  summary: string
}

export interface LeadershipChange {
  name: string
  role: string
  change_type: string
  date: string
  source_url: string
}

export interface ScoutOutput {
  company_name: string
  news_items: NewsItem[]
  leadership_changes: LeadershipChange[]
  key_events: string[]
  research_date: string
}

export interface PricePoint {
  date: string
  close: number
}

export interface AccountantOutput {
  company_name: string
  ticker: string | null
  is_public: boolean
  sector: string
  industry: string
  market_cap: number | null
  market_cap_formatted: string | null
  pe_ratio: number | null
  revenue_ttm: number | null
  revenue_formatted: string | null
  gross_margin_pct: number | null
  debt_to_equity: number | null
  employee_count: number | null
  current_price: number | null
  currency: string
  price_history: PricePoint[]
  price_change_1y: number | null
  price_change_5y: number | null
  analyst_recommendation: string | null
  analyst_count: number | null
  target_price_mean: number | null
  target_price_high: number | null
  target_price_low: number | null
  financial_summary: string
  company_description: string
  ceo: string | null
  founded: number | null
  headquarters: string
  website: string | null
}

export interface RiskFlag {
  category: string
  description: string
  severity: "low" | "medium" | "high"
  source_url: string
}

export interface SkepticOutput {
  company_name: string
  sentiment_score: number
  sentiment_label: string
  risk_flags: RiskFlag[]
  positive_signals: string[]
  employee_sentiment: string
  public_sentiment: string
  summary: string
  sources_analyzed: number
}

export interface HitlPayload {
  company: string
  sentiment_score: number | null
  sentiment_label: string | null
  risk_flags: RiskFlag[]
  positive_signals: string[]
  summary: string
  sources_analyzed: number
}

export interface Source {
  url: string
  title: string
  agent: string
  retrieved_at: string
  tier?: number  // 1=primary, 2=secondary, 3=acceptable, null=unknown
}

export interface AgentOutputs {
  scout?: ScoutOutput
  accountant?: AccountantOutput
  skeptic?: SkepticOutput
}