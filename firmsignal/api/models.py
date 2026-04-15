from pydantic import BaseModel
from typing import Any


class AnalyzeRequest(BaseModel):
    company: str


class AnalyzeResponse(BaseModel):
    run_id: str
    company: str
    status: str = "started"


class ResumeRequest(BaseModel):
    approved: bool
    edits: str | None = None


class ResumeResponse(BaseModel):
    run_id: str
    status: str  # "resumed" | "aborted"


class RunStatusResponse(BaseModel):
    run_id: str
    company: str
    status: str   # "running" | "paused" | "complete" | "aborted" | "error"
    hitl_approved: bool | None = None
    has_brief: bool = False
    error: str | None = None


class PdfRequest(BaseModel):
    company: str
    brief: str | None = None
    accountant: dict[str, Any] | None = None
    skeptic: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = []
    ticker: str | None = None
    correction_note: str | None = None