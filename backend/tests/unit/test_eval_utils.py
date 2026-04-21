from evals.eval_utils import (
    check_stable_facts,
    check_forbidden_content,
    check_citation_coverage,
    check_sentiment_range,
    check_structure,
)

SAMPLE_BRIEF = """
## Executive Summary
Nvidia reported revenue of $39.3 billion with Jensen Huang as CEO. [1]

## Recent Developments
Blackwell chip demand remains strong. [2]

## Financial Overview
Market cap exceeds $3 trillion. [3]

## Risk Assessment
Export controls on China sales pose risk. [4]

## Signal Summary
**Bull case:** AI demand continues.
**Bear case:** Export restrictions tighten.
"""

SAMPLE_GOLDEN = {
    "stable_facts": [
        "Jensen Huang is the founder and CEO of Nvidia",
        "Nvidia trades on NASDAQ under ticker NVDA",
    ],
    "sentiment_direction": "positive",
    "quality_thresholds": {
        "min_word_count": 50,
        "min_citations": 2,
        "min_citation_coverage": 0.30,
    },
    "forbidden_content": [
        "Jensen Huang stepped down",
        "Nvidia is a private company",
    ],
}

def test_stable_facts_finds_ceo():
    result = check_stable_facts(SAMPLE_BRIEF, SAMPLE_GOLDEN)
    passed = [f for f in result["passed"] if "Jensen Huang" in f]
    assert len(passed) > 0

def test_forbidden_content_passes_clean_brief():
    result = check_forbidden_content(SAMPLE_BRIEF, SAMPLE_GOLDEN)
    assert result["score"] == 1.0
    assert not result["critical"]

def test_forbidden_content_catches_violation():
    bad_brief = SAMPLE_BRIEF + "\nJensen Huang stepped down as CEO."
    result = check_forbidden_content(bad_brief, SAMPLE_GOLDEN)
    assert result["score"] == 0.0
    assert result["critical"]

def test_citation_coverage_counts_correctly():
    result = check_citation_coverage(SAMPLE_BRIEF, SAMPLE_GOLDEN)
    assert result["unique_citations_used"] == 4
    assert result["citations_met"]

def test_sentiment_direction_positive():
    golden = {"sentiment_direction": "positive"}
    assert check_sentiment_range(0.5, golden)["passed"]
    assert not check_sentiment_range(-0.3, golden)["passed"]

def test_sentiment_direction_any_always_passes():
    golden = {"sentiment_direction": "any"}
    assert check_sentiment_range(-0.9, golden)["passed"]
    assert check_sentiment_range(0.9, golden)["passed"]

def test_structure_finds_all_sections():
    result = check_structure(SAMPLE_BRIEF, SAMPLE_GOLDEN)
    assert result["section_score"] == 1.0
    assert len(result["sections_missing"]) == 0

def test_structure_fails_below_word_count():
    golden = {"quality_thresholds": {"min_word_count": 10000, "min_citations": 2}}
    result = check_structure(SAMPLE_BRIEF, golden)
    assert not result["word_count_passed"]