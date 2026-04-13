from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import END, StateGraph

from firmsignal.agents.scout import scout_node
from firmsignal.state import FirmState


def create_graph():
    graph = StateGraph(FirmState)

    graph.add_node("scout", scout_node)

    # Accountant, Skeptic, HITL, Synthesizer nodes go here in coming weeks
    graph.set_entry_point("scout")
    graph.add_edge("scout", END)

    return graph.compile()


app = create_graph()