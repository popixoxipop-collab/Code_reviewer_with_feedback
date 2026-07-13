# source notebook: Step1. 상품리뷰분석 Agent 1.ipynb (cells 42, 43)
from langgraph.graph import END, START, StateGraph

from nodes import analyzer_node, critic_node, route_next, supervisor_node
from state import ReviewState

builder = StateGraph(ReviewState)

builder.add_node("supervisor", supervisor_node)
builder.add_node("analyzer",   analyzer_node)
builder.add_node("critic",     critic_node)

builder.add_edge(START, "supervisor")
builder.add_conditional_edges(
    "supervisor",
    route_next,
    {"analyzer": "analyzer", "critic": "critic", "end": END}
)
builder.add_edge("analyzer", "supervisor")
builder.add_edge("critic",   "supervisor")

app = builder.compile()
