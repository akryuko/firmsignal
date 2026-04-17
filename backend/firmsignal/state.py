from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class FirmState(TypedDict):
    company_name: str

    # Normalizer output
    ticker_hint:      str | None   # ticker resolved before Accountant runs
    is_private_hint:  bool         # private company flag from normalizer
    input_correction: str | None   # human-readable correction note for UI

    # Agent outputs — stored as dicts after .model_dump()
    scout_output: dict | None
    accountant_output: dict | None
    skeptic_output: dict | None

    # HITL fields
    hitl_approved: bool
    hitl_edits: str | None  # human can overwrite Skeptic's risk flags before Synthesizer runs

    # Final output
    final_brief: str | None

    # All source URLs collected across all agents — used for citation injection
    sources: list[dict]

    # LangGraph message history (required for streaming)
    messages: Annotated[list, add_messages]

    # Captures agent failures without crashing the graph
    error: str | None