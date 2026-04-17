import concurrent.futures
import re
from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from firmsignal.models import SynthesizerOutput
from firmsignal.state import FirmState
from firmsignal.tools.retry import llm_retry
from firmsignal.tools.source_quality import get_source_tier, is_valid_result


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

SOURCE QUALITY RULES:
- Prefer citing Tier 1 sources (Reuters, Bloomberg, SEC, official company communications)
  over secondary sources when both support the same claim.
- Never cite a source that looks like a personal social media post or random blog.
- For financial figures: only cite from SEC filings, earnings releases, or major
  financial press (Bloomberg, Reuters, FT, WSJ).
- Label unconfirmed claims clearly: "reportedly", "according to unverified reports" —
  never state them as established fact.

WRITING RULES:
- Lead with the most important insight in the Executive Summary — risk or opportunity.
- Use exact numbers wherever available. Never round aggressively.
- Do not soften red flags. Be direct.
- Incorporate any analyst notes from the human reviewer naturally into the analysis.
- Omit sections where data is genuinely missing — do not pad.
- No filler phrases: "it is worth noting", "it is important to consider", "in conclusion".
- In Recent Developments: every event must include one sentence of analytical implication.
  Not "Apple launched X at $Y" but "Apple launched X at $Y, undercutting competitors by ~20%
  and signalling a deliberate shift toward volume over margin." Ask: what does this event mean
  for the company's strategy, competitive position, or financial trajectory?

ABOUT SECTION — write 3-4 sentences, no citations needed:
1. What the company does — plain English, not SEC boilerplate
2. Size and leadership — employees, HQ, founded year (if known), CEO name
3. Business model — how they primarily make money (name the revenue segments)
4. Strategic moment — one sentence on where they are right now (shift, inflection, challenge)
Use actual numbers from the ABOUT DATA and FINANCIAL DATA blocks. Do not copy the raw
description verbatim.

OUTPUT FORMAT (use exactly these section headers):

# {Company} — Intelligence Brief
*{date} · {n} sources analysed · FirmSignal*

## About

## Executive Summary

## Recent Developments

## Financial Overview
(Open this section with the YFINANCE_ATTRIBUTION line from the FINANCIAL DATA block.
Do NOT add [N] citations for figures from that block — the attribution line is sufficient.
Only cite [N] for claims that match an entry in the NUMBERED SOURCES list.)

## Risk Assessment

## Signal Summary
**Bull case:** (2-3 sentences, specific numbers and named competitors/markets — no generic phrases
like "strong momentum" or "solid fundamentals". Explain the mechanism: why does this advantage
translate into revenue, margin, or market share gain, and over what timeframe?)
**Bear case:** (2-3 sentences, same standard — name the specific risk vector, quantify the
exposure where possible, and state what would have to happen for the bear case to materialise.
Fold in employee sentiment and public/investor sentiment from the RISK ANALYSIS block here
if they support the bear case — do not create separate sections for them.)

(Do NOT include a Sources section — citations are handled separately by the UI)"""


# ─── Source validation ────────────────────────────────────────────────────────

def _validate_sources(sources: list[dict]) -> list[dict]:
    """
    Drops blocked sources before the Synthesizer sees them:
    - Domain tier == -1 (hard-blocked domains)
    - Title matches a known challenge/error page (Cloudflare, WAF, 403, etc.)
    Unknown domains (tier == None) are kept — better to cite than to drop.
    """
    clean = []
    for s in sources:
        if not is_valid_result(s):
            print(f"[Synthesizer] Dropping challenge/error page: '{s.get('title')}' — {s.get('url')}")
            continue
        tier = get_source_tier(s.get("url", ""))
        if tier == -1:
            print(f"[Synthesizer] Dropping blocked source: {s.get('url')}")
            continue
        clean.append(s)
    return clean


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

    # ── About data ─────────────────────────────────────────────────────────────
    about_parts = []
    if acc.get("ceo"):
        about_parts.append(f"  CEO:          {acc['ceo']}")
    if acc.get("founded"):
        about_parts.append(f"  Founded:      {acc['founded']}")
    if acc.get("headquarters"):
        about_parts.append(f"  HQ:           {acc['headquarters']}")
    if acc.get("employee_count"):
        about_parts.append(f"  Employees:    {acc['employee_count']:,}")
    if acc.get("website"):
        about_parts.append(f"  Website:      {acc['website']}")
    if acc.get("sector"):
        about_parts.append(f"  Sector:       {acc.get('sector')} / {acc.get('industry')}")
    if acc.get("company_description"):
        about_parts.append(f"  Description:  {acc['company_description']}")
    about_block = "\n".join(about_parts) if about_parts else "  (no structured data available)"

    # ── Accountant ─────────────────────────────────────────────────────────────
    if acc.get("is_public"):
        employees = f"{acc['employee_count']:,}" if acc.get("employee_count") else "N/A"
        fin_block = f"""\
  YFINANCE_ATTRIBUTION: *Financial data sourced from Yahoo Finance via yfinance as of {today}.*
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

ABOUT DATA (use to write the ## About section):
{about_block}

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


# ─── LLM invoke ───────────────────────────────────────────────────────────────

@llm_retry
def _invoke_llm(llm, messages):
    return llm.invoke(messages)


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
    sources = _validate_sources(state.get("sources", []))

    print(f"\n[Synthesizer] Generating intelligence brief for '{company}'...")
    print(f"[Synthesizer] Using Claude Sonnet · {len(sources)} sources available")

    try:
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.1,   # tiny amount of creativity — better prose than 0
            max_tokens=4096,
        )

        context = _build_context(state, sources)
        messages = [SystemMessage(content=_SYSTEM), HumanMessage(content=context)]

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_invoke_llm, llm, messages)
        executor.shutdown(wait=False)
        try:
            response = future.result(timeout=90)
        except concurrent.futures.TimeoutError:
            print("[Synthesizer] Synthesis timed out after 90s")
            partial_brief = (
                "> Note: Report generation timed out. "
                "The following is a partial summary based on available data."
            )
            output = SynthesizerOutput(
                brief=partial_brief,
                word_count=len(partial_brief.split()),
                sources_cited=0,
                generated_at=today,
            )
            return {"final_brief": output.brief, "error": None}

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
