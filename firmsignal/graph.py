from dotenv import load_dotenv
load_dotenv()

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from firmsignal.agents.accountant import accountant_node
from firmsignal.agents.hitl import hitl_node
from firmsignal.agents.scout import scout_node
from firmsignal.agents.skeptic import skeptic_node
from firmsignal.state import FirmState


def create_graph():
    graph = StateGraph(FirmState)

    graph.add_node("scout",      scout_node)
    graph.add_node("accountant", accountant_node)
    graph.add_node("skeptic",    skeptic_node)
    graph.add_node("hitl",       hitl_node)
    # synthesizer node goes here next week

    graph.set_entry_point("scout")
    graph.add_edge("scout",      "accountant")
    graph.add_edge("accountant", "skeptic")
    graph.add_edge("skeptic",    "hitl")
    graph.add_edge("hitl",       END)   # → "synthesizer" next week

    # MemorySaver persists state in-process.
    # Week 5: swap this for AsyncSqliteSaver or Supabase so state
    # survives server restarts between the pause and the resume.
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


app = create_graph()