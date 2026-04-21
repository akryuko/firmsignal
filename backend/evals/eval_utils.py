import json
import re
from pathlib import Path
from urllib.parse import urlparse

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage


# ─── Trusted domain list (mirrors source_quality.py) ──────────────────────────

TRUSTED_DOMAINS = {
    "sec.gov", "reuters.com", "bloomberg.com", "ft.com", "wsj.com",
    "cnbc.com", "forbes.com", "techcrunch.com", "theverge.com",
    "wired.com", "apnews.com", "bbc.com", "nytimes.com",
    "washingtonpost.com", "businesswire.com", "prnewswire.com",
    "glassdoor.com", "comparably.com", "economist.com",
}


# ─── Helpers ───────────────────────────────────────────────────────────────────

def load_golden(company_slug: str) -> dict:
    path = Path(__file__).parent / "golden" / f"{company_slug}.json"
    with open(path) as f:
        return json.load(f)


def _haiku():
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0,
        max_tokens=100,
    )


def _ask_judge(question: str, brief: str) -> bool:
    """
    Asks Claude Haiku a yes/no question about the brief.
    Returns True if answer is yes, False if no.
    Cost: ~$0.001 per call.
    """
    response = _haiku().invoke([
        SystemMessage(content=(
            "You are an evaluator checking intelligence briefs. "
            "Answer ONLY with 'yes' or 'no'. No other text."
        )),
        HumanMessage(content=(
            f"Brief to evaluate:\n\n{brief}\n\n"
            f"Question: {question}"
        )),
    ])
    return response.content.strip().lower().startswith("yes")


# ─── Check 1: Stable facts ─────────────────────────────────────────────────────

def check_stable_facts(brief: str, golden: dict) -> dict:
    """
    Simple string matching for facts that never change.
    CEO name, ticker, HQ city etc.
    No LLM needed — fast and free.
    """
    stable_facts = golden.get("stable_facts", [])
    if not stable_facts:
        return {"score": 1.0, "passed": [], "failed": [], "total": 0}

    passed = []
    failed = []

    for fact in stable_facts:
        # Special handling for ticker/exchange facts
        if any(kw in fact.lower() for kw in ["ticker", "trades on", "nasdaq", "nyse"]):
            tickers = [w for w in fact.split() if w.isupper() and 2 <= len(w) <= 5]
            found = any(t in brief for t in tickers) if tickers else False
        else:
            words = [w for w in fact.split() if len(w) > 3 and w[0].isupper()]
            key_terms = words[:3]
            found = all(term.lower() in brief.lower() for term in key_terms)

        if found:
            passed.append(fact)
        else:
            failed.append(fact)

    total = len(stable_facts)
    score = len(passed) / total if total > 0 else 1.0

    return {
        "score": round(score, 3),
        "passed": passed,
        "failed": failed,
        "total": total,
    }


# ─── Check 2: Expected patterns ────────────────────────────────────────────────

def check_patterns(brief: str, golden: dict) -> dict:
    """
    Uses Claude Haiku as judge to check each expected pattern.
    Patterns are intent-based not literal — survives data updates.
    e.g. "mentions revenue figure" not "mentions $94.8B specifically"
    """
    patterns = golden.get("expected_patterns", [])
    if not patterns:
        return {"score": 1.0, "passed": [], "failed": [], "total": 0}

    passed = []
    failed = []

    for pattern in patterns:
        question = f"Does the brief {pattern}?"
        result = _ask_judge(question, brief)
        if result:
            passed.append(pattern)
        else:
            failed.append(pattern)

    total = len(patterns)
    score = len(passed) / total if total > 0 else 1.0

    return {
        "score": round(score, 3),
        "passed": passed,
        "failed": failed,
        "total": total,
    }


# ─── Check 3: Forbidden content ────────────────────────────────────────────────

