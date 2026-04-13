from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import END, StateGraph

from firmsignal.agents.scout import scout_node
from firmsignal.agents.accountant import accountant_node
from firmsignal.agents.skeptic import skeptic_node
from firmsignal.state import FirmState


def create_graph():
    graph = StateGraph(FirmState)

    graph.add_node("scout", scout_node)
    graph.add_node("accountant", accountant_node)
    graph.add_node("skeptic", skeptic_node)

    # HITL and Synthesizer go here next week
    graph.set_entry_point("scout")
    graph.add_edge("scout", "accountant")
    graph.add_edge("accountant", "skeptic")
    graph.add_edge("skeptic", END)

    return graph.compile()


app = create_graph()