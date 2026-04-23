"""
Experiment: Skeptic evidence threshold vs risk flag quality

Hypothesis: A stricter evidence threshold reduces hallucinations
but misses genuine risks. An aggressive threshold surfaces more
risks but introduces noise and hallucinated claims.

Tests three variants across a subset of companies and compares
quality scores using the existing eval suite.

Usage:
  cd backend
  uv run python -m evals.experiments.skeptic_strictness

Results saved to: evals/results/experiment_skeptic_strictness.json
"""

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from evals.eval_utils import (
    check_citation_coverage,
    check_forbidden_content,
    check_patterns,
    check_sentiment_range,
    check_source_quality,
    check_stable_facts,
    check_structure,
    compute_overall_score,
    load_golden,
)
from firmsignal.graph import create_graph
from firmsignal.state import FirmState
from langgraph.types import Command

RESULTS_DIR = Path(__file__).parent.parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Three companies that cover different risk profiles:
# Boeing  — known high-risk, tests if aggressive mode over-flags
# Nvidia  — known low-risk, tests if strict mode under-flags
# Tesla   — mixed sentiment, tests calibration
TEST_COMPANIES = ["boeing", "nvidia", "tesla"]

VARIANTS = {
    "baseline": {
        "description": "Current setting — one credible source required",
        "prompt_suffix": "",
    },
    "strict": {
        "description": "Two independent sources required per risk flag",
        "prompt_suffix": (
            "\n\nSTRICTNESS OVERRIDE — MANDATORY:\n"
            "A risk flag is only valid if supported by TWO independent "
            "credible sources. Single-source claims must NOT be included "
            "as risk flags. If you only have one source for a risk, "
            "omit the flag entirely."
        ),
    },
    "aggressive": {
        "description": "Any source acceptable, surface all potential risks",
        "prompt_suffix": (
            "\n\nAGGRESSIVENESS OVERRIDE — MANDATORY:\n"
            "Surface any potential risk even if supported by a single "
            "source including blogs, forums, or unverified reports. "
            "Quantity of flags matters — flag everything that could "
            "possibly be a risk. Do not filter for credibility."
        ),
    },
}


def run_pipeline_with_variant(
    company_name: str,
    variant_key: str,
    prompt_suffix: str,
) -> dict:
    """
    Runs the full FirmSignal pipeline with a modified Skeptic prompt.
    Returns the final state dict.
    """
    # Inject the prompt variant via environment variable
    os.environ["SKEPTIC_PROMPT_SUFFIX"] = prompt_suffix

    graph   = create_graph()
    run_id  = str(uuid.uuid4())
    config  = {"configurable": {"thread_id": run_id}}

    initial_state: FirmState = {
        "company_name":     company_name,
        "ticker_hint":      None,
        "is_private_hint":  False,
        "input_correction": None,
        "scout_output":      None,
        "accountant_output": None,
        "skeptic_output":    None,
        "hitl_approved":     False,
        "hitl_edits":        None,
        "final_brief":       None,
        "sources":           [],
        "messages":          [],
        "error":             None,
    }

    # Phase 1
    graph.invoke(initial_state, config=config)

    state = graph.get_state(config)
    if state.values.get("error"):
        return {"error": state.values["error"]}

    # Phase 2 — auto approve
    final = graph.invoke(
        Command(resume={"approved": True, "edits": None}),
        config=config,
    )

    # Clean up env var
    os.environ.pop("SKEPTIC_PROMPT_SUFFIX", None)

    return final


def score_result(
    company_slug: str,
    final: dict,
    golden: dict,
) -> dict:
    """
    Runs all eval checks and returns a score dict.
    Same checks as run_single_eval() but standalone.
    """
    brief   = final.get("final_brief", "")
    sources = final.get("sources", [])
    skeptic = final.get("skeptic_output") or {}

    if not brief:
        return {
            "status":        "no_brief",
            "overall_score": 0,
            "grade":         "F",
            "risk_flag_count": 0,
        }

    results = {}
    results["stable_facts"]     = check_stable_facts(brief, golden)
    results["patterns"]         = check_patterns(brief, golden)
    results["forbidden_content"] = check_forbidden_content(brief, golden)
    results["citations"]        = check_citation_coverage(brief, golden)
    results["sentiment"]        = check_sentiment_range(
        skeptic.get("sentiment_score", 0.0), golden
    )
    results["structure"]        = check_structure(brief, golden)
    results["source_quality"]   = check_source_quality(sources)

    scoring = compute_overall_score(results)

    return {
        "status":          "success",
        "overall_score":   scoring["overall_score"],
        "grade":           scoring["grade"],
        "component_scores": scoring["component_scores"],
        "risk_flag_count": len(skeptic.get("risk_flags", [])),
        "sentiment_score": skeptic.get("sentiment_score", 0.0),
        "word_count":      len(brief.split()),
        "sources_count":   len(sources),
    }


