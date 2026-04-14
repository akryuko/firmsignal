import asyncio
from concurrent.futures import ThreadPoolExecutor

from langgraph.types import Command

from firmsignal.api.store import RunRecord, RunStatus
from firmsignal.graph import app
from firmsignal.state import FirmState

_executor = ThreadPoolExecutor(max_workers=4)


async def _put(record: RunRecord, event: str, data: dict) -> None:
    await record.events.put({"event": event, "data": data})


def _invoke_sync(state: FirmState, config: dict) -> None:
    app.invoke(state, config=config)


def _resume_sync(decision: dict, config: dict) -> dict:
    return app.invoke(Command(resume=decision), config=config)


async def run_pipeline(record: RunRecord) -> None:
    company = record.company
    run_id  = record.run_id
    config  = {"configurable": {"thread_id": run_id}}
    loop    = asyncio.get_event_loop()

    initial_state: FirmState = {
        "company_name":     company,
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

    # ── Emit granular progress events before each agent ────────────────────────
    await _put(record, "agent_start", {
        "agent": "normalizer",
        "log":   f"Resolving company name: '{company}'..."
    })
    await _put(record, "agent_start", {
        "agent": "scout",
        "log":   "Searching for recent news and leadership changes..."
    })

    try:
        await loop.run_in_executor(_executor, _invoke_sync, initial_state, config)
    except Exception as e:
        record.status = RunStatus.ERROR
        record.error  = str(e)
        await _put(record, "error", {"message": str(e)})
        await record.events.put(None)
        return

    graph_state = app.get_state(config)

    if graph_state.values.get("error"):
        err = graph_state.values["error"]
        record.status = RunStatus.ERROR
        record.error  = err
        await _put(record, "error", {"message": err})
        await record.events.put(None)
        return

    values = graph_state.values

    # Emit correction notice if normalizer changed the name
    correction = values.get("input_correction")
    if correction:
        await _put(record, "correction", {
            "original":  company,
            "resolved":  values.get("company_name"),
            "note":      correction,
        })

    # Emit each agent's completed output
    if values.get("scout_output"):
        await _put(record, "agent_complete", {
            "agent":  "scout",
            "log":    f"Found {len(values['scout_output'].get('news_items', []))} news items and {len(values['scout_output'].get('leadership_changes', []))} leadership changes",
            "output": values["scout_output"],
        })

    await _put(record, "agent_start", {
        "agent": "accountant",
        "log":   "Pulling financials and 5-year price history..."
    })

    if values.get("accountant_output"):
        acc = values["accountant_output"]
        if acc.get("is_public"):
            log = f"Ticker: {acc.get('ticker')} · Cap: {acc.get('market_cap_formatted')} · {len(acc.get('price_history', []))} months of price data"
        else:
            log = "Private company — no public market data"
        await _put(record, "agent_complete", {
            "agent":  "accountant",
            "log":    log,
            "output": acc,
        })

    await _put(record, "agent_start", {
        "agent": "skeptic",
        "log":   "Analysing sentiment, Glassdoor reviews, and risk signals..."
    })

    if values.get("skeptic_output"):
        skep = values["skeptic_output"]
        await _put(record, "agent_complete", {
            "agent":  "skeptic",
            "log":    f"Sentiment: {skep.get('sentiment_score', 0):+.2f} ({skep.get('sentiment_label')}) · {len(skep.get('risk_flags', []))} risk flags",
            "output": skep,
        })

    # ── HITL pause ─────────────────────────────────────────────────────────────
    interrupt_payload = None
    for task in graph_state.tasks:
        if task.interrupts:
            interrupt_payload = task.interrupts[0].value
            break

    record.status    = RunStatus.PAUSED
    record.hitl_data = interrupt_payload

    await _put(record, "hitl_required", {
        "company":          values.get("company_name", company),
        "sentiment_score":  interrupt_payload.get("sentiment_score") if interrupt_payload else None,
        "sentiment_label":  interrupt_payload.get("sentiment_label") if interrupt_payload else None,
        "risk_flags":       interrupt_payload.get("risk_flags", []) if interrupt_payload else [],
        "positive_signals": interrupt_payload.get("positive_signals", []) if interrupt_payload else [],
        "summary":          interrupt_payload.get("summary", "") if interrupt_payload else "",
        "sources_analyzed": interrupt_payload.get("sources_analyzed", 0) if interrupt_payload else 0,
    })

    # ── Wait for human ─────────────────────────────────────────────────────────
    await record.resume_event.wait()
    decision = record.resume_payload

    if not decision or not decision.get("approved"):
        record.status = RunStatus.ABORTED
        await _put(record, "aborted", {"run_id": run_id})
        await record.events.put(None)
        return

    # ── Phase 2: Resume ────────────────────────────────────────────────────────
    await _put(record, "agent_start", {
        "agent": "synthesizer",
        "log":   "Writing cited intelligence brief with Claude Sonnet..."
    })

    try:
        final = await loop.run_in_executor(_executor, _resume_sync, decision, config)
    except Exception as e:
        record.status = RunStatus.ERROR
        record.error  = str(e)
        await _put(record, "error", {"message": str(e)})
        await record.events.put(None)
        return

    if final.get("error"):
        record.status = RunStatus.ERROR
        record.error  = final["error"]
        await _put(record, "error", {"message": final["error"]})
        await record.events.put(None)
        return

    brief         = final.get("final_brief")
    record.brief  = brief
    record.status = RunStatus.COMPLETE

    await _put(record, "agent_complete", {
        "agent": "synthesizer",
        "log":   "Brief generated successfully",
    })

    await _put(record, "complete", {
        "run_id":        run_id,
        "brief":         brief,
        "sources_count": len(final.get("sources", [])),
        "sources":       final.get("sources", []),
        "company":       final.get("company_name", company),
    })

    await record.events.put(None)