import re
from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from firmsignal.models import SynthesizerOutput
from firmsignal.state import FirmState


# ─── System prompt ─────────────────────────────────────────────────────────────
#
# The framing matters: "institutional clients" and "senior analyst" pull Claude
# toward precise, direct prose rather than hedged summaries.
# The citation rule is the most important instruction — it's repeated twice
# because Claude Sonnet reliably follows it when emphasised.

_SYSTEM = """\
You are a senior equity research analyst writing a company intelligence brief for institutional clients.

CITATION RULE — MANDATORY:
Every factual claim must end with an inline citation: [1], [2], etc.
Match each claim to the closest source URL in the numbered source list.
A brief with uncited claims is unacceptable.

WRITING RULES:
- Lead with the most important insight in the Executive Summary — risk or opportunity.
- Use exact numbers wherever available. Never round aggressively.
- Do not soften red flags. Be direct.
- Incorporate any analyst notes from the human reviewer naturally into the analysis.
- Omit sections where data is genuinely missing — do not pad.
- No filler phrases: "it is worth noting", "it is important to consider", "in conclusion".

OUTPUT FORMAT (use exactly these section headers):

# {Company} — Intelligence Brief
*{date} · {n} sources analysed · FirmSignal*

## Executive Summary

## Recent Developments

## Financial Overview

## Risk Assessment

## Signal Summary
**Bull case:**
**Bear case:**

(Do NOT include a Sources section — citations are handled separately by the UI)"""


# ─── Context builder ───────────────────────────────────────────────────────────

def _url_to_index(sources: list[dict]) -> dict[str, int]:
    """
    Build a URL → citation number map from the sources list.
    Used to pre-annotate each data section so Claude can match
    claims to [N] references without hallucinating URLs.
    """
    mapping = {}
    for i, source in enumerate(sources, 1):
        url = source.get("url", "")
        if url and url not in mapping:
            mapping[url] = i
    return mapping


def _format_sources(sources: list[dict]) -> str:
    seen = {}
    lines = []
    n = 1
    for s in sources:
        url = s.get("url", "")
        if url and url not in seen:
            seen[url] = n
            title = s.get("title") or "Untitled"
            lines.append(f"[{n}] {title} — {url}")
            n += 1
    return "\n".join(lines)


