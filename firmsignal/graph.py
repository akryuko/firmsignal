from dotenv import load_dotenv
load_dotenv()

# Timeout budget per run (before HITL):
# Normalizer:  10s
# Scout:       45s
# Accountant:  20s
# Skeptic:     60s
# Total max:  135s before HITL pause
# Synthesizer: 90s after HITL approval

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from firmsignal.agents.accountant  import accountant_node
from firmsignal.agents.hitl        import hitl_node
from firmsignal.agents.normalizer  import normalizer_node
from firmsignal.agents.scout       import scout_node
from firmsignal.agents.skeptic     import skeptic_node
from firmsignal.agents.synthesizer import synthesizer_node
from firmsignal.state import FirmState


def _route_after_hitl(state: FirmState) -> str:
    return "synthesizer" if state.get("hitl_approved") else END


def create_graph():
    graph = StateGraph(FirmState)

    graph.add_node("normalizer",  normalizer_node)
    graph.add_node("scout",       scout_node)
    graph.add_node("accountant",  accountant_node)
    graph.add_node("skeptic",     skeptic_node)
    graph.add_node("hitl",        hitl_node)
    graph.add_node("synthesizer", synthesizer_node)

    graph.set_entry_point("normalizer")
    graph.add_edge("normalizer",  "scout")
    graph.add_edge("scout",       "accountant")
    graph.add_edge("accountant",  "skeptic")
    graph.add_edge("skeptic",     "hitl")
    graph.add_conditional_edges("hitl", _route_after_hitl)
    graph.add_edge("synthesizer", END)

    return graph.compile(checkpointer=MemorySaver())


app = create_graph()