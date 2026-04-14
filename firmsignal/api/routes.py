import asyncio
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from firmsignal.api.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ResumeRequest,
    ResumeResponse,
    RunStatusResponse,
)
from firmsignal.api.runner import run_pipeline
from firmsignal.api.store import RunStatus, create_run, get_run

router = APIRouter(prefix="/api")


# ── POST /api/analyze ──────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest, background: BackgroundTasks):
    """
    Kicks off a FirmSignal run.
    Returns immediately with run_id — the frontend uses this to open
    the SSE stream and later to call /resume.
    """
    if not req.company.strip():
        raise HTTPException(status_code=422, detail="Company name cannot be empty")

    run_id = str(uuid.uuid4())
    record = create_run(run_id, req.company.strip())

    # Start the pipeline as a background task so this endpoint returns instantly
    background.add_task(run_pipeline, record)

    return AnalyzeResponse(run_id=run_id, company=record.company)


# ── GET /api/stream/{run_id} ───────────────────────────────────────────────────

@router.get("/stream/{run_id}")
async def stream(run_id: str):
    """
    Server-Sent Events stream for a run.

    The frontend opens this immediately after POST /analyze and keeps it
    open until the sentinel (None) arrives, which signals completion.

    Event types the frontend receives:
    - agent_start      → show spinner for that agent
    - agent_complete   → show agent output section
    - hitl_required    → show the HITL review panel
    - complete         → render the final brief
    - aborted          → show abort message
    - error            → show error message
    """
    record = get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        while True:
            try:
                item = await asyncio.wait_for(record.events.get(), timeout=60.0)
            except asyncio.TimeoutError:
                # Keep-alive ping — prevents proxy/browser from closing idle connections
                yield "event: ping\ndata: {}\n\n"
                continue

            if item is None:
                # Sentinel — pipeline finished
                yield "event: done\ndata: {}\n\n"
                break

            event = item["event"]
            data  = json.dumps(item["data"])
            yield f"event: {event}\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",   # disables Nginx buffering
            "Access-Control-Allow-Origin": "*",
        },
    )


# ── POST /api/resume/{run_id} ──────────────────────────────────────────────────

@router.post("/resume/{run_id}", response_model=ResumeResponse)
async def resume(run_id: str, req: ResumeRequest):
    """
    Injects the human HITL decision and resumes the graph.

    The background task is blocked on resume_event.wait() —
    setting it here unblocks it immediately.
    """
    record = get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Run not found")
    if record.status != RunStatus.PAUSED:
        raise HTTPException(
            status_code=409,
            detail=f"Run is not paused (current status: {record.status})"
        )

    record.resume_payload = {"approved": req.approved, "edits": req.edits}
    record.resume_event.set()   # unblocks the background task

    status = "resumed" if req.approved else "aborted"
    return ResumeResponse(run_id=run_id, status=status)


# ── GET /api/status/{run_id} ───────────────────────────────────────────────────

@router.get("/status/{run_id}", response_model=RunStatusResponse)
async def status(run_id: str):
    """
    Lightweight polling endpoint — useful for reconnecting after
    a lost SSE connection without re-running the pipeline.
    """
    record = get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunStatusResponse(
        run_id=     run_id,
        company=    record.company,
        status=     record.status,
        has_brief=  record.brief is not None,
        error=      record.error,
    )