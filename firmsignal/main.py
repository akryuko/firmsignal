from dotenv import load_dotenv
load_dotenv()

import sys
from firmsignal.graph import app
from firmsignal.state import FirmState

SEVERITY_ICON = {"high": "(!)", "medium": "(*)", "low": "(-)"}


def run(company: str):
    initial_state: FirmState = {
        "company_name": company,
        "scout_output": None,
        "accountant_output": None,
        "skeptic_output": None,
        "hitl_approved": False,
        "hitl_edits": None,
        "final_brief": None,
        "sources": [],
        "messages": [],
        "error": None,
    }

    result = app.invoke(initial_state)

    if result.get("error"):
        print(f"\nError: {result['error']}")
        return

    # ── Scout ──────────────────────────────────────────────────────────────────
    scout = result.get("scout_output")
    if scout:
        print(f"\n{'═' * 55}")
        print(f"  Scout — {scout['company_name']}  ({scout['research_date']})")
        print(f"{'═' * 55}")
        for item in scout["news_items"]:
            print(f"\n  • {item['headline']}")
            print(f"    {item['date']}  |  {item['url']}")
        if scout["leadership_changes"]:
            print(f"\n  Leadership changes:")
            for c in scout["leadership_changes"]:
                print(f"    – {c['name']} ({c['role']}): {c['change_type']}")

    # ── Accountant ─────────────────────────────────────────────────────────────
    acc = result.get("accountant_output")
    if acc:
        print(f"\n{'═' * 55}")
        print(f"  Accountant — {acc.get('ticker', 'Private')}")
        print(f"{'═' * 55}")
        if acc["is_public"]:
            print(f"\n  Price:        ${acc['current_price']}  ({acc['currency']})")
            print(f"  Market Cap:   {acc['market_cap_formatted']}")
            print(f"  Revenue:      {acc['revenue_formatted']}")
            print(f"  P/E:          {acc['pe_ratio']}")
            print(f"  Gross Margin: {acc['gross_margin_pct']}%")
            print(f"  1Y / 5Y:      {acc['price_change_1y']}% / {acc['price_change_5y']}%")
            print(f"  History:      {len(acc['price_history'])} months")
        print(f"\n  {acc['financial_summary']}")

    # ── Skeptic ────────────────────────────────────────────────────────────────
    skep = result.get("skeptic_output")
    if skep:
        print(f"\n{'═' * 55}")
        print(f"  Skeptic — sentiment: {skep['sentiment_score']:+.2f}  ({skep['sentiment_label']})")
        print(f"{'═' * 55}")

        if skep["risk_flags"]:
            print(f"\n  Risk Flags:")
            for flag in skep["risk_flags"]:
                icon = SEVERITY_ICON.get(flag["severity"], "(-)")
                print(f"\n    {icon} [{flag['severity'].upper()}] {flag['category']}")
                print(f"       {flag['description']}")
                print(f"       {flag['source_url']}")

        if skep["positive_signals"]:
            print(f"\n  Positive Signals:")
            for sig in skep["positive_signals"]:
                print(f"    + {sig}")

        print(f"\n  Employee sentiment:  {skep['employee_sentiment']}")
        print(f"  Public sentiment:    {skep['public_sentiment']}")
        print(f"\n  Summary: {skep['summary']}")
        print(f"\n  Sources analysed: {skep['sources_analyzed']}")

    print(f"\n{'─' * 55}")
    print(f"  Total citations collected: {len(result['sources'])}")


if __name__ == "__main__":
    company = sys.argv[1] if len(sys.argv) > 1 else "Nvidia"
    run(company)