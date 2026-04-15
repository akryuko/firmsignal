import os
from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from tavily import TavilyClient

from firmsignal.models import SkepticOutput
from firmsignal.state import FirmState
from firmsignal.tools.cache import get_cached, set_cached
from firmsignal.tools.source_quality import (
    EXCLUDED_DOMAINS,
    TRUSTED_NEWS_DOMAINS,
    TRUSTED_SENTIMENT_DOMAINS,
    filter_results,
    get_source_tier,
)


# ─── Reddit ───────────────────────────────────────────────────────────────────

# Finance subs: investor and public sentiment
# Employee subs: culture, workload, management quality
FINANCE_SUBS = ["investing", "stocks", "wallstreetbets"]
EMPLOYEE_SUBS = ["cscareerquestions", "jobs", "layoffs"]


def _reddit_client():
    cid = os.getenv("REDDIT_CLIENT_ID")
    secret = os.getenv("REDDIT_CLIENT_SECRET")
    agent = os.getenv("REDDIT_USER_AGENT", "firmsignal/1.0")
    if not cid or not secret:
        return None
    try:
        import praw
        return praw.Reddit(client_id=cid, client_secret=secret, user_agent=agent)
    except Exception as e:
        print(f"    [reddit] Init failed: {e}")
        return None


def _search_reddit(company: str) -> list[dict]:
    """
    Searches 6 subreddits — 3 finance, 3 employee — for mentions of the company
    in the past year. Returns [] gracefully if PRAW isn't configured.

    3 posts per subreddit keeps us well within Reddit's rate limits.
    We pass the full post text (truncated) to Claude rather than just titles —
    titles alone miss a lot of nuance in comment threads.
    """
    reddit = _reddit_client()
    if reddit is None:
        print("    [reddit] Credentials not set — skipping Reddit")
        return []

    posts = []
    for sub_name in FINANCE_SUBS + EMPLOYEE_SUBS:
        try:
            results = reddit.subreddit(sub_name).search(
                company,
                limit=3,
                sort="relevance",
                time_filter="year",
            )
            for post in results:
                posts.append({
                    "subreddit": f"r/{sub_name}",
                    "title": post.title,
                    "score": post.score,
                    "url": f"https://reddit.com{post.permalink}",
                    "text": post.selftext[:400] if post.selftext else "",
                    "num_comments": post.num_comments,
                })
        except Exception as e:
            print(f"    [reddit] r/{sub_name} failed: {e}")

    print(f"    [reddit] {len(posts)} posts across {len(FINANCE_SUBS + EMPLOYEE_SUBS)} subreddits")
    return posts


# ─── Tavily ───────────────────────────────────────────────────────────────────

