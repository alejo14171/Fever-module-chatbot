"""
LangGraph compiled agent — used by the FastAPI server (with PostgresSaver) and
by the test ConversationRunner (with InMemorySaver).
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from fever_routing.nodes.answer_question.node import answer_question_node
from fever_routing.nodes.close_conversation.node import close_conversation_node
from fever_routing.nodes.conversation_manager.node import (
    conversation_manager_node,
    manager_route,
)
from fever_routing.nodes.empathy_response.node import empathy_response_node
from fever_routing.nodes.greeting.node import greeting_node
from fever_routing.nodes.inquiry.node import inquiry_node
from fever_routing.nodes.receptor.node import receptor_node
from fever_routing.nodes.recommendation.node import recommendation_node
from fever_routing.nodes.reframe_question.node import reframe_question_node
from fever_routing.nodes.urgency_recommendation.node import urgency_recommendation_node
from fever_routing.routes.triage.route import triage_route
from fever_routing.state import State


def make_graph(config: TypedDict):
    checkpointer = config.get("checkpoint", None)
    if checkpointer is None:
        checkpointer = InMemorySaver()

    builder = StateGraph(State)
    builder.add_node("conversation_manager", conversation_manager_node)
    builder.add_node("greeting", greeting_node)
    builder.add_node("empathy_response", empathy_response_node)
    builder.add_node("answer_question", answer_question_node)
    builder.add_node("reframe_question", reframe_question_node)
    builder.add_node("close_conversation", close_conversation_node)
    builder.add_node("receptor", receptor_node)
    builder.add_node("inquiry", inquiry_node)
    builder.add_node("recommendation", recommendation_node)
    builder.add_node("urgency_recommendation", urgency_recommendation_node)

    builder.add_edge(START, "conversation_manager")
    builder.add_conditional_edges(
        "conversation_manager",
        manager_route,
        {
            "greeting": "greeting",
            "empathy_response": "empathy_response",
            "answer_question": "answer_question",
            "reframe_question": "reframe_question",
            "close_conversation": "close_conversation",
            "receptor": "receptor",
        },
    )
    builder.add_conditional_edges(
        "receptor",
        triage_route,
        {
            "inquiry": "inquiry",
            "recommendation": "recommendation",
            "urgency_recommendation": "urgency_recommendation",
            "answer_question": "answer_question",
        },
    )
    for n in ("greeting", "empathy_response", "answer_question", "reframe_question",
              "close_conversation", "inquiry", "recommendation", "urgency_recommendation"):
        builder.add_edge(n, END)

    return builder.compile(checkpointer=checkpointer)