def run_experiment() -> None:
    print(f"\nExperiment: Skeptic Evidence Threshold")
    print(f"Companies:  {', '.join(TEST_COMPANIES)}")
    print(f"Variants:   {', '.join(VARIANTS.keys())}")
    print(f"Started:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    all_results = {}

    for variant_key, variant_config in VARIANTS.items():
        print(f"\n{'═' * 60}")
        print(f"  Variant: {variant_key.upper()}")
        print(f"  {variant_config['description']}")
        print(f"{'═' * 60}")

        variant_results = []

        for slug in TEST_COMPANIES:
            golden       = load_golden(slug)
            company_name = golden["company"]

            print(f"\n  Running {company_name}...")

            try:
                final = run_pipeline_with_variant(
                    company_name=company_name,
                    variant_key=variant_key,
                    prompt_suffix=variant_config["prompt_suffix"],
                )

                if final.get("error"):
                    print(f"  Error: {final['error']}")
                    variant_results.append({
                        "company":       slug,
                        "status":        "error",
                        "overall_score": 0,
                        "grade":         "F",
                        "risk_flag_count": 0,
                    })
                    continue

                scores = score_result(slug, final, golden)
                scores["company"] = slug

                variant_results.append(scores)

                print(
                    f"  Score: {scores['overall_score']:.1f} "
                    f"Grade: {scores['grade']}  "
                    f"Risk flags: {scores['risk_flag_count']}  "
                    f"Hallucinations: {'PASS' if scores['component_scores'].get('forbidden_content', 0) == 1.0 else 'FAIL'}"
                )

            except Exception as e:
                print(f"  Failed: {e}")
                variant_results.append({
                    "company":       slug,
                    "status":        "exception",
                    "overall_score": 0,
                    "grade":         "F",
                    "risk_flag_count": 0,
                    "error":         str(e),
                })

        all_results[variant_key] = variant_results

    # Print comparison table
    _print_comparison(all_results)

    # Save results
    output = {
        "experiment":   "skeptic_evidence_threshold",
        "run_at":       datetime.now().isoformat(),
        "hypothesis":   (
            "Stricter evidence threshold reduces hallucinations "
            "but misses genuine risks. Aggressive threshold surfaces "
            "more risks but introduces noise."
        ),
        "variants":     {k: v["description"] for k, v in VARIANTS.items()},
        "companies":    TEST_COMPANIES,
        "results":      all_results,
        "summary":      _build_summary(all_results),
        "conclusion":   "",  # fill in manually after reviewing
    }

    path = RESULTS_DIR / "experiment_skeptic_strictness.json"
    path.write_text(json.dumps(output, indent=2))
    print(f"\n  Results saved to {path}")
    print(f"  Fill in 'conclusion' field with your finding.")

    # Log to LangSmith if available
    _log_to_langsmith(output)


def _build_summary(all_results: dict) -> dict:
    summary = {}
    for variant_key, results in all_results.items():
        successful = [r for r in results if r.get("status") == "success"]
        if not successful:
            summary[variant_key] = {}
            continue

        summary[variant_key] = {
            "avg_overall_score":    round(
                sum(r["overall_score"] for r in successful) / len(successful), 1
            ),
            "avg_risk_flags":       round(
                sum(r["risk_flag_count"] for r in successful) / len(successful), 1
            ),
            "hallucination_rate":   round(
                1.0 - sum(
                    r["component_scores"].get("forbidden_content", 1.0)
                    for r in successful
                ) / len(successful), 3
            ),
            "avg_patterns_score":   round(
                sum(
                    r["component_scores"].get("patterns", 0)
                    for r in successful
                ) / len(successful), 3
            ),
            "companies_evaluated":  len(successful),
        }

    return summary


def _print_comparison(all_results: dict) -> None:
    print(f"\n{'═' * 70}")
    print(f"  EXPERIMENT RESULTS — SKEPTIC EVIDENCE THRESHOLD")
    print(f"{'═' * 70}")

    print(f"\n  {'Variant':<12} {'Score':>7}  {'Flags':>6}  {'Halluc':>8}  {'Patterns':>9}  {'Desc'}")
    print(f"  {'─'*12} {'─'*7}  {'─'*6}  {'─'*8}  {'─'*9}  {'─'*30}")

    summary = _build_summary(all_results)

    for variant_key in VARIANTS:
        s   = summary.get(variant_key, {})
        desc = VARIANTS[variant_key]["description"][:35]
        print(
            f"  {variant_key:<12} "
            f"{s.get('avg_overall_score', 0):>6.1f}  "
            f"{s.get('avg_risk_flags', 0):>6.1f}  "
            f"{s.get('hallucination_rate', 0):>8.1%}  "
            f"{s.get('avg_patterns_score', 0):>9.1%}  "
            f"{desc}"
        )

    print(f"\n  Per-company breakdown:")
    print(f"  {'Company':<12} {'Variant':<12} {'Score':>7}  {'Flags':>6}  {'Halluc':>8}")
    print(f"  {'─'*12} {'─'*12} {'─'*7}  {'─'*6}  {'─'*8}")

    for slug in TEST_COMPANIES:
        for variant_key in VARIANTS:
            results = all_results.get(variant_key, [])
            result  = next((r for r in results if r.get("company") == slug), {})
            if not result:
                continue
            halluc = "PASS" if result.get(
                "component_scores", {}
            ).get("forbidden_content", 1.0) == 1.0 else "FAIL"
            print(
                f"  {slug:<12} "
                f"{variant_key:<12} "
                f"{result.get('overall_score', 0):>6.1f}  "
                f"{result.get('risk_flag_count', 0):>6}  "
                f"{halluc:>8}"
            )


def _log_to_langsmith(output: dict) -> None:
    try:
        from langsmith import Client
        from langsmith.evaluation import evaluate, EvaluationResult

        client      = Client()
        summary     = output["summary"]
        all_results = output["results"]

        # Build lookup: variant → company → result
        lookup = {
            variant_key: {r["company"]: r for r in results}
            for variant_key, results in all_results.items()
        }

        for variant_key in VARIANTS:
            variant_results = [
                r for r in all_results.get(variant_key, [])
                if r.get("status") == "success"
            ]
            if not variant_results:
                continue

            results_by_company = lookup[variant_key]

            def make_target(vk):
                def target(inputs):
                    slug   = inputs.get("company_slug", "")
                    result = lookup[vk].get(slug, {})
                    return {
                        "overall_score":   result.get("overall_score", 0),
                        "risk_flag_count": result.get("risk_flag_count", 0),
                        "grade":           result.get("grade", "F"),
                    }
                return target

            def make_evaluators(vk):
                def eval_score(run, _example):
                    slug   = run.inputs.get("company_slug", "")
                    result = lookup[vk].get(slug, {})
                    return EvaluationResult(
                        key="overall_score",
                        score=result.get("overall_score", 0) / 100,
                        comment=f"Grade: {result.get('grade', 'F')}",
                    )

                def eval_risk_flags(run, _example):
                    slug   = run.inputs.get("company_slug", "")
                    result = lookup[vk].get(slug, {})
                    return EvaluationResult(
                        key="risk_flag_count",
                        score=result.get("risk_flag_count", 0),
                    )

                def eval_no_hallucinations(run, _example):
                    slug   = run.inputs.get("company_slug", "")
                    result = lookup[vk].get(slug, {})
                    score  = result.get(
                        "component_scores", {}
                    ).get("forbidden_content", 1.0)
                    return EvaluationResult(
                        key="no_hallucinations",
                        score=score,
                        comment="PASS" if score == 1.0 else "FAIL",
                    )

                def eval_patterns(run, _example):
                    slug   = run.inputs.get("company_slug", "")
                    result = lookup[vk].get(slug, {})
                    score  = result.get(
                        "component_scores", {}
                    ).get("patterns", 0)
                    return EvaluationResult(key="patterns", score=score)

                return [eval_score, eval_risk_flags,
                        eval_no_hallucinations, eval_patterns]

            # Only pass examples for companies we evaluated
            all_examples = list(client.list_examples(
                dataset_name="firmsignal-golden-10"
            ))
            filtered = [
                ex for ex in all_examples
                if ex.inputs.get("company_slug") in {
                    r["company"] for r in variant_results
                }
            ]

            experiment_prefix = (
                f"skeptic-{variant_key}-"
                f"{datetime.now().strftime('%Y%m%d')}"
            )

            evaluate(
                make_target(variant_key),
                data=filtered,
                evaluators=make_evaluators(variant_key),
                experiment_prefix=experiment_prefix,
                client=client,
                metadata={
                    "experiment":  "skeptic_evidence_threshold",
                    "variant":     variant_key,
                    "description": VARIANTS[variant_key]["description"],
                    "avg_score":   summary.get(
                        variant_key, {}
                    ).get("avg_overall_score", 0),
                },
            )

            print(
                f"  [LangSmith] Logged variant '{variant_key}' "
                f"as experiment '{experiment_prefix}'"
            )

    except Exception as e:
        print(f"  [LangSmith] Experiment logging failed (non-fatal): {e}")


if __name__ == "__main__":
    run_experiment()