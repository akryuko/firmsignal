from dotenv import load_dotenv
load_dotenv()

import sys
from firmsignal.graph import app
from firmsignal.state import FirmState


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

    # ── Scout output ───────────────────────────────────────────────────────────
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

    # ── Accountant output ──────────────────────────────────────────────────────
    acc = result.get("accountant_output")
    if acc:
        print(f"\n{'═' * 55}")
        print(f"  Accountant — {acc['company_name']}  ({acc.get('ticker', 'Private')})")
        print(f"{'═' * 55}")

        if not acc["is_public"]:
            print(f"\n  {acc['financial_summary']}")
        else:
            print(f"\n  Price:       ${acc['current_price']}  ({acc['currency']})")
            print(f"  Market Cap:  {acc['market_cap_formatted']}")
            print(f"  P/E Ratio:   {acc['pe_ratio']}")
            print(f"  Revenue:     {acc['revenue_formatted']}")
            print(f"  Gross Margin:{acc['gross_margin_pct']}%")
            print(f"  Debt/Equity: {acc['debt_to_equity']}")
            print(f"  Employees:   {acc['employee_count']:,}" if acc["employee_count"] else "  Employees:   N/A")
            print(f"\n  1Y change:   {acc['price_change_1y']}%")
            print(f"  5Y change:   {acc['price_change_5y']}%")
            print(f"\n  Price history points: {len(acc['price_history'])}")
            print(f"  Range: {acc['price_history'][0]['date']} → {acc['price_history'][-1]['date']}")
            print(f"\n  Summary: {acc['financial_summary']}")

    print(f"\n  Total sources collected: {len(result['sources'])}")


if __name__ == "__main__":
    company = sys.argv[1] if len(sys.argv) > 1 else "Nvidia"
    run(company)