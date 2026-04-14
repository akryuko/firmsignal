import asyncio
from dataclasses import dataclass, field
from enum import Enum


class RunStatus(str, Enum):
    RUNNING  = "running"
    PAUSED   = "paused"      # waiting at HITL
    COMPLETE = "complete"
    ABORTED  = "aborted"
    ERROR    = "error"


@dataclass
class RunRecord:
    run_id:  str
    company: str
    status:  RunStatus = RunStatus.RUNNING

    # SSE event queue — the background task puts events here,
    # the /stream endpoint reads from it
    events: asyncio.Queue = field(default_factory=asyncio.Queue)

    # Set when the graph pauses at HITL — the /resume endpoint
    # puts the human decision here so the background task can read it
    resume_event: asyncio.Event   = field(default_factory=asyncio.Event)
    resume_payload: dict | None   = None

    error:     str | None = None
    brief:     str | None = None
    hitl_data: dict | None = None   # interrupt payload shown to user


# Global in-memory store
# Week 5: replace with async Supabase calls
_runs: dict[str, RunRecord] = {}


def create_run(run_id: str, company: str) -> RunRecord:
    record = RunRecord(run_id=run_id, company=company)
    _runs[run_id] = record
    return record


def get_run(run_id: str) -> RunRecord | None:
    return _runs.get(run_id)


def all_runs() -> dict[str, RunRecord]:
    return _runs