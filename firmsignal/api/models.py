import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    company: str = Field(
        min_length=2,
        max_length=100,
        description="Company name, ticker symbol, or common name",
    )

    @field_validator("company")
    @classmethod
    def company_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Company name cannot be blank")
        return v.strip()


class AnalyzeResponse(BaseModel):
    run_id: str
    company: str
    status: str = "started"


class ResumeRequest(BaseModel):
    approved: bool
    edits: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional analyst note — max 1000 characters",
    )

    @field_validator("edits")
    @classmethod
    def sanitize_edits(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = re.sub(r"<[^>]+>", "", v)
        return cleaned.strip() or None


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
