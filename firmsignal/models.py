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
    category: str = Field(
        description=(
            "One of: Culture, Legal, Financial, Regulatory, "
            "Competition, Leadership, Operations"
        )
    )
    description: str = Field(
        description="1-2 sentence description of the specific risk"
    )
    severity: str = Field(
        description="One of: low, medium, high"
    )
    source_url: str = Field(
        description="URL of the source that surfaced this risk — must appear verbatim in the provided sources"
    )


class SkepticOutput(BaseModel):
    company_name: str

    sentiment_score: float = Field(
        description="Overall sentiment from -1.0 (extremely negative) to 1.0 (extremely positive), based strictly on the evidence"
    )
    sentiment_label: str = Field(
        description="One of: very_negative, negative, neutral, positive, very_positive"
    )

    risk_flags: list[RiskFlag] = Field(
        default_factory=list,
        description="Up to 5 most significant risk flags. Prioritise patterns over single incidents."
    )
    positive_signals: list[str] = Field(
        default_factory=list,
        description="Up to 3 genuinely notable positives. Exclude obvious PR talking points."
    )

    employee_sentiment: str = Field(
        description="2-sentence summary of what employees say about working here"
    )
    public_sentiment: str = Field(
        description="2-sentence summary of investor and public perception"
    )
    summary: str = Field(
        description="3-4 sentence overall risk assessment written for the Synthesizer. Be direct."
    )

    sources_analyzed: int = Field(default=0)

# ─── Synthesizer models ────────────────────────────────────────────────────────

class SynthesizerOutput(BaseModel):
    brief: str = Field(description="Full Markdown intelligence brief with inline citations")
    word_count: int = 0
    sources_cited: int = Field(
        default=0,
        description="Number of unique [N] citations used in the brief"
    )
    generated_at: str = ""