def check_forbidden_content(brief: str, golden: dict) -> dict:
    """
    Checks that known wrong facts do not appear in the brief.
    Uses both string matching and Claude judge for nuanced cases.
    A single violation is a critical failure.
    """
    forbidden = golden.get("forbidden_content", [])
    if not forbidden:
        return {"score": 1.0, "violations": [], "total": 0}

    violations = []

    for item in forbidden:
        # First try simple string match
        if item.lower() in brief.lower():
            violations.append({"item": item, "method": "string_match"})
            continue

        # If not found literally, ask Claude if the meaning is present
        question = f"Does the brief state or strongly imply that {item}?"
        if _ask_judge(question, brief):
            violations.append({"item": item, "method": "llm_judge"})

    total = len(forbidden)
    score = 1.0 if not violations else 0.0

    return {
        "score": score,
        "violations": violations,
        "total": total,
        "critical": len(violations) > 0,
    }


# ─── Check 4: Citation coverage ────────────────────────────────────────────────

def check_citation_coverage(brief: str, golden: dict) -> dict:
    """
    Counts what percentage of sentences containing factual claims
    have a [N] citation attached.
    A sentence is "factual" if it contains numbers, proper nouns,
    or specific claims (not headings or transitional sentences).
    """
    min_citations = golden.get("quality_thresholds", {}).get("min_citations", 3)

    # Find all citation markers
    all_citations = re.findall(r'\[\d+\]', brief)
    unique_citations = set(re.findall(r'\[(\d+)\]', brief))

    # Count sentences that look factual (contain numbers or % or $)
    sentences = [s.strip() for s in re.split(r'[.!?]', brief) if len(s.strip()) > 20]
    factual_sentences = [
        s for s in sentences
        if re.search(r'[\$\%]|\d+|billion|million|percent', s, re.IGNORECASE)
    ]

    cited_sentences = [s for s in factual_sentences if re.search(r'\[\d+\]', s)]

    coverage = (
        len(cited_sentences) / len(factual_sentences)
        if factual_sentences else 0.0
    )

    min_coverage = golden.get("quality_thresholds", {}).get("min_citation_coverage", 0.30)

    return {
        "score": round(coverage, 3),
        "unique_citations_used": len(unique_citations),
        "min_citations_required": min_citations,
        "citations_met": len(unique_citations) >= min_citations,
        "factual_sentences": len(factual_sentences),
        "cited_sentences": len(cited_sentences),
        "min_coverage_threshold": min_coverage,
        "passed": coverage >= min_coverage and len(unique_citations) >= min_citations,
    }


# ─── Check 5: Sentiment calibration ───────────────────────────────────────────

def check_sentiment_range(sentiment_score: float, golden: dict) -> dict:
    direction = golden.get("sentiment_direction", "any")

    if direction == "any":
        passed = True
    elif direction == "positive":
        passed = sentiment_score > 0.0
    elif direction == "negative":
        passed = sentiment_score < 0.0
    elif direction == "neutral":
        passed = -0.3 <= sentiment_score <= 0.3
    else:
        passed = True

    return {
        "score":     1.0 if passed else 0.0,
        "sentiment_score": sentiment_score,
        "expected_direction": direction,
        "passed": passed,
    }

# ─── Check 6: Private company handling ────────────────────────────────────────

def check_private_company_handling(
    brief: str,
    accountant_output: dict,
    golden: dict,
) -> dict | None:
    """
    Only runs for private companies (is_public=False).
    Verifies:
    - No stock price is shown
    - No market cap is fabricated
    - is_public is correctly set to False
    - Brief acknowledges private status
    """
    if golden.get("is_public", True):
        return None  # skip for public companies

    issues = []

    if accountant_output.get("is_public"):
        issues.append("Accountant incorrectly marked company as public")

    if accountant_output.get("current_price") is not None:
        issues.append("Accountant fabricated a stock price for private company")

    if accountant_output.get("ticker") and golden.get("ticker") is None:
        issues.append("Accountant fabricated a ticker symbol for private company")

    # Check brief doesn't present fake stock data
    stock_patterns = [r'\$\d+\.\d+ per share', r'stock price', r'share price', r'trades at']
    for pattern in stock_patterns:
        if re.search(pattern, brief, re.IGNORECASE):
            issues.append(f"Brief contains stock price language for private company: {pattern}")

    return {
        "score": 1.0 if not issues else 0.0,
        "issues": issues,
        "passed": len(issues) == 0,
    }


