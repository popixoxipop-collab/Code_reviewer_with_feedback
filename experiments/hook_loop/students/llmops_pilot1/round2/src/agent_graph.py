# source notebook: Step1. 상품리뷰분석 Agent 1.ipynb (cells 42, 43)
#
# ── 라우팅 구조 요약 (Step1 리뷰 피드백: planner->executor->critic 흐름의 역할을
#    각 파일에서 명확히 하라) ──────────────────────────────────────────────
#   supervisor(Planner)가 START 직후의 유일한 허브다. analyzer(Executor)와
#   critic(Critic)은 실행이 끝나면 항상 supervisor로 돌아오고, 절대 서로를 직접
#   호출하거나 END로 직행하지 않는다 -- "다음에 뭘 할지/언제 끝낼지"를 오직
#   supervisor(=nodes.py의 supervisor_node, 재시도 정책 포함) 한 곳에서만 결정하게
#   하려는 의도적 설계다. 그래서 analyzer/critic -> supervisor 엣지는 고정 엣지이고,
#   supervisor -> {analyzer, critic, end}만 조건부 엣지(route_next)로 되어 있다.
#
#   미션③(LangSmith): 이 파일은 그래프 "구조"만 정의한다. trace를 켜는 코드는
#   monitoring.py의 setup_langsmith_tracing()이 진입점(main.py/app.py)에서 한 번
#   호출하는 식으로 분리되어 있다 -- 환경변수만 켜져 있으면 아래 compile된 app을
#   invoke()할 때 각 노드 실행과 llm.invoke 호출이 코드 변경 없이 자동으로 LangSmith에
#   기록되므로, 그래프 정의 자체를 건드릴 필요가 없다.
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
