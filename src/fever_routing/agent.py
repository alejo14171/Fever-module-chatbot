from typing import TypedDict
from fever_routing.nodes.receptor.node import receptor_node
from fever_routing.nodes.inquiry.node import inquiry_node
from fever_routing.nodes.recommendation.node import recommendation_node
from fever_routing.nodes.urgency_recommendation.node import urgency_recommendation_node
from fever_routing.routes.triage.route import triage_route
from fever_routing.state import State

from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import InMemorySaver


def make_graph(config: TypedDict):
    checkpointer = config.get("checkpoint", None)
    if checkpointer is None:
        checkpointer = InMemorySaver()
        
    builder = StateGraph(State)
    builder.add_node("receptor", receptor_node)
    builder.add_node("inquiry", inquiry_node)
    builder.add_node("recommendation", recommendation_node)
    builder.add_node("urgency_recommendation", urgency_recommendation_node)

    builder.add_edge(START, "receptor")
    builder.add_conditional_edges(
    "receptor",
    triage_route,
    {
        "inquiry": "inquiry",
        "recommendation": "recommendation",
        "urgency_recommendation": "urgency_recommendation"
    }
)
    builder.add_edge("inquiry", END)
    builder.add_edge("recommendation", END)
    builder.add_edge("urgency_recommendation", END)

    agent = builder.compile(checkpointer=checkpointer)
    return agent
