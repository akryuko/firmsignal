from urllib.parse import urlparse


# ─── Domain lists ─────────────────────────────────────────────────────────────

# Used as Tavily include_domains for general news/financial queries
TRUSTED_NEWS_DOMAINS = [
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "wsj.com",
    "cnbc.com",
    "forbes.com",
    "businessinsider.com",
    "techcrunch.com",
    "theverge.com",
    "wired.com",
    "arstechnica.com",
    "apnews.com",
    "bbc.com",
    "economist.com",
    "nytimes.com",
    "washingtonpost.com",
    "sec.gov",
    "investor.gov",
    "prnewswire.com",
    "businesswire.com",
    "globenewswire.com",
    "fortune.com",
    "inc.com",
    "theregister.com",
]

# Used as Tavily include_domains for employee/culture/sentiment queries
TRUSTED_SENTIMENT_DOMAINS = [
    "glassdoor.com",
    "comparably.com",
    "levels.fyi",
    "bloomberg.com",
    "reuters.com",
    "ft.com",
    "wsj.com",
    "cnbc.com",
    "techcrunch.com",
    "theverge.com",
    "layoffs.fyi",
    "theregister.com",
]

# Always excluded from Tavily searches regardless of query
EXCLUDED_DOMAINS = [
    "linkedin.com",
    "twitter.com",
    "x.com",
    "reddit.com",
    "quora.com",
    "medium.com",
    "substack.com",
    "facebook.com",
    "tiktok.com",
    "youtube.com",
    "wikipedia.org",
    "indeed.com",
]


# ─── Tier definitions ─────────────────────────────────────────────────────────

# Tier 1 = primary sources and major outlets
# Tier 2 = reliable secondary sources
# Tier 3 = acceptable but lower weight
DOMAIN_TIERS: dict[str, int] = {
    # Tier 1 — primary sources
    "sec.gov":            1,
    "investor.gov":       1,
    "reuters.com":        1,
    "bloomberg.com":      1,
    "ft.com":             1,
    "wsj.com":            1,
    "apnews.com":         1,
    "prnewswire.com":     1,
    "businesswire.com":   1,
    "globenewswire.com":  1,
    # Tier 2 — reliable secondary
    "cnbc.com":           2,
    "forbes.com":         2,
    "techcrunch.com":     2,
    "theverge.com":       2,
    "wired.com":          2,
    "economist.com":      2,
    "nytimes.com":        2,
    "washingtonpost.com": 2,
    "bbc.com":            2,
    "glassdoor.com":      2,
    "comparably.com":     2,
    "layoffs.fyi":        2,
    # Tier 3 — acceptable, lower weight
    "businessinsider.com": 3,
    "arstechnica.com":     3,
    "theregister.com":     3,
    "fortune.com":         3,
    "inc.com":             3,
}

# Hard block — never cite these
BLOCKED_DOMAINS: set[str] = {
    "linkedin.com",
    "twitter.com",
    "x.com",
    "reddit.com",
    "quora.com",
    "facebook.com",
    "tiktok.com",
    "youtube.com",
    "medium.com",
    "substack.com",
    "wikipedia.org",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_domain(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
        return host.removeprefix("www.")
    except Exception:
        return ""


def get_source_tier(url: str) -> int | None:
    """
    Returns 1, 2, or 3 for trusted sources.
    Returns None for unknown/unrecognised domains.
    Returns -1 for blocked domains (never cite).
    """
    domain = _get_domain(url)
    if not domain:
        return None
    if domain in BLOCKED_DOMAINS:
        return -1
    for trusted_domain, tier in DOMAIN_TIERS.items():
        if domain == trusted_domain or domain.endswith(f".{trusted_domain}"):
            return tier
    return None


def filter_results(
    results: list[dict],
    min_tier: int = 3,
    fallback_if_empty: bool = True,
) -> list[dict]:
    """
    Filters search results by source quality tier.

    min_tier=1  → only Reuters, Bloomberg, SEC etc.
    min_tier=2  → includes CNBC, TechCrunch, Glassdoor etc.
    min_tier=3  → all known trusted domains

    If fallback_if_empty=True and filtering removes everything, returns the
    original unblocked list rather than empty — so the agent degrades
    gracefully instead of producing no output.
    """
    blocked: list[str] = []
    trusted: list[dict] = []
    unknown: list[dict] = []

    for r in results:
        url  = r.get("url", "")
        tier = get_source_tier(url)

        if tier == -1:
            blocked.append(url)
            continue
        if tier is not None and tier <= min_tier:
            trusted.append(r)
        else:
            unknown.append(r)

    if blocked:
        print(f"    [source filter] Blocked {len(blocked)} untrusted sources:")
        for url in blocked:
            print(f"      \u2717 {url}")

    if not trusted and fallback_if_empty:
        print(
            f"    [source filter] No trusted sources found — "
            f"using {len(unknown)} unknown sources as fallback"
        )
        return unknown

    print(
        f"    [source filter] "
        f"{len(trusted)} trusted \u00b7 {len(unknown)} unknown \u00b7 {len(blocked)} blocked"
    )
    return trusted
