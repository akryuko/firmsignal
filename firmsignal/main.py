from dotenv import load_dotenv
load_dotenv()

import sys
import uuid

from langgraph.types import Command
from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule

from firmsignal.graph import app
from firmsignal.state import FirmState

console = Console()

SEVERITY_ICON = {"high": "(!)", "medium": "(*)", "low": "(-)"}
SENTIMENT_BAR = {
    "very_negative": "■■■■■□□□□□",
    "negative":      "■■■□□□□□□□",
    "neutral":       "□□□□■□□□□□",
    "positive":      "□□□□□□■■□□",
    "very_positive": "□□□□□□□■■■",
}


def _print_scout(scout: dict) -> None:
    console.print(Rule("Scout"))
    for item in scout.get("news_items", []):
        console.print(f"  • [bold]{item['headline']}[/bold]")
        console.print(f"    {item['date']}  {item['url']}", style="dim")
    changes = scout.get("leadership_changes", [])
    if changes:
        console.print("\n  [bold]Leadership changes:[/bold]")
        for c in changes:
            console.print(f"    – {c['name']} ({c['role']}): {c['change_type']}")


def _print_accountant(acc: dict) -> None:
    console.print(Rule("Accountant"))
    if acc.get("is_public"):
        console.print(
            f"  [bold]{acc.get('ticker')}[/bold]  "
            f"${acc.get('current_price')} {acc.get('currency')}  |  "
            f"Cap: {acc.get('market_cap_formatted')}  |  "
            f"P/E: {acc.get('pe_ratio')}  |  "
            f"Rev: {acc.get('revenue_formatted')}"
        )
        console.print(
            f"  1Y: [green]{acc.get('price_change_1y')}%[/green]  "
            f"5Y: [green]{acc.get('price_change_5y')}%[/green]  "
            f"History: {len(acc.get('price_history', []))} months",
        )
    console.print(f"\n  {acc.get('financial_summary', '')}", style="dim")


def _print_skeptic(skep: dict) -> None:
    console.print(Rule("Skeptic"))
    score = skep.get("sentiment_score", 0)
    label = skep.get("sentiment_label", "neutral")
    bar   = SENTIMENT_BAR.get(label, "")
    color = "red" if score < -0.3 else "yellow" if score < 0.3 else "green"
    console.print(f"  Sentiment: [{color}]{score:+.2f}  {label}  {bar}[/{color}]")
    for flag in skep.get("risk_flags", []):
        icon = SEVERITY_ICON.get(flag["severity"], "(-)")
        sev_color = "red" if flag["severity"] == "high" else "yellow"
        console.print(
            f"\n  {icon} [{sev_color}][{flag['severity'].upper()}][/{sev_color}] "
            f"[bold]{flag['category']}[/bold]"
        )
        console.print(f"     {flag['description']}", style="dim")
    for sig in skep.get("positive_signals", []):
        console.print(f"\n  [green](+)[/green] {sig}")


def _print_hitl_prompt(payload: dict) -> None:
    score  = payload.get("sentiment_score", 0)
    label  = payload.get("sentiment_label", "neutral")
    flags  = payload.get("risk_flags", [])
    color  = "red" if score < -0.3 else "yellow" if score < 0.3 else "green"

    console.print(Rule("[bold yellow]HUMAN REVIEW REQUIRED[/bold yellow]"))
    console.print(
        f"  Company: [bold]{payload.get('company')}[/bold]  |  "
        f"Sentiment: [{color}]{score:+.2f} ({label})[/{color}]  |  "
        f"Sources: {payload.get('sources_analyzed', 0)}"
    )
    console.print(f"\n  [bold]Risk Flags ({len(flags)}):[/bold]")
    for i, flag in enumerate(flags, 1):
        icon      = SEVERITY_ICON.get(flag["severity"], "(-)")
        sev_color = "red" if flag["severity"] == "high" else "yellow"
        console.print(
            f"\n  {i}. {icon} [{sev_color}][{flag['severity'].upper()}][/{sev_color}] "
            f"[bold]{flag['category']}[/bold]"
        )
        console.print(f"     {flag['description']}", style="dim")

    console.print(f"\n  [bold]Skeptic summary:[/bold]")
    console.print(f"  {payload.get('summary', '')}", style="dim")

    console.print(Rule())
    console.print("  [dim]Enter[/dim]          → approve, generate report")
    console.print("  [dim]Type a note[/dim]    → approve with analyst note attached")
    console.print("  [dim]abort[/dim]          → cancel run")
    console.print(Rule())


def _get_human_decision() -> dict:
    try:
        raw = input("\n  Your decision: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [yellow]Interrupted — aborting.[/yellow]")
        return {"approved": False, "edits": None}

    if raw.lower() == "abort":
        console.print("  [red]Run aborted.[/red]")
        return {"approved": False, "edits": None}

    edits = raw if raw else None
    console.print(
        "  [green]Approved.[/green]"
        + (f" Analyst note: '{edits}'" if edits else "")
    )
    return {"approved": True, "edits": edits}


def run(company: str) -> None:
    thread_id = str(uuid.uuid4())
    config    = {"configurable": {"thread_id": thread_id}}

    console.print(Rule(f"[bold]FirmSignal[/bold] — {company}"))
    console.print(f"  Thread: [dim]{thread_id[:8]}...[/dim]\n")

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

    # Phase 1: Scout → Accountant → Skeptic → HITL pause
    app.invoke(initial_state, config=config)

    current_state = app.get_state(config)

    if current_state.values.get("error"):
        console.print(f"\n[red]Error: {current_state.values['error']}[/red]")
        return

    if not current_state.next:
        console.print("\n[yellow]Run ended without HITL — check graph configuration.[/yellow]")
        return

    # Retrieve interrupt payload
    interrupt_payload = None
    for task in current_state.tasks:
        if task.interrupts:
            interrupt_payload = task.interrupts[0].value
            break

    # Print intermediate results
    values = current_state.values
    if values.get("scout_output"):
        _print_scout(values["scout_output"])
    if values.get("accountant_output"):
        _print_accountant(values["accountant_output"])
    if values.get("skeptic_output"):
        _print_skeptic(values["skeptic_output"])

    # HITL prompt
    _print_hitl_prompt(interrupt_payload or {})
    decision = _get_human_decision()

    # Phase 2: Resume → Synthesizer → END
    final = app.invoke(Command(resume=decision), config=config)

    if final.get("error"):
        console.print(f"\n[red]Error: {final['error']}[/red]")
        return

    brief = final.get("final_brief")
    if not brief:
        console.print("\n[yellow]Run aborted — no brief generated.[/yellow]")
        return

    # Render the final brief
    console.print(Rule("[bold green]Intelligence Brief[/bold green]"))
    console.print(Markdown(brief))
    console.print(Rule())
    console.print(
        f"  [dim]Total sources collected: {len(final.get('sources', []))}[/dim]"
    )


if __name__ == "__main__":
    company = sys.argv[1] if len(sys.argv) > 1 else "Nvidia"
    run(company)