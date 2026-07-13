# source notebook: Step1. 상품리뷰분석 Agent 1.ipynb (cells 28, 30)
# split from the single-notebook original into logical modules (state/nodes/graph/db/main/app)
# -- content unchanged, only file boundaries added to match how the student's own section
# headers ("1) State & LLM 준비", "2) Agent 노드 준비", "3) 그래프 구성") already group the code.
#
# ── Agent 아키텍처 요약 (Step1 리뷰 피드백 반영: planner->executor->critic 흐름의 역할을
#    각 파일 상단에 명확히 남긴다) ──────────────────────────────────────────────
#   supervisor_node(nodes.py) = Planner/Router : 작업을 직접 하지 않고 다음 행선지와
#     재시도 여부만 결정한다.
#   analyzer_node  (nodes.py) = Executor        : 리뷰에서 속성별 감성을 추출한다.
#   critic_node    (nodes.py) = Critic          : analyzer 결과를 검증하고 reason_code를 매긴다.
#   아래 ReviewState는 이 세 노드가 공유하는 단일 데이터 계약이다. v2.0에서도 이 모듈이
#   유일한 정의처이고, app.py를 포함한 모든 파일이 여기서 import해서 쓴다(중복 정의 없음).
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
