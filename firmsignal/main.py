from dotenv import load_dotenv
load_dotenv()

import sys
import uuid

from langgraph.types import Command

from firmsignal.graph import app
from firmsignal.state import FirmState

SEVERITY_ICON  = {"high": "(!)", "medium": "(*)", "low": "(-)"}
SENTIMENT_BAR  = {
    "very_negative": "[----      ]",
    "negative":      "[--        ]",
    "neutral":       "[-----     ]",
    "positive":      "[-------   ]",
    "very_positive": "[----------]",
}


# ─── Display helpers ───────────────────────────────────────────────────────────

def _print_scout(scout: dict) -> None:
    print(f"\n{'=' * 56}")
    print(f"  SCOUT  —  {scout['company_name']}  ({scout['research_date']})")
    print(f"{'=' * 56}")
    for item in scout.get("news_items", []):
        print(f"\n  • {item['headline']}")
        print(f"    {item['date']}  |  {item['url']}")
    changes = scout.get("leadership_changes", [])
    if changes:
        print(f"\n  Leadership changes:")
        for c in changes:
            print(f"    - {c['name']} ({c['role']}): {c['change_type']}")


def _print_accountant(acc: dict) -> None:
    print(f"\n{'=' * 56}")
    ticker = acc.get("ticker", "private")
    print(f"  ACCOUNTANT  —  {acc['company_name']}  ({ticker})")
    print(f"{'=' * 56}")
    if acc.get("is_public"):
        print(f"\n  Price:        ${acc.get('current_price')}  ({acc.get('currency')})")
        print(f"  Market Cap:   {acc.get('market_cap_formatted')}")
        print(f"  Revenue TTM:  {acc.get('revenue_formatted')}")
        print(f"  P/E:          {acc.get('pe_ratio')}")
        print(f"  Gross Margin: {acc.get('gross_margin_pct')}%")
        print(f"  1Y / 5Y:      {acc.get('price_change_1y')}% / {acc.get('price_change_5y')}%")
        print(f"  History:      {len(acc.get('price_history', []))} months")
    print(f"\n  {acc.get('financial_summary', '')}")


def _print_skeptic(skep: dict) -> None:
    score = skep.get("sentiment_score", 0)
    label = skep.get("sentiment_label", "neutral")
    print(f"\n{'=' * 56}")
    print(f"  SKEPTIC  —  sentiment: {score:+.2f}  ({label})")
    print(f"  {SENTIMENT_BAR.get(label, '')}")
    print(f"{'=' * 56}")
    for flag in skep.get("risk_flags", []):
        icon = SEVERITY_ICON.get(flag["severity"], "(-)")
        print(f"\n  {icon} [{flag['severity'].upper()}] {flag['category']}")
        print(f"     {flag['description']}")
        print(f"     {flag['source_url']}")
    for sig in skep.get("positive_signals", []):
        print(f"\n  (+) {sig}")
    print(f"\n  Summary: {skep.get('summary', '')}")


def _print_hitl_prompt(payload: dict) -> None:
    """Renders the HITL review screen in the terminal."""
    score = payload.get("sentiment_score", 0)
    label = payload.get("sentiment_label", "neutral")
    flags = payload.get("risk_flags", [])

    print(f"\n{'#' * 56}")
    print(f"  HUMAN REVIEW REQUIRED")
    print(f"  Company:   {payload.get('company')}")
    print(f"  Sentiment: {score:+.2f}  ({label})")
    print(f"  Sources:   {payload.get('sources_analyzed', 0)} analysed")
    print(f"{'#' * 56}")

    print(f"\n  Risk Flags ({len(flags)}):\n")
    for i, flag in enumerate(flags, 1):
        icon = SEVERITY_ICON.get(flag["severity"], "(-)")
        print(f"  {i}. {icon} [{flag['severity'].upper()}] {flag['category']}")
        print(f"     {flag['description']}\n")

    positives = payload.get("positive_signals", [])
    if positives:
        print(f"  Positive Signals:")
        for sig in positives:
            print(f"  (+) {sig}")

    print(f"\n  Skeptic summary:")
    print(f"  {payload.get('summary', '')}")
    print(f"\n{'#' * 56}")
    print("  OPTIONS:")
    print("  - Press Enter              → approve and continue to Synthesizer")
    print("  - Type a note + Enter      → approve with your edits attached")
    print("  - Type 'abort' + Enter     → cancel this run")
    print(f"{'#' * 56}")


def _get_human_decision() -> dict:
    """Reads human input from the terminal and returns a resume payload."""
    try:
        raw = input("\n  Your decision: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Interrupted — aborting run.")
        return {"approved": False, "edits": None}

    if raw.lower() == "abort":
        print("  Run aborted.")
        return {"approved": False, "edits": None}

    edits = raw if raw else None
    print("  Approved." + (f" Edits noted: '{edits}'" if edits else ""))
    return {"approved": True, "edits": edits}


# ─── Main run loop ─────────────────────────────────────────────────────────────

def run(company: str) -> None:
    # Each run gets a unique thread_id so the checkpointer can store its state
    # independently from other runs. In Week 5 this becomes a UUID returned
    # by POST /analyze and stored in the database.
    thread_id = str(uuid.uuid4())
    config    = {"configurable": {"thread_id": thread_id}}

    initial_state: FirmState = {
        "company_name":      company,
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

    print(f"\nStarting FirmSignal run for '{company}'  (thread: {thread_id[:8]}...)")

    # ── Phase 1: Scout → Accountant → Skeptic → HITL (pauses here) ────────────
    app.invoke(initial_state, config=config)

    # Check whether the graph is paused or finished
    current_state = app.get_state(config)

    if not current_state.next:
        # Graph finished without interrupting (shouldn't happen with HITL node,
        # but handles the error path gracefully)
        print("\nRun completed without reaching HITL.")
        _print_final(current_state.values)
        return

    # ── Graph is paused at HITL ────────────────────────────────────────────────
    # Retrieve the interrupt payload from the paused task
    interrupt_payload = None
    for task in current_state.tasks:
        if task.interrupts:
            interrupt_payload = task.interrupts[0].value
            break

    # Display intermediate results then the HITL review prompt
    values = current_state.values
    if values.get("scout_output"):
        _print_scout(values["scout_output"])
    if values.get("accountant_output"):
        _print_accountant(values["accountant_output"])
    if values.get("skeptic_output"):
        _print_skeptic(values["skeptic_output"])

    _print_hitl_prompt(interrupt_payload or {})

    # ── Phase 2: get human decision, resume graph ──────────────────────────────
    decision = _get_human_decision()

    final = app.invoke(Command(resume=decision), config=config)

    if final.get("error"):
        print(f"\nError after resume: {final['error']}")
        return

    print(f"\nRun complete. Total sources: {len(final.get('sources', []))}")
    print("(Synthesizer output will appear here next week)")


def _print_final(values: dict) -> None:
    if values.get("scout_output"):
        _print_scout(values["scout_output"])
    if values.get("accountant_output"):
        _print_accountant(values["accountant_output"])
    if values.get("skeptic_output"):
        _print_skeptic(values["skeptic_output"])


if __name__ == "__main__":
    company = sys.argv[1] if len(sys.argv) > 1 else "Nvidia"
    run(company)