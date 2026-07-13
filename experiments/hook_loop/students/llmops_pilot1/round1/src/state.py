# source notebook: Step1. 상품리뷰분석 Agent 1.ipynb (cells 28, 30)
# split from the single-notebook original into logical modules (state/nodes/graph/db/main/app)
# -- content unchanged, only file boundaries added to match how the student's own section
# headers ("1) State & LLM 준비", "2) Agent 노드 준비", "3) 그래프 구성") already group the code.
from typing import TypedDict, Optional, Dict, Any, Literal

from langchain_openai import ChatOpenAI


class ReviewState(TypedDict):
    # 입력 리뷰
    review: str

    # 개별 에이전트 실행 결과
    analyzer_result: Optional[Dict[str, Any]]   # {"items":[{"aspect":..., "label":..., "evidence":...}]}
    critic_result:   Optional[Dict[str, Any]]   # {"verdict":"Conformity|Non-conformity", "reason":..., "reason_code":..., "repair_directive":...}

    # 흐름 제어
    retry_count: int
    max_retries: int
    next_agent:  Literal["analyzer", "critic", "end"]


llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
