import asyncio
from concurrent.futures import ThreadPoolExecutor

from firmsignal.agents.accountant  import accountant_node
from firmsignal.agents.normalizer  import normalizer_node
from firmsignal.agents.scout       import scout_node
from firmsignal.agents.skeptic     import skeptic_node
from firmsignal.agents.synthesizer import synthesizer_node
from firmsignal.api.store import RunRecord, RunStatus

_executor = ThreadPoolExecutor(max_workers=4)


async def _put(record: RunRecord, event: str, data: dict) -> None:
    await record.events.put({"event": event, "data": data})


async def _error(record: RunRecord, msg: str) -> None:
    record.status = RunStatus.ERROR
    record.error  = msg
    await _put(record, "error", {"message": msg})
    await record.events.put(None)


async def run_pipeline(record: RunRecord) -> None:
    """
    Runs the FirmSignal pipeline agent by agent, emitting SSE events
    in real time between each step.

    Each agent is called directly (not via app.stream) so we control
    exactly when progress events fire — no LangGraph stream buffering.
    """
    company = record.company
    run_id  = record.run_id
    loop    = asyncio.get_event_loop()

    state: dict = {
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

    async def run_node(fn):
        """Run a sync agent node in the thread pool. Returns its state update."""
        try:
            return await loop.run_in_executor(_executor, fn, dict(state))
        except Exception as e:
            return {"error": f"{fn.__name__} raised: {type(e).__name__}: {e}"}

    # ── 1. Normalizer ─────────────────────────────────────────────────────────
    result = await run_node(normalizer_node)
    if result.get("error"):
        await _error(record, result["error"])
        return
    state.update(result)

    if state.get("input_correction"):
        await _put(record, "correction", {
            "original": company,
            "resolved": state["company_name"],
            "note":     state["input_correction"],
        })

    # ── 2. Scout ──────────────────────────────────────────────────────────────
    await _put(record, "agent_start", {
        "agent": "scout",
        "log":   "Searching for recent news and leadership changes...",
    })

    result = await run_node(scout_node)
    if result.get("error"):
        await _error(record, result["error"])
        return
    state.update(result)

    scout_out = state.get("scout_output") or {}
    await _put(record, "agent_complete", {
        "agent":  "scout",
        "log":    (
            f"Found {len(scout_out.get('news_items', []))} news items and "
            f"{len(scout_out.get('leadership_changes', []))} leadership changes"
        ),
        "output": scout_out,
    })

    # ── 3. Accountant ─────────────────────────────────────────────────────────
    await _put(record, "agent_start", {
        "agent": "accountant",
        "log":   "Pulling financials and 5-year price history...",
    })

    result = await run_node(accountant_node)
    if result.get("error"):
        await _error(record, result["error"])
        return
    state.update(result)

    acc = state.get("accountant_output") or {}
    acc_log = (
        f"Ticker: {acc.get('ticker')} · Cap: {acc.get('market_cap_formatted')} · "
        f"{len(acc.get('price_history', []))} months of price data"
        if acc.get("is_public")
        else "Private company — no public market data"
    )
    await _put(record, "agent_complete", {
        "agent":  "accountant",
        "log":    acc_log,
        "output": acc,
    })

    # ── 4. Skeptic ────────────────────────────────────────────────────────────
    await _put(record, "agent_start", {
        "agent": "skeptic",
        "log":   "Analysing sentiment, reviews, and risk signals...",
    })

    result = await run_node(skeptic_node)
    if result.get("error"):
        await _error(record, result["error"])
        return
    state.update(result)

    skep = state.get("skeptic_output") or {}
    await _put(record, "agent_complete", {
        "agent":  "skeptic",
        "log":    (
            f"Sentiment: {skep.get('sentiment_score', 0):+.2f} "
            f"({skep.get('sentiment_label')}) · "
            f"{len(skep.get('risk_flags', []))} risk flags"
        ),
        "output": skep,
    })

    # ── 5. HITL pause ─────────────────────────────────────────────────────────
    record.status    = RunStatus.PAUSED
    record.hitl_data = skep  # store for reference

    await _put(record, "hitl_required", {
        "company":          state["company_name"],
        "sentiment_score":  skep.get("sentiment_score"),
        "sentiment_label":  skep.get("sentiment_label"),
        "risk_flags":       skep.get("risk_flags", []),
        "positive_signals": skep.get("positive_signals", []),
        "summary":          skep.get("summary", ""),
        "sources_analyzed": skep.get("sources_analyzed", 0),
    })

    await record.resume_event.wait()
    decision = record.resume_payload

    if not decision or not decision.get("approved"):
        record.status = RunStatus.ABORTED
        await _put(record, "aborted", {"run_id": run_id})
        await record.events.put(None)
        return

    # ── 6. Synthesizer ────────────────────────────────────────────────────────
    await _put(record, "agent_start", {
        "agent": "synthesizer",
        "log":   "Writing cited intelligence brief with Claude Sonnet...",
    })

    state["hitl_approved"] = True
    state["hitl_edits"]    = decision.get("edits")

    result = await run_node(synthesizer_node)
    if result.get("error"):
        await _error(record, result["error"])
        return

    brief         = result.get("final_brief")
    record.brief  = brief
    record.status = RunStatus.COMPLETE

    await _put(record, "agent_complete", {
        "agent": "synthesizer",
        "log":   "Brief generated successfully",
    })
    await _put(record, "complete", {
        "run_id":        run_id,
        "brief":         brief,
        "sources_count": len(state.get("sources", [])),
        "sources":       state.get("sources", []),
        "company":       state["company_name"],
    })
    await record.events.put(None)
