"""
Creates a LangSmith dataset from the 10 golden company files
and logs eval results against it for score tracking over time.

Run once to create the dataset:
  cd backend
  uv run python -m evals.langsmith_dataset

After running evals, scores appear in LangSmith under:
  Datasets → firmsignal-golden-10
"""

import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from langsmith import Client


DATASET_NAME = "firmsignal-golden-10"
GOLDEN_DIR   = Path(__file__).parent / "golden"

COMPANIES = [
    "nvidia", "boeing", "apple", "microsoft", "stripe",
    "openai", "tesla", "jpmorgan", "airbnb", "anthropic",
]


def create_or_get_dataset(client: Client) -> str:
    """
    Creates the dataset if it doesn't exist.
    Returns the dataset ID either way.
    """
    existing = [d for d in client.list_datasets() if d.name == DATASET_NAME]
    if existing:
        dataset_id = str(existing[0].id)
        print(f"Dataset already exists: {DATASET_NAME} (id: {dataset_id[:8]}...)")
        return dataset_id

    dataset = client.create_dataset(
        dataset_name=DATASET_NAME,
        description=(
            "10 gold standard companies for FirmSignal evaluation. "
            "Each example is a company name input with expected output "
            "criteria — stable facts, patterns, forbidden content, "
            "quality thresholds, and sentiment range."
        ),
    )
    print(f"Created dataset: {DATASET_NAME} (id: {str(dataset.id)[:8]}...)")
    return str(dataset.id)


def upload_examples(client: Client, dataset_id: str) -> None:
    """
    Uploads one example per company.
    Skips companies that already have an example in the dataset.
    """
    existing_examples = list(client.list_examples(dataset_id=dataset_id))
    existing_companies = {
        ex.inputs.get("company_slug")
        for ex in existing_examples
    }

    added = 0
    for slug in COMPANIES:
        if slug in existing_companies:
            print(f"  Skipping {slug} — already in dataset")
            continue

        path = GOLDEN_DIR / f"{slug}.json"
        if not path.exists():
            print(f"  Skipping {slug} — golden file not found at {path}")
            continue

        golden = json.loads(path.read_text())

        client.create_example(
            dataset_id=dataset_id,
            inputs={
                "company":      golden["company"],
                "company_slug": slug,
                "is_public":    golden.get("is_public", True),
            },
            outputs={
                "stable_facts":       golden.get("stable_facts", []),
                "expected_patterns":  golden.get("expected_patterns", []),
                "forbidden_content":  golden.get("forbidden_content", []),
                "sentiment_direction": golden.get("sentiment_direction", "any"),
                "quality_thresholds": golden.get("quality_thresholds", {}),
                "ceo":                golden.get("ceo", ""),
                "ticker":             golden.get("ticker"),
                "notes":              golden.get("notes", ""),
            },
        )
        print(f"  Added: {golden['company']}")
        added += 1

    if added == 0:
        print("All companies already in dataset — nothing to add.")
    else:
        print(f"\n{added} examples added.")


