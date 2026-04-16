import json
import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from firmsignal.state import FirmState


_SYSTEM = """\
You are a company name resolver. Given any user input — including misspellings,
abbreviations, ticker symbols, or informal names — return the correct official
company name and stock ticker.

Respond with ONLY a valid JSON object, no other text:
{
  "official_name": "Alphabet Inc.",
  "common_name": "Google",
  "ticker": "GOOGL",
  "is_likely_private": false,
  "corrected": true,
  "note": "User typed 'Googlee' — resolved to Google (Alphabet Inc.)"
}

Rules:
- official_name: the legal company name
- common_name: what people call it day-to-day (use this as company_name in state)
- ticker: primary exchange ticker, or null if private/unknown
- is_likely_private: true for Stripe, OpenAI, SpaceX etc.
- corrected: true if you changed the input at all
- note: one sentence explaining what you did, only if corrected is true

Examples:
- "Googlee" → Google (Alphabet), GOOGL, corrected: true
- "AAPL" → Apple Inc., AAPL, corrected: true
- "microsoft" → Microsoft, MSFT, corrected: true
- "stripe" → Stripe, null, private: true
- "Nvidia" → Nvidia, NVDA, corrected: false
"""


def normalizer_node(state: FirmState) -> dict:
    """
    LangGraph node — Company Name Normalizer.

    First node in the graph. Resolves whatever the user typed into a
    clean, official company name before any agent runs.
    Handles: misspellings, ticker symbols, abbreviations, casing.
    """
    raw_input = state["company_name"]

    # Guard — should already be clean from API layer, but agents can be
    # called directly in tests or invoked without going through the routes.
    if not raw_input or not raw_input.strip():
        return {
            "company_name":     "Unknown",
            "ticker_hint":      None,
            "is_private_hint":  False,
            "input_correction": None,
            "error": "Empty company name reached normalizer — check API validation layer",
        }

    if len(raw_input) > 100:
        raw_input = raw_input[:100]
        print(f"[Normalizer] Input truncated to 100 chars")

    print(f"\n[Normalizer] Resolving '{raw_input}'...")

    try:
        llm = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            temperature=0,
            max_tokens=200,
        )

        response = llm.invoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=raw_input),
        ])

        text = response.content.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        data = json.loads(text)

        common_name   = data.get("common_name") or data.get("official_name") or raw_input
        ticker_hint   = data.get("ticker")
        is_private    = data.get("is_likely_private", False)
        corrected     = data.get("corrected", False)
        note          = data.get("note", "")

        if corrected:
            print(f"[Normalizer] Corrected: '{raw_input}' → '{common_name}' ({ticker_hint or 'private'})")
            if note:
                print(f"[Normalizer] Note: {note}")
        else:
            print(f"[Normalizer] Confirmed: '{common_name}' ({ticker_hint or 'private'})")

        return {
            "company_name":     common_name,
            "ticker_hint":      ticker_hint,
            "is_private_hint":  is_private,
            "input_correction": note if corrected else None,
            "error":            None,
        }

    except Exception as e:
        # Non-fatal — pass original input through if normalizer fails
        print(f"[Normalizer] Failed ({e}) — using raw input")
        return {
            "company_name":     raw_input,
            "ticker_hint":      None,
            "is_private_hint":  False,
            "input_correction": None,
            "error":            None,
        }