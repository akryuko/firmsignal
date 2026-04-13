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

class PricePoint(BaseModel):
    date: str = Field(description="Month in YYYY-MM format")
    close: float = Field(description="Adjusted monthly closing price")


class AccountantOutput(BaseModel):
    company_name: str
    ticker: str | None = None
    is_public: bool = False
    sector: str = ""
    industry: str = ""

    # Market metrics
    market_cap: float | None = None
    market_cap_formatted: str | None = None     # "$2.7T"
    pe_ratio: float | None = None

    # Income statement
    revenue_ttm: float | None = None
    revenue_formatted: str | None = None         # "$130.5B"
    gross_margin_pct: float | None = None        # 74.6 (not 0.746)

    # Balance sheet
    debt_to_equity: float | None = None

    # Company size
    employee_count: int | None = None

    # Price data
    current_price: float | None = None
    currency: str = "USD"
    price_history: list[PricePoint] = Field(default_factory=list)
    price_change_1y: float | None = None         # percentage, e.g. 65.3
    price_change_5y: float | None = None

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