def log_experiment_to_langsmith(
    client: Client,
    dataset_name: str,
    all_results: list,
    experiment_prefix: str,
) -> object:
    """
    Logs all eval results as a LangSmith Experiment using evaluate().
    Results appear in the Experiments tab of the dataset.
    """
    try:
        from langsmith.evaluation import evaluate, EvaluationResult

        results_lookup = {
            r["company"]: r
            for r in all_results
            if r.get("status") == "success"
        }

        # Only pass examples for companies we actually evaluated.
        # Without this filter, unrun companies score 0 and pollute averages
        # (e.g. running --company nvidia over a 10-example dataset gives 1/10 = 0.10).
        all_examples = list(client.list_examples(dataset_name=dataset_name))
        filtered_examples = [
            ex for ex in all_examples
            if ex.inputs.get("company_slug") in results_lookup
        ]

        def target(inputs: dict) -> dict:
            slug = inputs.get("company_slug", "")
            result = results_lookup.get(slug, {})
            if not result:
                return {"overall_score": 0, "grade": "F"}
            return {
                "overall_score":    result.get("overall_score", 0),
                "grade":            result.get("grade", "F"),
                "word_count":       result.get("word_count", 0),
                "citations_used":   result.get("citations_used", 0),
                "pipeline_time_s":  result.get("pipeline_time_s", 0),
            }

        def eval_overall_score(run, _example):
            score = run.outputs.get("overall_score", 0) / 100
            comment = f"Grade: {run.outputs.get('grade', 'F')}"
            return EvaluationResult(key="overall_score", score=score, comment=comment)

        def _component(run, key):
            slug = run.inputs.get("company_slug", "")
            return results_lookup.get(slug, {}).get("component_scores", {}).get(key, 0)

        def eval_stable_facts(run, _example):
            return EvaluationResult(key="stable_facts", score=_component(run, "stable_facts"))

        def eval_patterns(run, _example):
            return EvaluationResult(key="patterns", score=_component(run, "patterns"))

        def eval_no_hallucinations(run, _example):
            score = _component(run, "forbidden_content")
            comment = "PASS" if score == 1.0 else "FAIL — see checks"
            return EvaluationResult(key="no_hallucinations", score=score, comment=comment)

        def eval_citations(run, _example):
            return EvaluationResult(key="citations", score=_component(run, "citations"))

        def eval_source_quality(run, _example):
            return EvaluationResult(key="source_quality", score=_component(run, "source_quality"))

        def eval_sentiment_calibration(run, _example):
            score = _component(run, "sentiment")
            comment = "PASS" if score == 1.0 else "FAIL"
            return EvaluationResult(key="sentiment_calibration", score=score, comment=comment)

        def eval_pipeline_time(run, _example):
            slug = run.inputs.get("company_slug", "")
            time_s = results_lookup.get(slug, {}).get("pipeline_time_s", 0)
            return EvaluationResult(key="pipeline_time_s", score=time_s,
                                    comment=f"{time_s:.1f}s pipeline execution")

        def eval_word_count(run, _example):
            slug = run.inputs.get("company_slug", "")
            count = results_lookup.get(slug, {}).get("word_count", 0)
            return EvaluationResult(key="word_count", score=count)

        def eval_citations_used(run, _example):
            slug = run.inputs.get("company_slug", "")
            count = results_lookup.get(slug, {}).get("citations_used", 0)
            return EvaluationResult(key="citations_used", score=count)

        def eval_faithfulness(run, _example):
            slug = run.inputs.get("company_slug", "")
            de = results_lookup.get(slug, {}).get("deepeval_scores") or {}
            score = de.get("faithfulness")
            if score is None:
                return EvaluationResult(
                    key="faithfulness",
                    score=None,
                    comment="DeepEval not run — OPENAI_API_KEY not set",
                )
            return EvaluationResult(key="faithfulness", score=float(score))

        def eval_relevancy(run, _example):
            slug = run.inputs.get("company_slug", "")
            de = results_lookup.get(slug, {}).get("deepeval_scores") or {}
            score = de.get("answer_relevancy")
            if score is None:
                return EvaluationResult(
                    key="answer_relevancy",
                    score=None,
                    comment="DeepEval not run — OPENAI_API_KEY not set",
                )
            return EvaluationResult(key="answer_relevancy", score=float(score))

        results = evaluate(
            target,
            data=filtered_examples,
            evaluators=[
                eval_overall_score,
                eval_stable_facts,
                eval_patterns,
                eval_no_hallucinations,
                eval_citations,
                eval_source_quality,
                eval_sentiment_calibration,
                eval_pipeline_time,
                eval_word_count,
                eval_citations_used,
                eval_faithfulness,
                eval_relevancy,
            ],
            experiment_prefix=experiment_prefix,
            client=client,
            metadata={
                "total_companies": len(all_results),
                "successful":      len(results_lookup),
                "avg_score":       sum(r.get("overall_score", 0) for r in results_lookup.values())
                                   / max(len(results_lookup), 1),
            },
        )

        # Patch latency: update each run's end_time so LangSmith shows real
        # pipeline duration instead of the ~0ms dict-lookup time.
        from datetime import timedelta
        for result_row in results:
            run = result_row.get("run")
            if not run or not getattr(run, "start_time", None):
                continue
            slug = (run.inputs or {}).get("company_slug", "")
            time_s = results_lookup.get(slug, {}).get("pipeline_time_s", 0)
            if time_s:
                try:
                    client.update_run(
                        run_id=str(run.id),
                        end_time=run.start_time + timedelta(seconds=time_s),
                    )
                except Exception:
                    pass

        return results

    except Exception as e:
        print(f"  [LangSmith] log_experiment_to_langsmith failed (non-fatal): {e}")
        return None

def main():
    client = Client()

    print(f"Connecting to LangSmith...")
    print(f"Project: firmsignal-evals\n")

    dataset_id = create_or_get_dataset(client)

    print(f"\nUploading examples...")
    upload_examples(client, dataset_id)

    print(f"\nDone. View at:")
    print(f"  https://smith.langchain.com → Datasets → {DATASET_NAME}")


if __name__ == "__main__":
    main()