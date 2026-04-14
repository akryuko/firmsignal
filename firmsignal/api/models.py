from pydantic import BaseModel


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