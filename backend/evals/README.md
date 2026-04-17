# FirmSignal Eval Suite

Automated quality evaluation across 10 gold standard companies.

## Run all evals
```bash
uv run python -m evals.run_evals
```

## Run single company
```bash
uv run python -m evals.run_evals --company nvidia
```

## Fast mode (skip LLM pattern checks, saves ~$0.50)
```bash
uv run python -m evals.run_evals --fast
```

## What gets measured

| Check | Method | Expires? |
|---|---|---|
| Stable facts | String match | Rarely |
| Expected patterns | Claude Haiku judge | Never |
| Forbidden content | String + LLM | Never |
| Citation coverage | Regex | Never |
| Sentiment calibration | Range check | Occasionally |
| Structure | Section detection | Never |
| Source quality | Domain allowlist | Never |
| Private company handling | Schema check | Never |

## Refreshing golden files

Golden files should be re-verified every 90 days.
Check `last_verified` field in each file under `golden/`.
Only `stable_facts` and `forbidden_content` need manual review.
`expected_patterns` and `quality_thresholds` rarely change.

## Cost per full run

- Fast mode: ~$0.10 (no LLM pattern checks)
- Full mode: ~$0.60 (Claude Haiku for pattern checks)
- Pipeline cost: ~$0.90 (10 × $0.09 per run)
- Total full run: ~$1.50