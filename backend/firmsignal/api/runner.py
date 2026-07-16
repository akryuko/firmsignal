import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

from firmsignal.agents.accountant  import accountant_node
from firmsignal.agents.normalizer  import normalizer_node
from firmsignal.agents.scout       import scout_node
from firmsignal.agents.skeptic     import skeptic_node
from firmsignal.agents.synthesizer import stream_synthesizer
from firmsignal.api.store import RunRecord, RunStatus

_executor = ThreadPoolExecutor(max_workers=4)


async def _put(record: RunRecord, event: str, data: dict) -> None:
    await record.broadcast({"event": event, "data": data})


async def _error(record: RunRecord, msg: str) -> None:
    record.status = RunStatus.ERROR
    record.error  = msg
    await _put(record, "error", {"message": msg})
    await record.broadcast(None)


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

    # Unified LangSmith parent trace spanning the entire pipeline,
    # including the HITL pause. No-op if LangSmith is not configured.
    _ls_ctx = None
    try:
        from langsmith import trace as _ls_trace
        _ls_ctx = _ls_trace(
            f"FirmSignal — {company}",
            run_type="chain",
            tags=["pipeline", company],
            metadata={
                "firmsignal_run_id": run_id,
                "company":           company,
                "mode":              "ui",
            },
        )
        _ls_ctx.__enter__()
    except Exception:
        pass

    try:
        async def run_node(fn, agent_name: str | None = None):
            """Run a sync agent node in the thread pool. Returns its state update."""
            outer_ctx = copy_context()

            def _call():
                # Build the named span FIRST, then copy context so any sub-thread
                # spawned inside fn (e.g. synthesizer's inner ThreadPoolExecutor)
                # inherits the agent span rather than the parent FirmSignal span.
                trace_cm = None
                if agent_name:
                    try:
                        from langsmith import trace as _ls_trace
                        trace_cm = _ls_trace(agent_name, run_type="chain")
                    except Exception:
                        pass

                if trace_cm is None:
                    return fn(dict(state))

                with trace_cm:
                    return copy_context().run(fn, dict(state))

            try:
                return await loop.run_in_executor(_executor, outer_ctx.run, _call)
            except Exception as e:
                return {"error": f"{fn.__name__} raised: {type(e).__name__}: {e}"}

        # ── 1. Normalizer ─────────────────────────────────────────────────────────
        result = await run_node(normalizer_node, "normalizer")
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

        # ── 2-4. Scout + Accountant + Skeptic (parallel fan-out) ─────────────────
        await _put(record, "agent_start", {
            "agent": "scout",
            "log":   "Searching for recent news and leadership changes...",
        })
        await _put(record, "agent_start", {
            "agent": "accountant",
            "log":   "Pulling financials and 5-year price history...",
        })
        await _put(record, "agent_start", {
            "agent": "skeptic",
            "log":   "Analysing sentiment, reviews, and risk signals...",
        })

        async def _run_scout():
            r = await run_node(scout_node, "scout")
            if not r.get("error"):
                out = r.get("scout_output") or {}
                await _put(record, "agent_complete", {
                    "agent":  "scout",
                    "log":    (
                        f"Found {len(out.get('news_items', []))} news items and "
                        f"{len(out.get('leadership_changes', []))} leadership changes"
                    ),
                    "output": out,
                })
            return r

        async def _run_accountant():
            r = await run_node(accountant_node, "accountant")
            if not r.get("error"):
                out = r.get("accountant_output") or {}
                log = (
                    f"Ticker: {out.get('ticker')} · Cap: {out.get('market_cap_formatted')} · "
                    f"{len(out.get('price_history', []))} months of price data"
                    if out.get("is_public")
                    else "Private company — no public market data"
                )
                await _put(record, "agent_complete", {
                    "agent":  "accountant",
                    "log":    log,
                    "output": out,
                })
            return r

        async def _run_skeptic():
            r = await run_node(skeptic_node, "skeptic")
            if not r.get("error"):
                out = r.get("skeptic_output") or {}
                await _put(record, "agent_complete", {
                    "agent":  "skeptic",
                    "log":    (
                        f"Sentiment: {out.get('sentiment_score', 0):+.2f} "
                        f"({out.get('sentiment_label')}) · "
                        f"{len(out.get('risk_flags', []))} risk flags"
                    ),
                    "output": out,
                })
            return r

        scout_r, acc_r, skep_r = await asyncio.gather(
            _run_scout(), _run_accountant(), _run_skeptic()
        )

        for r in (scout_r, acc_r, skep_r):
            if r.get("error"):
                await _error(record, r["error"])
                return

        state.update(scout_r)
        state.update(acc_r)
        state.update(skep_r)
        # Merge sources from all three (each agent only sees the pre-run snapshot)
        state["sources"] = (
            scout_r.get("sources", []) +
            acc_r.get("sources", []) +
            skep_r.get("sources", [])
        )

        skep = state.get("skeptic_output") or {}

        # ── 5. HITL pause ─────────────────────────────────────────────────────────
        record.status    = RunStatus.PAUSED
        record.hitl_data = skep

        await _put(record, "hitl_required", {
            "company":          state["company_name"],
            "sentiment_score":  skep.get("sentiment_score"),
            "sentiment_label":  skep.get("sentiment_label"),
            "risk_flags":       skep.get("risk_flags", []),
            "positive_signals": skep.get("positive_signals", []),
            "summary":          skep.get("summary", ""),
            "sources_analyzed": skep.get("sources_analyzed", 0),
        })

        _hitl_cm = None
        _hitl_rt = None
        try:
            from langsmith import trace as _ls_trace
            _hitl_cm = _ls_trace(
                "hitl",
                run_type="chain",
                metadata={"type": "human_in_the_loop", "company": state["company_name"]},
            )
            _hitl_rt = _hitl_cm.__enter__()
        except Exception:
            pass

        hitl_start = time.time()
        await record.resume_event.wait()
        hitl_duration = round(time.time() - hitl_start, 1)
        decision = record.resume_payload

        if _hitl_cm is not None:
            try:
                approved = bool(decision and decision.get("approved"))
                if _hitl_rt is not None and hasattr(_hitl_rt, "end"):
                    _hitl_rt.end(outputs={
                        "approved":   approved,
                        "duration_s": hitl_duration,
                        "edits":      decision.get("edits") if decision else None,
                    })
                _hitl_cm.__exit__(None, None, None)
            except Exception:
                pass

        if not decision or not decision.get("approved"):
            record.status = RunStatus.ABORTED
            await _put(record, "aborted", {"run_id": run_id})
            await record.broadcast(None)
            return

        # ── 6. Synthesizer (streamed paragraph by paragraph) ──────────────────────
        await _put(record, "agent_start", {
            "agent": "synthesizer",
            "log":   "Writing cited intelligence brief with Claude Sonnet...",
        })

        state["hitl_approved"] = True
        state["hitl_edits"]    = decision.get("edits")

        async def _on_paragraph(paragraph: str) -> None:
            await _put(record, "brief_paragraph", {"paragraph": paragraph})

        # stream_synthesizer is natively async (llm.astream), so it runs
        # directly on this loop rather than via run_node's thread pool —
        # that's what lets it await _put() per paragraph as tokens arrive
        # instead of blocking until the full ~90s call completes.
        _synth_cm = None
        try:
            from langsmith import trace as _ls_trace
            _synth_cm = _ls_trace("synthesizer", run_type="chain")
            _synth_cm.__enter__()
        except Exception:
            _synth_cm = None

        try:
            result = await stream_synthesizer(dict(state), _on_paragraph)
        finally:
            if _synth_cm is not None:
                try:
                    _synth_cm.__exit__(None, None, None)
                except Exception:
                    pass

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
        await record.broadcast(None)

    finally:
        if _ls_ctx is not None:
            _ls_ctx.__exit__(None, None, None)
