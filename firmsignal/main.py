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

    scout = result.get("scout_output")
    if not scout:
        print("No scout output produced.")
        return

    print(f"\n{'═' * 55}")
    print(f"  Scout Report — {scout['company_name']}  ({scout['research_date']})")
    print(f"{'═' * 55}")

    print(f"\nNews ({len(scout['news_items'])} items)")
    for item in scout["news_items"]:
        print(f"  • {item['headline']}")
        print(f"    {item['date']}  |  {item['url']}")
        print(f"    {item['summary']}\n")

    if scout["leadership_changes"]:
        print(f"Leadership Changes")
        for c in scout["leadership_changes"]:
            print(f"  • {c['name']} ({c['role']}) — {c['change_type']} — {c['date']}")

    if scout["key_events"]:
        print(f"\nKey Events")
        for e in scout["key_events"]:
            print(f"  • {e}")

    print(f"\nSources collected: {len(result['sources'])}")


if __name__ == "__main__":
    company = sys.argv[1] if len(sys.argv) > 1 else "Stripe"
    run(company)