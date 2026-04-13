from pydantic import BaseModel, Field


# ─── Scout models ─────────────────────────────────────────────────────────────

class NewsItem(BaseModel):
    headline: str = Field(description="The news headline")
    url: str = Field(description="Source URL — must appear in search results")
    date: str = Field(description="Publication date (YYYY-MM-DD), or 'unknown'")
    summary: str = Field(description="2-3 sentence summary of the article")


class LeadershipChange(BaseModel):
    name: str = Field(description="Executive's full name")
    role: str = Field(description="Their title or role")
    change_type: str = Field(description="One of: joined, departed, promoted, other")
    date: str = Field(description="When the change occurred, or 'unknown'")
    source_url: str = Field(description="URL where this was reported")


class ScoutOutput(BaseModel):
    company_name: str = Field(description="Company being researched")
    news_items: list[NewsItem] = Field(
        description="Up to 5 most recent and relevant news items"
    )
    leadership_changes: list[LeadershipChange] = Field(default_factory=list)
    key_events: list[str] = Field(
        default_factory=list,
        description="Other significant events: acquisitions, launches, controversies",
    )
    research_date: str = Field(description="Date research was conducted (YYYY-MM-DD)")


# ─── Placeholder models for Accountant + Skeptic (you'll fill these in later) ─

class AccountantOutput(BaseModel):
    company_name: str
    ticker: str | None = None
    revenue_ttm: float | None = None
    revenue_currency: str = "USD"
    pe_ratio: float | None = None
    debt_to_equity: float | None = None
    employee_count: int | None = None
    market_cap: float | None = None
    financial_summary: str = ""


class RiskFlag(BaseModel):
    category: str
    description: str
    severity: str  # "low" | "medium" | "high"
    source_url: str


class SkepticOutput(BaseModel):
    company_name: str
    sentiment_score: float = 0.0  # -1.0 to 1.0
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    summary: str = ""