import os
from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from tavily import TavilyClient

from firmsignal.models import ScoutOutput
from firmsignal.state import FirmState
from firmsignal.tools.cache import get_cached, set_cached
from firmsignal.tools.source_quality import (
    EXCLUDED_DOMAINS,
    TRUSTED_NEWS_DOMAINS,
    filter_results,
    get_source_tier,
)


# ─── LLM setup ────────────────────────────────────────────────────────────────
#
# Claude Haiku for the Scout — it's fast and cheap for research/extraction tasks.
# Temperature 0 = deterministic. You don't want creativity here, you want accuracy.
# .with_structured_output() uses Anthropic's tool_use under the hood, which is
# more reliable than asking for JSON in the prompt.

def _get_llm():
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0,
        max_tokens=2048,
    ).with_structured_output(ScoutOutput)


# ─── Search layer ─────────────────────────────────────────────────────────────

def _search(
    client: TavilyClient,
    query: str,
    max_results: int = 5,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> list[dict]:
    """
    Runs a Tavily search, checking the Redis cache first.
    On cache miss: hits Tavily API, stores result, returns it.
    On Tavily failure: returns empty list (agent handles gracefully).
    """
    cached = get_cached(query)
    if cached is not None:
        print(f"    [cache hit] {query}")
        return cached

    print(f"    [tavily]    {query}")
    try:
        kwargs: dict = {
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False,
        }
        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains
        response = client.search(**kwargs)
        results = response.get("results", [])
        set_cached(query, results)
        return results
    except Exception as e:
        print(f"    [tavily error] {e}")
        return []


# ─── Prompt ───────────────────────────────────────────────────────────────────

_SYSTEM = """\
You are a senior research analyst building a company intelligence brief.
You will receive web search results and must extract structured information precisely.

Rules:
- Only include facts that appear in the provided search results. Do not invent anything.
- Only use URLs that appear verbatim in the results.
- For news_items: pick the 5 most recent and relevant. Ignore press releases older than 6 months.
- For leadership_changes: only confirmed changes from the past 12 months.
- Summaries must be 2-3 sentences maximum.
- If a field has no relevant data, return an empty list — do not guess."""


def _build_prompt(company: str, results: list[dict], today: str) -> str:
    blocks = []
    for i, r in enumerate(results, 1):
        blocks.append(
            f"[{i}]\n"
            f"Title:   {r.get('title', 'N/A')}\n"
            f"URL:     {r.get('url', 'N/A')}\n"
            f"Content: {r.get('content', 'N/A')}\n"
        )

    return (
        f"Research target: {company}\n"
        f"Today's date: {today}\n\n"
        f"SEARCH RESULTS:\n"
        f"{'—' * 60}\n"
        f"{chr(10).join(blocks)}"
        f"{'—' * 60}\n\n"
        f"Extract all news items, leadership changes, and key events "
        f"from these results for {company}. "
        f"Use research_date = '{today}'."
    )


# ─── The node ─────────────────────────────────────────────────────────────────

def scout_node(state: FirmState) -> dict:
    """
    LangGraph node — The Scout.

    Runs two Tavily searches (recent news + leadership changes),
    passes all results to Claude Haiku for structured extraction,
    and returns the validated ScoutOutput as a dict update to FirmState.

    On any failure, sets state["error"] instead of raising — this lets
    the graph continue or route to an error handler rather than crashing.
    """
    company = state["company_name"]
    today = datetime.now().strftime("%Y-%m-%d")
    year = today[:4]

    print(f"\n[Scout] Starting research on '{company}'...")

    try:
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

        # Two targeted queries gives better coverage than one broad search.
        # Leadership changes are often underrepresented in general news results.
        news_results = filter_results(
            _search(
                tavily,
                query=f"{company} latest news {year}",
                max_results=5,
                include_domains=TRUSTED_NEWS_DOMAINS,
                exclude_domains=EXCLUDED_DOMAINS,
            ),
            min_tier=2,
        )
        leadership_results = filter_results(
            _search(
                tavily,
                query=f"{company} CEO leadership executive changes {year}",
                max_results=3,
                include_domains=TRUSTED_NEWS_DOMAINS,
                exclude_domains=EXCLUDED_DOMAINS,
            ),
            min_tier=2,
        )

        all_results = news_results + leadership_results

        # Graceful fallback — no crash, just an informative error in state
        if not all_results:
            return {
                "error": (
                    f"Scout: No search results found for '{company}'. "
                    "Check your TAVILY_API_KEY or try a different company name."
                )
            }

        # Extract structured data via Claude Haiku
        llm = _get_llm()
        output: ScoutOutput = llm.invoke(
            [
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=_build_prompt(company, all_results, today)),
            ]
        )

        # Build the sources list — these flow into the final citation layer
        new_sources = [
            {
                "url": r["url"],
                "title": r.get("title", ""),
                "agent": "scout",
                "retrieved_at": today,
                "tier": get_source_tier(r["url"]),
            }
            for r in all_results
            if r.get("url")
        ]

        print(
            f"[Scout] Done — "
            f"{len(output.news_items)} news items, "
            f"{len(output.leadership_changes)} leadership changes, "
            f"{len(output.key_events)} key events"
        )

        return {
            "scout_output": output.model_dump(),
            "sources": state.get("sources", []) + new_sources,
            "error": None,
        }

    except Exception as e:
        # Catch-all: LLM failures, Pydantic validation errors, etc.
        print(f"[Scout] Unexpected error: {e}")
        return {"error": f"Scout failed: {type(e).__name__}: {e}"}