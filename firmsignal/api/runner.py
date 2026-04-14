import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

from langgraph.types import Command

from firmsignal.api.store import RunRecord, RunStatus
from firmsignal.graph import app
from firmsignal.state import FirmState

# Single thread pool for all LangGraph runs.
# LangGraph graph execution is CPU-bound + sync — we offload it here
# so it never blocks the FastAPI event loop.
_executor = ThreadPoolExecutor(max_workers=4)


async def _put(record: RunRecord, event: str, data: dict) -> None:
    """Push an SSE event into the run's queue."""
    await record.events.put({"event": event, "data": data})


def _invoke_sync(state: FirmState, config: dict) -> None:
    """Runs the graph synchronously (called in thread pool)."""
    app.invoke(state, config=config)


def _resume_sync(decision: dict, config: dict) -> dict:
    """Resumes the graph synchronously (called in thread pool)."""
    return app.invoke(Command(resume=decision), config=config)


async def run_pipeline(record: RunRecord) -> None:
    """
    Async background task — drives one full FirmSignal run.

    Sequence:
    1. Build initial state, invoke graph in thread pool
    2. Graph pauses at HITL — emit 'paused' SSE event
    3. Wait for human decision via resume_event
    4. Resume graph in thread pool
    5. Emit 'complete' or 'aborted' SSE event
    """
    company   = record.company
    run_id    = record.run_id
    config    = {"configurable": {"thread_id": run_id}}
    loop      = asyncio.get_event_loop()

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

    # ── Phase 1 ────────────────────────────────────────────────────────────────

    await _put(record, "agent_start", {"agent": "scout", "company": company})

    try:
        # Run graph in thread pool — won't block the event loop
        await loop.run_in_executor(
            _executor, _invoke_sync, initial_state, config
        )
    except Exception as e:
        record.status = RunStatus.ERROR
        record.error  = str(e)
        await _put(record, "error", {"message": str(e)})
        await record.events.put(None)   # sentinel — closes the SSE stream
        return

    # Read the paused state
    graph_state = app.get_state(config)

    if graph_state.values.get("error"):
        err = graph_state.values["error"]
        record.status = RunStatus.ERROR
        record.error  = err
        await _put(record, "error", {"message": err})
        await record.events.put(None)
        return

    # Pull each agent's output out of state and emit as SSE events
    values = graph_state.values

    if values.get("scout_output"):
        await _put(record, "agent_complete", {
            "agent":  "scout",
            "output": values["scout_output"],
        })

    if values.get("accountant_output"):
        await _put(record, "agent_complete", {
            "agent":  "accountant",
            "output": values["accountant_output"],
        })

    if values.get("skeptic_output"):
        await _put(record, "agent_complete", {
            "agent":  "skeptic",
            "output": values["skeptic_output"],
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
        "company":          company,
        "sentiment_score":  interrupt_payload.get("sentiment_score") if interrupt_payload else None,
        "sentiment_label":  interrupt_payload.get("sentiment_label") if interrupt_payload else None,
        "risk_flags":       interrupt_payload.get("risk_flags", []) if interrupt_payload else [],
        "positive_signals": interrupt_payload.get("positive_signals", []) if interrupt_payload else [],
        "summary":          interrupt_payload.get("summary", "") if interrupt_payload else "",
        "sources_analyzed": interrupt_payload.get("sources_analyzed", 0) if interrupt_payload else 0,
    })

    # ── Wait for human ─────────────────────────────────────────────────────────

    # Blocks here until POST /resume/{run_id} fires resume_event
    await record.resume_event.wait()
    decision = record.resume_payload

    if not decision or not decision.get("approved"):
        record.status = RunStatus.ABORTED
        await _put(record, "aborted", {"run_id": run_id})
        await record.events.put(None)
        return

    # ── Phase 2: Resume ────────────────────────────────────────────────────────

    await _put(record, "agent_start", {"agent": "synthesizer"})

    try:
        final = await loop.run_in_executor(
            _executor, _resume_sync, decision, config
        )
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

    brief = final.get("final_brief")
    record.brief  = brief
    record.status = RunStatus.COMPLETE

    await _put(record, "complete", {
        "run_id":         run_id,
        "brief":          brief,
        "sources_count":  len(final.get("sources", [])),
        "sources":        final.get("sources", []),
    })

    # Sentinel — tells the SSE stream it can close
    await record.events.put(None)