# ─── Check 7: Source quality ───────────────────────────────────────────────────

def check_source_quality(sources: list[dict]) -> dict:
    """
    Checks what percentage of cited sources come from trusted domains.
    """
    if not sources:
        return {"score": 0.0, "trusted": 0, "total": 0, "untrusted_urls": []}

    trusted = []
    untrusted = []

    for s in sources:
        url = s.get("url", "")
        try:
            domain = urlparse(url).hostname or ""
            domain = domain.removeprefix("www.")
            is_trusted = any(
                domain == td or domain.endswith(f".{td}")
                for td in TRUSTED_DOMAINS
            )
            if is_trusted:
                trusted.append(url)
            else:
                untrusted.append(url)
        except Exception:
            untrusted.append(url)

    score = len(trusted) / len(sources) if sources else 0.0

    return {
        "score": round(score, 3),
        "trusted": len(trusted),
        "untrusted": len(untrusted),
        "total": len(sources),
        "untrusted_urls": untrusted[:5],  # show first 5 for debugging
    }


# ─── Check 8: Word count and structure ────────────────────────────────────────

def check_structure(brief: str, golden: dict) -> dict:
    """
    Checks that the brief meets minimum length requirements
    and contains expected structural sections.
    """
    thresholds = golden.get("quality_thresholds", {})
    min_words = thresholds.get("min_word_count", 300)

    word_count = len(brief.split())

    expected_sections = [
        "Executive Summary",
        "Recent Developments",
        "Financial Overview",
        "Risk Assessment",
        "Signal Summary",
    ]

    found_sections = [s for s in expected_sections if s in brief]
    missing_sections = [s for s in expected_sections if s not in brief]

    return {
        "word_count": word_count,
        "min_word_count": min_words,
        "word_count_passed": word_count >= min_words,
        "sections_found": found_sections,
        "sections_missing": missing_sections,
        "section_score": round(len(found_sections) / len(expected_sections), 3),
        "passed": word_count >= min_words and len(missing_sections) <= 1,
    }


# ─── Aggregate scorer ──────────────────────────────────────────────────────────

def compute_overall_score(results: dict) -> dict:
    """
    Weights each check and computes a final 0-100 score.

    Weights reflect importance to portfolio quality:
    - Forbidden content: highest weight — a hallucinated fact is critical failure
    - Patterns: high weight — core coverage test
    - Citations: high weight — key differentiator of FirmSignal
    - Stable facts: medium — important but string matching can miss valid phrasings
    - Structure: medium — format requirement
    - Sentiment: lower — directional signal only
    - Source quality: lower — filter may not catch everything
    """
    weights = {
        "forbidden_content": 0.25,
        "patterns":          0.20,
        "citations":         0.20,
        "stable_facts":      0.15,
        "structure":         0.10,
        "sentiment":         0.05,
        "source_quality":    0.05,
    }

    scores = {
        "forbidden_content": results.get("forbidden_content", {}).get("score", 1.0),
        "patterns":          results.get("patterns", {}).get("score", 1.0),
        "citations":         1.0 if results.get("citations", {}).get("passed") else 0.5,
        "stable_facts":      results.get("stable_facts", {}).get("score", 1.0),
        "structure":         results.get("structure", {}).get("section_score", 1.0),
        "sentiment":         results.get("sentiment", {}).get("score", 1.0),
        "source_quality":    results.get("source_quality", {}).get("score", 1.0),
    }

    weighted = sum(scores[k] * weights[k] for k in weights)
    overall = round(weighted * 100, 1)

    # Any critical failure overrides the score
    if results.get("forbidden_content", {}).get("critical"):
        overall = min(overall, 30.0)

    grade = (
        "A" if overall >= 90 else
        "B" if overall >= 80 else
        "C" if overall >= 70 else
        "D" if overall >= 60 else
        "F"
    )

    return {
        "overall_score": overall,
        "grade": grade,
        "component_scores": scores,
        "weights": weights,
    }