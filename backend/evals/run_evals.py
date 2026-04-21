"""
FirmSignal Eval Suite

Runs the full pipeline on 10 gold standard companies and scores
the output across 8 quality dimensions.

Usage:
  uv run python -m evals.run_evals                    # all 10 companies
  uv run python -m evals.run_evals --company nvidia   # single company
  uv run python -m evals.run_evals --fast             # skip LLM pattern checks

Results saved to: evals/results/latest.json
"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Add backend to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.eval_utils import (
    check_citation_coverage,
    check_forbidden_content,
    check_patterns,
    check_private_company_handling,
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


COMPANIES = [
    "nvidia",
    "boeing",
    "apple",
    "microsoft",
    "stripe",
    "openai",
    "tesla",
    "jpmorgan",
    "airbnb",
    "anthropic",
]

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


# ─── HITL auto-approve node ────────────────────────────────────────────────────

def auto_approve_hitl(run_id: str, graph) -> None:
    """
    Automatically approves the HITL checkpoint during eval runs.
    Resumes the graph with approved=True and no analyst edits.
    """
    config = {"configurable": {"thread_id": run_id}}
    graph.invoke(
        Command(resume={"approved": True, "edits": None}),
        config=config,
    )


# ─── Single company eval ───────────────────────────────────────────────────────

def run_single_eval(
    company_slug: str,
    fast: bool = False,
) -> dict:
    """
    Runs the full FirmSignal pipeline on one company and scores
    all output dimensions against the golden file.

    fast=True skips LLM pattern checks (saves ~$0.05 per company)
    """
    print(f"\n{'─' * 55}")
    print(f"  Evaluating: {company_slug.upper()}")
    print(f"{'─' * 55}")

    golden = load_golden(company_slug)
    graph = create_graph()

    run_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": run_id}}

    initial_state: FirmState = {
        "company_name":      golden["company"],
        "ticker_hint":       None,
        "is_private_hint":   False,
        "input_correction":  None,
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

    start_time = time.time()

    # Wrap both graph invocations in a single LangSmith trace (no-op if unavailable)
    try:
        from langsmith import traceable as _traceable
        _ls_wrap = _traceable(
            name=f"FirmSignal — {golden['company']}",
            tags=["eval", company_slug, golden["company"].lower()],
            metadata={
                "company":      golden["company"],
                "company_slug": company_slug,
                "eval_mode":    True,
                "run_id":       run_id,
            },
        )
    except Exception:
        _ls_wrap = lambda f: f

    def _run_pipeline():
        graph.invoke(initial_state, config=config)
        state_check = graph.get_state(config)
        if state_check.values.get("error"):
            raise RuntimeError(state_check.values["error"])
        print(f"  [2/3] Auto-approving HITL...")
        return graph.invoke(
            Command(resume={"approved": True, "edits": None}),
            config=config,
        )

    run_full_pipeline = _ls_wrap(_run_pipeline)

    # Phase 1 & 2: Run pipeline then auto-approve HITL under one trace
    print(f"  [1/3] Running pipeline...")
    try:
        final = run_full_pipeline()
    except RuntimeError as e:
        return {
            "company": company_slug,
            "status": "agent_error",
            "error": str(e),
            "overall_score": 0,
            "grade": "F",
        }
    except Exception as e:
        return {
            "company": company_slug,
            "status": "pipeline_error",
            "error": str(e),
            "overall_score": 0,
            "grade": "F",
        }

    elapsed = round(time.time() - start_time, 1)
    print(f"  [3/3] Scoring output... (pipeline took {elapsed}s)")

    # Extract outputs
    brief            = final.get("final_brief", "")
    sources          = final.get("sources", [])
    accountant       = final.get("accountant_output") or {}
    skeptic          = final.get("skeptic_output") or {}
    sentiment_score  = skeptic.get("sentiment_score", 0.0)

    if not brief:
        return {
            "company": company_slug,
            "status": "no_brief",
            "error": "Synthesizer produced no output",
            "overall_score": 0,
            "grade": "F",
        }

    # Run all checks
    results = {}

    results["stable_facts"] = check_stable_facts(brief, golden)
    print(f"     stable_facts:     {results['stable_facts']['score']:.0%} "
          f"({len(results['stable_facts']['passed'])}/{results['stable_facts']['total']} passed)")

    if not fast:
        results["patterns"] = check_patterns(brief, golden)
        print(f"     patterns:         {results['patterns']['score']:.0%} "
              f"({len(results['patterns']['passed'])}/{results['patterns']['total']} passed)")
    else:
        results["patterns"] = {"score": 1.0, "skipped": True}
        print(f"     patterns:         skipped (--fast mode)")

    results["forbidden_content"] = check_forbidden_content(brief, golden)
    violations = results["forbidden_content"]["violations"]
    if violations:
        print(f"     forbidden_content: FAIL — {len(violations)} violation(s):")
        for v in violations:
            print(f"       ✗ {v['item']}")
    else:
        print(f"     forbidden_content: PASS — no violations")

    results["citations"] = check_citation_coverage(brief, golden)
    print(f"     citations:        {results['citations']['score']:.0%} coverage "
          f"({results['citations']['unique_citations_used']} unique)")

    results["sentiment"] = check_sentiment_range(sentiment_score, golden)
    expected = golden.get("sentiment_range", [-1, 1])
    status = "PASS" if results["sentiment"]["passed"] else "FAIL"
    print(f"     sentiment:        {status} — score {sentiment_score:+.2f} "
          f"(expected {expected[0]} to {expected[1]})")

    results["structure"] = check_structure(brief, golden)
    print(f"     structure:        {results['structure']['section_score']:.0%} "
          f"({len(results['structure']['sections_found'])}/5 sections, "
          f"{results['structure']['word_count']} words)")

    results["source_quality"] = check_source_quality(sources)
    print(f"     source_quality:   {results['source_quality']['score']:.0%} trusted "
          f"({results['source_quality']['trusted']}/{results['source_quality']['total']} sources)")

    # Private company check (only runs for private companies)
    private_check = check_private_company_handling(brief, accountant, golden)
    if private_check is not None:
        results["private_handling"] = private_check
        status = "PASS" if private_check["passed"] else "FAIL"
        print(f"     private_handling: {status}")
        if not private_check["passed"]:
            for issue in private_check["issues"]:
                print(f"       ✗ {issue}")

    # DeepEval checks (requires OPENAI_API_KEY)
    from evals.deepeval_checks import run_deepeval_checks

    print(f"     deepeval:         running faithfulness + relevancy...")
    deepeval_results = run_deepeval_checks(
        company=golden["company"],
        brief=brief,
        scout_output=final.get("scout_output") or {},
        accountant_output=accountant,
        skeptic_output=skeptic,
    )

    results["deepeval"] = deepeval_results

    if deepeval_results.get("skipped"):
        print(f"     deepeval:         skipped — {deepeval_results['reason']}")
    else:
        f_score = deepeval_results["faithfulness"]["score"]
        r_score = deepeval_results["answer_relevancy"]["score"]
        f_pass  = "PASS" if deepeval_results["faithfulness"]["passed"] else "FAIL"
        r_pass  = "PASS" if deepeval_results["answer_relevancy"]["passed"] else "FAIL"
        print(f"     faithfulness:     {f_pass} — {f_score:.2f}")
        print(f"     answer_relevancy: {r_pass} — {r_score:.2f}")

    scoring = compute_overall_score(results)

    deepeval_scores = None
    if not deepeval_results.get("skipped"):
        deepeval_scores = {
            "faithfulness":    deepeval_results["faithfulness"]["score"],
            "answer_relevancy": deepeval_results["answer_relevancy"]["score"],
        }

    return {
        "company":          company_slug,
        "status":           "success",
        "overall_score":    scoring["overall_score"],
        "grade":            scoring["grade"],
        "component_scores": scoring["component_scores"],
        "deepeval_included": scoring["deepeval_included"],
        "deepeval_scores":  deepeval_scores,
        "pipeline_time_s":  elapsed,
        "word_count":       results.get("structure", {}).get("word_count", 0),
        "citations_used":   results.get("citations", {}).get("unique_citations_used", 0),
    }

def compute_overall_score(results: dict) -> dict:
    # Check if DeepEval ran successfully
    deepeval = results.get("deepeval", {})
    deepeval_ran = not deepeval.get("skipped", True)

    if deepeval_ran:
        # With DeepEval: redistribute weights to include it
        weights = {
            "forbidden_content": 0.20,
            "patterns":          0.15,
            "citations":         0.15,
            "stable_facts":      0.10,
            "structure":         0.08,
            "sentiment":         0.05,
            "source_quality":    0.05,
            "faithfulness":      0.12,
            "answer_relevancy":  0.10,
        }
        scores = {
            "forbidden_content": results.get("forbidden_content", {}).get("score", 1.0),
            "patterns":          results.get("patterns", {}).get("score", 1.0),
            "citations":         1.0 if results.get("citations", {}).get("passed") else 0.5,
            "stable_facts":      results.get("stable_facts", {}).get("score", 1.0),
            "structure":         results.get("structure", {}).get("section_score", 1.0),
            "sentiment":         results.get("sentiment", {}).get("score", 1.0),
            "source_quality":    results.get("source_quality", {}).get("score", 1.0),
            "faithfulness":      deepeval["faithfulness"]["score"] if deepeval.get("faithfulness") else 0.0,
            "answer_relevancy":  deepeval["answer_relevancy"]["score"] if deepeval.get("answer_relevancy") else 0.0,
        }
    else:
        # Without DeepEval: original weights
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
    overall  = round(weighted * 100, 1)

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
        "overall_score":    overall,
        "grade":            grade,
        "component_scores": scores,
        "weights":          weights,
        "deepeval_included": deepeval_ran,
    }


# ─── Summary reporter ──────────────────────────────────────────────────────────

def print_summary(all_results: list[dict]) -> dict:
    successful = [r for r in all_results if r["status"] == "success"]
    failed     = [r for r in all_results if r["status"] != "success"]

    # Detect if any run included DeepEval
    deepeval_ran = any(r.get("deepeval_included") for r in successful)

    print(f"\n{'═' * 70}")
    print(f"  EVAL RESULTS SUMMARY")
    print(f"{'═' * 70}")

    if deepeval_ran:
        print(f"  {'Company':<15} {'Score':>6}  {'Grade':>5}  {'Faith':>6}  {'Relev':>6}  {'Time':>6}  {'Words':>6}")
        print(f"  {'─'*15} {'─'*6}  {'─'*5}  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*6}")
    else:
        print(f"  {'Company':<15} {'Score':>6}  {'Grade':>5}  {'Time':>6}  {'Words':>6}  {'Cites':>5}")
        print(f"  {'─'*15} {'─'*6}  {'─'*5}  {'─'*6}  {'─'*6}  {'─'*5}")

    for r in all_results:
        if r["status"] == "success":
            if deepeval_ran:
                de   = r.get("deepeval_scores", {})
                f    = de.get("faithfulness")
                v    = de.get("answer_relevancy")
                f_str = f"{f:.2f}" if f is not None else "─"
                v_str = f"{v:.2f}" if v is not None else "─"
                print(
                    f"  {r['company']:<15} "
                    f"{r['overall_score']:>5.1f}  "
                    f"{r['grade']:>5}  "
                    f"{f_str:>6}  "
                    f"{v_str:>6}  "
                    f"{r['pipeline_time_s']:>5.0f}s  "
                    f"{r['word_count']:>6}"
                )
            else:
                print(
                    f"  {r['company']:<15} "
                    f"{r['overall_score']:>5.1f}  "
                    f"{r['grade']:>5}  "
                    f"{r['pipeline_time_s']:>5.0f}s  "
                    f"{r['word_count']:>6}  "
                    f"{r['citations_used']:>5}"
                )
        else:
            cols = "  {'─':>6}  {'─':>6}  {'─':>6}  {'─':>6}" if deepeval_ran else "  {'─':>6}  {'─':>6}  {'─':>5}"
            print(f"  {r['company']:<15} {'ERROR':>6}  {'F':>5}{cols}")
            print(f"    → {r.get('error', 'Unknown error')[:60]}")

    if successful:
        avg_score = sum(r["overall_score"] for r in successful) / len(successful)
        avg_time  = sum(r["pipeline_time_s"] for r in successful) / len(successful)
        avg_words = sum(r["word_count"] for r in successful) / len(successful)
        avg_cites = sum(r["citations_used"] for r in successful) / len(successful)

        if deepeval_ran:
            f_scores = [r["deepeval_scores"]["faithfulness"] for r in successful
                        if r.get("deepeval_scores", {}).get("faithfulness") is not None]
            v_scores = [r["deepeval_scores"]["answer_relevancy"] for r in successful
                        if r.get("deepeval_scores", {}).get("answer_relevancy") is not None]
            avg_f = sum(f_scores) / len(f_scores) if f_scores else None
            avg_v = sum(v_scores) / len(v_scores) if v_scores else None
            f_str = f"{avg_f:.2f}" if avg_f is not None else "─"
            v_str = f"{avg_v:.2f}" if avg_v is not None else "─"
            print(f"\n  {'AVERAGE':<15} {avg_score:>5.1f}  {'─':>5}  {f_str:>6}  {v_str:>6}  {avg_time:>5.0f}s  {avg_words:>6.0f}")
        else:
            avg_f = avg_v = None
            print(f"\n  {'AVERAGE':<15} {avg_score:>5.1f}  {'─':>5}  {avg_time:>5.0f}s  {avg_words:>6.0f}  {avg_cites:>5.1f}")
    else:
        avg_score = avg_time = avg_words = avg_cites = 0
        avg_f = avg_v = None

    total = len(all_results)
    print(f"\n  Passed: {len(successful)}/{total}  Failed: {len(failed)}/{total}")

    # Component averages
    if successful:
        components = ["stable_facts", "patterns", "citations", "forbidden_content",
                      "structure", "sentiment", "source_quality"]
        if deepeval_ran:
            components += ["faithfulness", "answer_relevancy"]

        print(f"\n  Component averages:")
        for c in components:
            scores = [
                r["component_scores"].get(c, 1.0)
                for r in successful
                if "component_scores" in r and c in r["component_scores"]
            ]
            if scores:
                avg = sum(scores) / len(scores)
                print(f"    {c:<22} {avg:.0%}")

    # README-ready block
    deepeval_rows = ""
    if deepeval_ran and avg_f is not None:
        deepeval_rows = (
            f"| Faithfulness (DeepEval) | {avg_f:.0%} |\n"
            f"| Answer Relevancy (DeepEval) | {avg_v:.0%} |\n"
        )

    readme_block = f"""
