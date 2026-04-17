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

    # Phase 1: Run pipeline until HITL pause
    print(f"  [1/3] Running pipeline...")
    try:
        graph.invoke(initial_state, config=config)
    except Exception as e:
        return {
            "company": company_slug,
            "status": "pipeline_error",
            "error": str(e),
            "overall_score": 0,
            "grade": "F",
        }

    # Check for errors in state
    state = graph.get_state(config)
    if state.values.get("error"):
        return {
            "company": company_slug,
            "status": "agent_error",
            "error": state.values["error"],
            "overall_score": 0,
            "grade": "F",
        }

    # Phase 2: Auto-approve HITL
    print(f"  [2/3] Auto-approving HITL...")
    try:
        final = graph.invoke(
            Command(resume={"approved": True, "edits": None}),
            config=config,
        )
    except Exception as e:
        return {
            "company": company_slug,
            "status": "synthesis_error",
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

    # Compute overall score
    scoring = compute_overall_score(results)

    print(f"\n  ── Score: {scoring['overall_score']}/100  Grade: {scoring['grade']} ──")

    return {
        "company":         company_slug,
        "status":          "success",
        "overall_score":   scoring["overall_score"],
        "grade":           scoring["grade"],
        "component_scores": scoring["component_scores"],
        "checks":          results,
        "pipeline_time_s": elapsed,
        "word_count":      results["structure"]["word_count"],
        "citations_used":  results["citations"]["unique_citations_used"],
        "sentiment_score": sentiment_score,
        "sources_count":   len(sources),
        "is_public":       golden.get("is_public", True),
    }


# ─── Summary reporter ──────────────────────────────────────────────────────────

def print_summary(all_results: list[dict]) -> dict:
    successful = [r for r in all_results if r["status"] == "success"]
    failed     = [r for r in all_results if r["status"] != "success"]

    print(f"\n{'═' * 55}")
    print(f"  EVAL RESULTS SUMMARY")
    print(f"{'═' * 55}")
    print(f"  {'Company':<15} {'Score':>6}  {'Grade':>5}  {'Time':>6}  {'Words':>6}  {'Cites':>5}")
    print(f"  {'─'*15} {'─'*6}  {'─'*5}  {'─'*6}  {'─'*6}  {'─'*5}")

    for r in all_results:
        if r["status"] == "success":
            print(
                f"  {r['company']:<15} "
                f"{r['overall_score']:>5.1f}  "
                f"{r['grade']:>5}  "
                f"{r['pipeline_time_s']:>5.0f}s  "
                f"{r['word_count']:>6}  "
                f"{r['citations_used']:>5}"
            )
        else:
            print(f"  {r['company']:<15} {'ERROR':>6}  {'F':>5}  {'─':>6}  {'─':>6}  {'─':>5}")
            print(f"    → {r.get('error', 'Unknown error')[:60]}")

    if successful:
        avg_score = sum(r["overall_score"] for r in successful) / len(successful)
        avg_time  = sum(r["pipeline_time_s"] for r in successful) / len(successful)
        avg_words = sum(r["word_count"] for r in successful) / len(successful)
        avg_cites = sum(r["citations_used"] for r in successful) / len(successful)

        print(f"\n  {'AVERAGE':<15} {avg_score:>5.1f}  {'─':>5}  {avg_time:>5.0f}s  {avg_words:>6.0f}  {avg_cites:>5.1f}")

    print(f"\n  Passed: {len(successful)}/10  Failed: {len(failed)}/10")

    # Component averages (for README)
    if successful:
        components = ["stable_facts", "patterns", "citations", "forbidden_content",
                      "structure", "sentiment", "source_quality"]
        print(f"\n  Component averages:")
        for c in components:
            scores = [
                r["component_scores"].get(c, 1.0)
                for r in successful
                if "component_scores" in r
            ]
            if scores:
                avg = sum(scores) / len(scores)
                print(f"    {c:<22} {avg:.0%}")

    # README-ready summary
    readme_block = f"""
## Eval Results — {datetime.now().strftime('%B %Y')}

| Metric | Score |
|---|---|
| Overall average | {avg_score:.1f}/100 |
| Companies passing (≥70) | {sum(1 for r in successful if r['overall_score'] >= 70)}/10 |
| Avg pipeline time | {avg_time:.0f}s |
| Avg words per brief | {avg_words:.0f} |
| Avg citations used | {avg_cites:.1f} |
| Private company handling | {sum(1 for r in successful if not r.get('is_public', True))}/3 graceful |
""" if successful else ""

    return {
        "run_at":          datetime.now().isoformat(),
        "total_companies": len(all_results),
        "successful":      len(successful),
        "failed":          len(failed),
        "avg_score":       round(avg_score, 1) if successful else 0,
        "results":         all_results,
        "readme_summary":  readme_block.strip() if successful else "",
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

    if summary.get("readme_summary"):
        print(f"\n{'═' * 55}")
        print("  README-READY SUMMARY (copy into README.md):")
        print(f"{'═' * 55}")
        print(summary["readme_summary"])


if __name__ == "__main__":
    main()