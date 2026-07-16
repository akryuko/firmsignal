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

    # SSE fan-out — each open /stream connection gets its own queue.
    # The frontend opens a fresh EventSource per page (waiting page,
    # then again on the HITL review page), so a single shared queue
    # would race: asyncio.Queue delivers each item to exactly one
    # waiter, and the stale first connection (still looping on .get()
    # after the client navigated away) would keep winning that race
    # and silently swallow the synthesizer's events.
    subscribers: list[asyncio.Queue] = field(default_factory=list)

    # Set when the graph pauses at HITL — the /resume endpoint
    # puts the human decision here so the background task can read it
    resume_event: asyncio.Event   = field(default_factory=asyncio.Event)
    resume_payload: dict | None   = None

    error:     str | None = None
    brief:     str | None = None
    hitl_data: dict | None = None   # interrupt payload shown to user

    def subscribe(self) -> asyncio.Queue:
        """Register a new SSE connection; returns its dedicated event queue."""
        queue: asyncio.Queue = asyncio.Queue()
        self.subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Called when an SSE connection closes, to stop fanning events to it."""
        if queue in self.subscribers:
            self.subscribers.remove(queue)

    async def broadcast(self, item: dict | None) -> None:
        """Send an event (or the None sentinel) to every open SSE connection."""
        for queue in list(self.subscribers):
            await queue.put(item)


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