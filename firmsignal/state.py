from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class NewsItem(TypedDict):
    headline: str
    url: str
    date: str
    summary: str


class ScoutOutput(TypedDict):
    company_name: str
    news_items: list[NewsItem]
    recent_leadership_changes: list[str]
    key_events: list[str]


class FinancialMetrics(TypedDict):
    revenue_ttm: float | None
    revenue_currency: str
    pe_ratio: float | None
    debt_to_equity: float | None
    employee_count: int | None
    market_cap: float | None


class AccountantOutput(TypedDict):
    company_name: str
    ticker: str | None
    metrics: FinancialMetrics
    summary: str


class RiskFlag(TypedDict):
    category: str          # e.g. "Culture", "Legal", "Financial"
    description: str
    severity: str          # "low" | "medium" | "high"
    source_url: str


class SkepticOutput(TypedDict):
    company_name: str
    sentiment_score: float    # -1.0 to 1.0
    risk_flags: list[RiskFlag]
    summary: str


class FirmState(TypedDict):
    company_name: str
    scout_output: ScoutOutput | None
    accountant_output: AccountantOutput | None
    skeptic_output: SkepticOutput | None
    hitl_approved: bool
    hitl_edits: str | None      # human can overwrite risk flags
    final_brief: str | None
    sources: list[dict]         # all cited URLs collected during run
    messages: Annotated[list, add_messages]
    error: str | None           # captures agent failures gracefully