import json
import re

from pydantic import BaseModel, Field, field_validator, model_validator


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

    @field_validator("news_items", mode="before")
    @classmethod
    def _coerce_news_items(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        try:
            return json.loads(v)
        except Exception:
            return []


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

    # Analyst consensus (Wall Street, public companies only)
    analyst_recommendation: str | None = None    # "strongBuy" | "buy" | "hold" | "sell" | "strongSell"
    analyst_count: int | None = None
    target_price_mean: float | None = None
    target_price_high: float | None = None
    target_price_low: float | None = None

    # Company profile (for Synthesizer About section)
    ceo: str | None = None
    founded: int | None = None
    headquarters: str = ""
    website: str | None = None
    company_description: str = ""   # raw longBusinessSummary trimmed to 3 sentences

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
        default="",
        description="Best matching URL from the provided sources. Use the closest match — leave empty only if no source is even tangentially relevant."
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
        description=(
            "REQUIRED. 3–5 risk flags extracted from the sources. "
            "An empty list is never acceptable — always return at least 1 flag, "
            "even if severity is low. Prioritise patterns over single incidents."
        ),
    )
    positive_signals: list[str] = Field(
        default_factory=list,
        description=(
            "REQUIRED. 1–3 short phrases describing genuine competitive advantages or "
            "financial strengths visible in the sources. "
            "An empty list is never acceptable — always return at least 1 signal."
        ),
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

    @field_validator("positive_signals", mode="before")
    @classmethod
    def _coerce_positive_signals(cls, v: object) -> object:
        """
        Haiku sometimes returns a bare string (or XML-tagged string) instead
        of a list when structured output falls back to XML extraction.
        Strip tags and split into lines rather than crashing.
        """
        if not isinstance(v, str):
            return v
        cleaned = re.sub(r"<[^>]+>", "", v)
        return [
            line.strip().lstrip("•-*·").strip()
            for line in cleaned.splitlines()
            if line.strip()
        ]

    @field_validator("risk_flags", mode="before")
    @classmethod
    def _coerce_risk_flags(cls, v: object) -> object:
        """
        When Haiku emits XML instead of JSON for the risk_flags list, LangChain
        hands us the raw XML string.  Try to recover the structured data from it
        rather than silently dropping everything.
        """
        if isinstance(v, (list, type(None))):
            return v
        if not isinstance(v, str):
            return []

        # Attempt to reconstruct from XML parameter tags, e.g.:
        #   <parameter name="category">Operations</parameter>
        #   <parameter name="description">...</parameter>  ...
        categories    = re.findall(r'<parameter name="category">(.*?)</parameter>',    v, re.DOTALL)
        descriptions  = re.findall(r'<parameter name="description">(.*?)</parameter>',  v, re.DOTALL)
        severities    = re.findall(r'<parameter name="severity">(.*?)</parameter>',     v, re.DOTALL)
        source_urls   = re.findall(r'<parameter name="source_url">(.*?)</parameter>',   v, re.DOTALL)

        if categories:
            return [
                {
                    "category":   categories[i].strip(),
                    "description": descriptions[i].strip() if i < len(descriptions) else "See sources.",
                    "severity":   (severities[i].strip()   if i < len(severities)   else "medium"),
                    "source_url": (source_urls[i].strip()  if i < len(source_urls)  else ""),
                }
                for i in range(len(categories))
            ]

        # No recoverable structure — return empty rather than crash
        return []

    @model_validator(mode="after")
    def _ensure_non_empty(self) -> "SkepticOutput":
        """
        Safety net: if the LLM still returns empty lists despite the system prompt
        and field description constraints, insert a placeholder rather than silently
        surfacing 0 flags / 0 signals in the UI.
        """
        if not self.risk_flags:
            self.risk_flags = [RiskFlag(
                category="Operations",
                description=(
                    "Insufficient source data to identify specific risk flags. "
                    "Manual review recommended."
                ),
                severity="low",
                source_url="",
            )]
        if not self.positive_signals:
            self.positive_signals = [
                "No specific positive signals identified from available sources."
            ]
        return self


# ─── Synthesizer models ────────────────────────────────────────────────────────

class SynthesizerOutput(BaseModel):
    brief: str = Field(description="Full Markdown intelligence brief with inline citations")
    word_count: int = 0
    sources_cited: int = Field(
        default=0,
        description="Number of unique [N] citations used in the brief"
    )
    generated_at: str = ""