## Eval Results — {datetime.now().strftime('%B %Y')}

| Metric | Score |
|---|---|
| Overall average | {avg_score:.1f}/100 |
| Companies passing (≥70) | {sum(1 for r in successful if r['overall_score'] >= 70)}/{len(all_results)} |
{deepeval_rows}| Avg pipeline time | {avg_time:.0f}s |
| Avg words per brief | {avg_words:.0f} |
| Avg citations used | {avg_cites:.1f} |
| Private company handling | {sum(1 for r in successful if not r.get('is_public', True))}/3 graceful |
""" if successful else ""

    if readme_block:
        print(f"\n{'═' * 70}")
        print("  README-READY SUMMARY:")
        print(f"{'═' * 70}")
        print(readme_block)

    return {
        "run_at":           datetime.now().isoformat(),
        "total_companies":  len(all_results),
        "successful":       len(successful),
        "failed":           len(failed),
        "avg_score":        round(avg_score, 1) if successful else 0,
        "avg_faithfulness": round(avg_f, 3) if avg_f is not None else None,
        "avg_relevancy":    round(avg_v, 3) if avg_v is not None else None,
        "deepeval_ran":     deepeval_ran,
        "results":          all_results,
        "readme_summary":   readme_block.strip() if successful else "",
    }

# ─── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="FirmSignal Eval Suite")
    parser.add_argument(
        "--company",
        type=str,
        help="Run eval for a single company (e.g. --company nvidia)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip LLM pattern checks (faster, saves API cost)",
    )
    args = parser.parse_args()

    companies = [args.company] if args.company else COMPANIES

    print(f"\nFirmSignal Eval Suite")
    print(f"Companies: {', '.join(companies)}")
    print(f"Mode: {'fast (no LLM pattern checks)' if args.fast else 'full'}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    all_results = []
    for slug in companies:
        result = run_single_eval(slug, fast=args.fast)
        all_results.append(result)

    summary = print_summary(all_results)

    # Save results
    output_path = RESULTS_DIR / "latest.json"
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    # Also save timestamped copy
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = RESULTS_DIR / f"eval_{ts}.json"
    with open(archive_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Results saved to evals/results/latest.json")
    print(f"  Archive saved to evals/results/eval_{ts}.json")



if __name__ == "__main__":
    main()