def _build_context(state: FirmState, sources: list[dict]) -> str:
    company   = state["company_name"]
    today     = datetime.now().strftime("%Y-%m-%d")
    scout     = state.get("scout_output") or {}
    acc       = state.get("accountant_output") or {}
    skep      = state.get("skeptic_output") or {}
    edits     = state.get("hitl_edits")
    url_idx   = _url_to_index(sources)

    def cite(url: str) -> str:
        n = url_idx.get(url)
        return f"[{n}]" if n else ""

    # ── Scout ──────────────────────────────────────────────────────────────────
    news_lines = []
    for item in scout.get("news_items", []):
        news_lines.append(
            f"  - {item['headline']} ({item['date']}): {item['summary']} "
            f"{cite(item['url'])} | url: {item['url']}"
        )

    leadership_lines = []
    for c in scout.get("leadership_changes", []):
        leadership_lines.append(
            f"  - {c['name']} ({c['role']}): {c['change_type']} — {c['date']} "
            f"{cite(c['source_url'])} | url: {c['source_url']}"
        )

    events = scout.get("key_events", [])

    # ── Accountant ─────────────────────────────────────────────────────────────
    if acc.get("is_public"):
        employees = f"{acc['employee_count']:,}" if acc.get("employee_count") else "N/A"
        fin_block = f"""\
  Ticker:        {acc.get('ticker')}
  Market Cap:    {acc.get('market_cap_formatted')} ({acc.get('currency')})
  Current Price: ${acc.get('current_price')}
  P/E Ratio:     {acc.get('pe_ratio')}
  Revenue TTM:   {acc.get('revenue_formatted')}
  Gross Margin:  {acc.get('gross_margin_pct')}%
  Debt/Equity:   {acc.get('debt_to_equity')}
  Employees:     {employees}
  1Y Change:     {acc.get('price_change_1y')}%
  5Y Change:     {acc.get('price_change_5y')}%
  Analyst note:  {acc.get('financial_summary')}"""
    else:
        fin_block = "  Private company — no public market data available."

    # ── Skeptic ────────────────────────────────────────────────────────────────
    flag_lines = []
    for flag in skep.get("risk_flags", []):
        flag_lines.append(
            f"  [{flag['severity'].upper()}] {flag['category']}: "
            f"{flag['description']} "
            f"{cite(flag['source_url'])} | url: {flag['source_url']}"
        )

    positive_lines = [f"  + {s}" for s in skep.get("positive_signals", [])]

    # ── Analyst note (HITL) ────────────────────────────────────────────────────
    analyst_block = (
        f"\nANALYST NOTE FROM HUMAN REVIEWER (incorporate naturally):\n  {edits}"
        if edits else ""
    )

    return f"""
COMPANY: {company}
DATE: {today}
TOTAL SOURCES: {len(sources)}

NUMBERED SOURCES — use these [N] numbers for citations:
{_format_sources(sources)}

══════════════════════════════════════════════════════

SCOUT DATA:

News Items:
{chr(10).join(news_lines) or '  No recent news found.'}

Leadership Changes:
{chr(10).join(leadership_lines) or '  No leadership changes found.'}

Key Events:
{chr(10).join('  - ' + e for e in events) or '  None.'}

══════════════════════════════════════════════════════

FINANCIAL DATA:
{fin_block}

══════════════════════════════════════════════════════

RISK ANALYSIS:

Sentiment Score: {skep.get('sentiment_score', 0):+.2f} ({skep.get('sentiment_label', 'neutral')})
Sources Analysed: {skep.get('sources_analyzed', 0)}

Risk Flags:
{chr(10).join(flag_lines) or '  No significant risks identified.'}

Positive Signals:
{chr(10).join(positive_lines) or '  None identified.'}

Employee Sentiment: {skep.get('employee_sentiment', 'N/A')}
Public Sentiment:   {skep.get('public_sentiment', 'N/A')}
Skeptic Summary:    {skep.get('summary', 'N/A')}
{analyst_block}

══════════════════════════════════════════════════════

Write the intelligence brief now.
Remember: every factual claim needs a [N] citation matching the source list above.
""".strip()


# ─── The node ─────────────────────────────────────────────────────────────────

def synthesizer_node(state: FirmState) -> dict:
    """
    LangGraph node — The Synthesizer.

    Only runs if hitl_approved is True — the graph's conditional edge
    guarantees this, but we check anyway as a safety net.

    Uses Claude Sonnet (not Haiku) — this is the one place where
    model quality directly determines the value of the entire pipeline.
    Sonnet's superior instruction-following means citations are reliable
    and the prose is genuinely analyst-quality.
    """
    if not state.get("hitl_approved"):
        print("\n[Synthesizer] Run was not approved — skipping.")
        return {"final_brief": None, "error": None}

    company = state["company_name"]
    today   = datetime.now().strftime("%Y-%m-%d")
    sources = state.get("sources", [])

    print(f"\n[Synthesizer] Generating intelligence brief for '{company}'...")
    print(f"[Synthesizer] Using Claude Sonnet · {len(sources)} sources available")

    try:
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.1,   # tiny amount of creativity — better prose than 0
            max_tokens=4096,
        )

        context = _build_context(state, sources)

        response = llm.invoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=context),
        ])

        brief = response.content.strip()

        # Count unique [N] citations in the output
        citations_used = set(re.findall(r'\[(\d+)\]', brief))

        word_count = len(brief.split())

        print(
            f"[Synthesizer] Done — "
            f"{word_count} words · "
            f"{len(citations_used)} unique citations"
        )

        output = SynthesizerOutput(
            brief=brief,
            word_count=word_count,
            sources_cited=len(citations_used),
            generated_at=today,
        )

        return {
            "final_brief": output.brief,
            "error": None,
        }

    except Exception as e:
        print(f"[Synthesizer] Error: {e}")
        return {"error": f"Synthesizer failed: {type(e).__name__}: {e}"}