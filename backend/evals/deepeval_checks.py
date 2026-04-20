"""
DeepEval integration for FirmSignal.

Runs two LLM-as-judge metrics on the Synthesizer output:
- Faithfulness: did the brief hallucinate facts not in agent outputs?
- Answer Relevancy: does the brief answer the implied question?

These complement the custom checks in eval_utils.py.
Cost: ~$0.05 per company (uses gpt-4o-mini as judge by default).
"""

import os
from deepeval import evaluate
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase


def build_retrieval_context(
    scout_output: dict,
    accountant_output: dict,
    skeptic_output: dict,
) -> list[str]:
    """
    Builds the retrieval context that the Synthesizer had access to.
    DeepEval uses this to check if the brief hallucinated anything
    not present in the source data.
    """
    context = []

    # Scout context
    if scout_output:
        for item in scout_output.get("news_items", []):
            context.append(
                f"News: {item['headline']} — {item['summary']}"
            )
        for change in scout_output.get("leadership_changes", []):
            context.append(
                f"Leadership: {change['name']} ({change['role']}) {change['change_type']}"
            )
        for event in scout_output.get("key_events", []):
            context.append(f"Event: {event}")

    # Accountant context
    if accountant_output and accountant_output.get("is_public"):
        context.append(
            f"Financial data: ticker {accountant_output.get('ticker')}, "
            f"market cap {accountant_output.get('market_cap_formatted')}, "
            f"revenue {accountant_output.get('revenue_formatted')}, "
            f"P/E {accountant_output.get('pe_ratio')}, "
            f"gross margin {accountant_output.get('gross_margin_pct')}%, "
            f"1Y return {accountant_output.get('price_change_1y')}%, "
            f"5Y return {accountant_output.get('price_change_5y')}%"
        )
        context.append(accountant_output.get("financial_summary", ""))

    # Skeptic context
    if skeptic_output:
        context.append(
            f"Sentiment: {skeptic_output.get('sentiment_score')} "
            f"({skeptic_output.get('sentiment_label')})"
        )
        for flag in skeptic_output.get("risk_flags", []):
            context.append(
                f"Risk [{flag['severity'].upper()}] {flag['category']}: "
                f"{flag['description']}"
            )
        for signal in skeptic_output.get("positive_signals", []):
            context.append(f"Positive: {signal}")
        context.append(f"Skeptic summary: {skeptic_output.get('summary', '')}")

    return [c for c in context if c.strip()]


def run_deepeval_checks(
    company: str,
    brief: str,
    scout_output: dict,
    accountant_output: dict,
    skeptic_output: dict,
    threshold: float = 0.7,
) -> dict:
    """
    Runs DeepEval Faithfulness and Answer Relevancy checks.

    Returns scores and pass/fail for each metric.
    Degrades gracefully if DeepEval or OpenAI key is unavailable.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return {
            "skipped": True,
            "reason": "OPENAI_API_KEY not set — DeepEval requires OpenAI as judge",
            "faithfulness": None,
            "answer_relevancy": None,
        }

    try:
        context = build_retrieval_context(
            scout_output, accountant_output, skeptic_output
        )

        if not context:
            return {
                "skipped": True,
                "reason": "No retrieval context available",
                "faithfulness": None,
                "answer_relevancy": None,
            }

        # The implicit question every FirmSignal brief should answer
        input_question = (
            f"What should an investor or business professional know about "
            f"{company} right now — including recent developments, "
            f"financial performance, key risks, and overall outlook?"
        )

        test_case = LLMTestCase(
            input=input_question,
            actual_output=brief,
            retrieval_context=context,
        )

        faithfulness_metric = FaithfulnessMetric(
            threshold=threshold,
            verbose_mode=False,
        )

        relevancy_metric = AnswerRelevancyMetric(
            threshold=threshold,
            verbose_mode=False,
        )

        # Run both metrics
        faithfulness_metric.measure(test_case)
        relevancy_metric.measure(test_case)

        return {
            "skipped": False,
            "faithfulness": {
                "score":   round(faithfulness_metric.score, 3),
                "passed":  faithfulness_metric.is_successful(),
                "reason":  faithfulness_metric.reason,
                "threshold": threshold,
            },
            "answer_relevancy": {
                "score":   round(relevancy_metric.score, 3),
                "passed":  relevancy_metric.is_successful(),
                "reason":  relevancy_metric.reason,
                "threshold": threshold,
            },
        }

    except Exception as e:
        return {
            "skipped": True,
            "reason": f"DeepEval error: {type(e).__name__}: {e}",
            "faithfulness": None,
            "answer_relevancy": None,
        }