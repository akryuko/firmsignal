from firmsignal.tools.source_quality import get_source_tier, filter_results

def test_reuters_is_tier_1():
    assert get_source_tier("https://www.reuters.com/article/xyz") == 1

def test_linkedin_is_blocked():
    assert get_source_tier("https://www.linkedin.com/posts/random") == -1

def test_unknown_domain_returns_none():
    assert get_source_tier("https://randomsite.com/article") is None

def test_filter_removes_blocked():
    results = [
        {"url": "https://reuters.com/article"},
        {"url": "https://linkedin.com/posts/xyz"},
        {"url": "https://bloomberg.com/news"},
    ]
    filtered = filter_results(results, min_tier=2)
    urls = [r["url"] for r in filtered]
    assert "https://linkedin.com/posts/xyz" not in urls
    assert "https://reuters.com/article" in urls

def test_filter_fallback_on_empty():
    results = [{"url": "https://linkedin.com/posts/xyz"}]
    filtered = filter_results(results, min_tier=2, fallback_if_empty=True)
    assert len(filtered) == 0

def test_cloudflare_title_blocked():
    from firmsignal.tools.source_quality import is_valid_result
    assert not is_valid_result({"title": "Just a moment...", "url": "https://x.com"})
    assert is_valid_result({"title": "Boeing reports Q4 results", "url": "https://reuters.com"})