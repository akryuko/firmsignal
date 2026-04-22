import operator
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


def _merge_errors(a: str | None, b: str | None) -> str | None:
    """Reducer for parallel branches that may each write an error or None."""
    if a is None:
        return b
    if b is None:
        return a
    return f"{a}\n{b}"


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
    # operator.add merges lists from parallel branches without conflict
    sources: Annotated[list[dict], operator.add]

    # LangGraph message history (required for streaming)
    messages: Annotated[list, add_messages]

    # Captures agent failures without crashing the graph
    # _merge_errors handles concurrent writes from parallel branches
    error: Annotated[str | None, _merge_errors]