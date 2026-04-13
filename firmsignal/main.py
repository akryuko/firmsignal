from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, END
from firmsignal.state import FirmState

def dummy_node(state: FirmState) -> dict:
    print(f"Processing: {state['company_name']}")
    return {"error": None}

graph = StateGraph(FirmState)
graph.add_node("dummy", dummy_node)
graph.set_entry_point("dummy")
graph.add_edge("dummy", END)
app = graph.compile()

if __name__ == "__main__":
    result = app.invoke({
        "company_name": "Apple",
        "scout_output": None,
        "accountant_output": None,
        "skeptic_output": None,
        "hitl_approved": False,
        "hitl_edits": None,
        "final_brief": None,
        "sources": [],
        "messages": [],
        "error": None,
    })
    print("Graph ran successfully:", result["company_name"])