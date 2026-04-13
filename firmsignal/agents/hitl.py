from langgraph.types import interrupt

from firmsignal.state import FirmState


def hitl_node(state: FirmState) -> dict:
    """
    LangGraph HITL node.

    Calls interrupt() which does three things:
    1. Serialises the entire FirmState to the checkpointer (MemorySaver for now)
    2. Freezes the graph — no further nodes run
    3. Returns the payload to whoever is driving the graph (CLI today, FastAPI in Week 5)

    The graph stays frozen until app.invoke(Command(resume=...), config=config)
    is called with the same thread_id. Whatever is passed to Command(resume=...)
    becomes the return value of interrupt() here.

    This means the HITL node is also the contract between the graph and the UI —
    the interrupt payload is exactly what the frontend will render.
    """
    skeptic = state.get("skeptic_output") or {}

    human_response = interrupt({
        "company":          state["company_name"],
        "sentiment_score":  skeptic.get("sentiment_score"),
        "sentiment_label":  skeptic.get("sentiment_label"),
        "risk_flags":       skeptic.get("risk_flags", []),
        "positive_signals": skeptic.get("positive_signals", []),
        "employee_sentiment": skeptic.get("employee_sentiment", ""),
        "summary":          skeptic.get("summary", ""),
        "sources_analyzed": skeptic.get("sources_analyzed", 0),
    })

    # human_response is whatever was passed to Command(resume=...)
    approved = human_response.get("approved", False)
    edits    = human_response.get("edits")

    print(
        f"\n[HITL] Human decision received — "
        f"{'approved' if approved else 'rejected'}"
        + (f" with edits" if edits else "")
    )

    return {
        "hitl_approved": approved,
        "hitl_edits":    edits,
    }