def _search(
    client: TavilyClient,
    query: str,
    max_results: int = 4,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> list[dict]:
    """Tavily search with shared Redis cache."""
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
You are a critical research analyst. Your job is to identify risks and red flags.
Be genuinely skeptical — your role is to find real problems, not summarise PR material.

SOURCE QUALITY RULES — MANDATORY:
- Weight evidence by source credibility. Reuters, Bloomberg, SEC filings, and official
  company communications carry 10x more weight than blog posts or anonymous reviews.
- A risk flag requires at least ONE credible primary or secondary source.
  A single Glassdoor review is noise. Patterns across 10+ reviews = signal.
- If the only source for a claim is a personal blog, forum post, or unverified social
  media — do not include it as a risk flag.
- For legal/regulatory risks: only cite if from the regulator itself, a major news
  outlet, or official court records.
- For financial risks: only cite if from SEC filings, earnings calls, or Tier 1
  financial press (Bloomberg, Reuters, FT, WSJ).
- Distinguish between: confirmed facts, credible reports, and rumors. Label each
  risk flag's evidence type in your description using these prefixes:
    "Confirmed:" — from official source or major outlet
    "Reported:"  — from credible secondary source
    "Alleged:"   — from lawsuit or regulatory filing not yet resolved
    "Rumored:"   — multiple credible sources but unconfirmed

ANALYSIS RULES:
- Prioritise patterns over single incidents. One complaint = noise. Five = signal.
- Distinguish company-generated content from genuine employee or investor opinions.
- risk_flags: only substantive risks, not trivial criticism. Max 5.
- severity "high": could materially harm the company, employees, or investors.
- severity "medium": real concern worth monitoring.
- severity "low": minor issue, worth noting.
- positive_signals: only genuinely notable positives. Exclude obvious PR talking points. Max 3.
- sentiment_score: based strictly on the evidence provided. Do not anchor to the company's reputation.
- If data is sparse, say so clearly in the summary. Do not pad with speculation.
- source_url: must appear verbatim in the provided sources. Never invent URLs."""


def _build_prompt(company: str, reddit_posts: list[dict], web_results: list[dict]) -> str:
    sections = []

    if reddit_posts:
        sections.append("=== REDDIT POSTS ===")
        for p in reddit_posts:
            sections.append(
                f"Subreddit: {p['subreddit']} | Score: {p['score']} | "
                f"Comments: {p['num_comments']}\n"
                f"Title: {p['title']}\n"
                f"URL: {p['url']}\n"
                f"Body: {p['text'] or '(no body text)'}"
            )

    if web_results:
        sections.append("=== WEB SOURCES (Glassdoor, News, Reviews) ===")
        for r in web_results:
            sections.append(
                f"Title:   {r.get('title', 'N/A')}\n"
                f"URL:     {r.get('url', 'N/A')}\n"
                f"Content: {r.get('content', 'N/A')[:500]}"
            )

    body = "\n\n".join(sections) if sections else "No sources were found for this company."

    return (
        f"Company: {company}\n"
        f"Sources: {len(reddit_posts)} Reddit posts + {len(web_results)} web results\n\n"
        f"{'─' * 60}\n"
        f"{body}\n"
        f"{'─' * 60}\n\n"
        f"Analyse the above and extract structured risk intelligence for {company}."
    )


# ─── The node ─────────────────────────────────────────────────────────────────

def skeptic_node(state: FirmState) -> dict:
    """
    LangGraph node — The Skeptic.

    Sequence:
    1. Search Reddit (finance + employee subreddits) via PRAW
    2. Search Tavily for Glassdoor, controversies, and layoff reports (3 queries)
    3. Feed everything to Claude Haiku with an explicitly skeptical system prompt
    4. Return structured SkepticOutput with risk flags, sentiment, and signals

    Degrades gracefully on Reddit failure — Tavily alone still produces
    useful output. Never crashes the graph.
    """
    company = state["company_name"]
    year = datetime.now().strftime("%Y")
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"\n[Skeptic] Starting sentiment & risk analysis on '{company}'...")

    try:
        # Step 1: Reddit
        reddit_posts = _search_reddit(company)

        # Step 2: Three Tavily queries targeting the three main risk areas
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

        glassdoor = filter_results(
            _search(
                tavily,
                f"{company} Glassdoor employee reviews culture {year}",
                include_domains=TRUSTED_SENTIMENT_DOMAINS,
                exclude_domains=EXCLUDED_DOMAINS,
            ),
            min_tier=3,
        )
        controversy = filter_results(
            _search(
                tavily,
                f"{company} controversy lawsuit scandal criticism {year}",
                include_domains=TRUSTED_NEWS_DOMAINS,
                exclude_domains=EXCLUDED_DOMAINS,
            ),
            min_tier=2,
        )
        layoffs = filter_results(
            _search(
                tavily,
                f"{company} layoffs workforce reduction problems {year}",
                include_domains=TRUSTED_NEWS_DOMAINS,
                exclude_domains=EXCLUDED_DOMAINS,
            ),
            min_tier=2,
        )

        web_results = glassdoor + controversy + layoffs
        total = len(reddit_posts) + len(web_results)

        print(f"[Skeptic] Analysing {total} sources ({len(reddit_posts)} Reddit · {len(web_results)} web)")

        # Step 3: Structured extraction — Claude Haiku with skeptical system prompt
        llm = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            temperature=0,
            max_tokens=2048,
        ).with_structured_output(SkepticOutput)

        output: SkepticOutput = llm.invoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=_build_prompt(company, reddit_posts, web_results)),
        ])

        # Hard clamp — Pydantic validates type but not range
        output.sentiment_score = max(-1.0, min(1.0, output.sentiment_score))
        output.sources_analyzed = total

        # Collect all sources for the final citation layer
        new_sources = [
            {
                "url": p["url"],
                "title": p["title"],
                "agent": "skeptic",
                "retrieved_at": today,
                "tier": get_source_tier(p["url"]),
            }
            for p in reddit_posts
        ] + [
            {
                "url": r["url"],
                "title": r.get("title", ""),
                "agent": "skeptic",
                "retrieved_at": today,
                "tier": get_source_tier(r["url"]),
            }
            for r in web_results
            if r.get("url")
        ]

        print(
            f"[Skeptic] Done — "
            f"sentiment: {output.sentiment_score:+.2f} ({output.sentiment_label}) · "
            f"{len(output.risk_flags)} risk flags · "
            f"{len(output.positive_signals)} positive signals"
        )

        return {
            "skeptic_output": output.model_dump(),
            "sources": state.get("sources", []) + new_sources,
            "error": None,
        }

    except Exception as e:
        print(f"[Skeptic] Error: {e}")
        return {"error": f"Skeptic failed: {type(e).__name__}: {e}"}