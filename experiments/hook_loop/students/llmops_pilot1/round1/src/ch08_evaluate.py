# source notebook: Ch08. [Evaluate] Agent 시스템 평가.ipynb

# --- cell 0 ---
# --- markdown ---
# # **[Evaluate] Agent 시스템 평가**

# --- cell 1 ---
# --- markdown ---
# ## **1. 환경준비**

# --- cell 2 ---
# --- markdown ---
# ### (1) 구글 드라이브

# --- cell 3 ---
# --- markdown ---
# * 구글 드라이브 폴더 생성
#     * 새 폴더 `ai_agent`를 생성(이미 만들었다면 skip)
#     * 제공 받은 파일을 업로드

# --- cell 4 ---
# --- markdown ---
# * 구글 드라이브 연결

# --- cell 5 ---
from google.colab import drive
drive.mount('/content/drive')

# --- cell 6 ---
# --- markdown ---
# ### (2) 라이브러리

# --- cell 7 ---
# --- markdown ---
# * 필요한 라이브러리 설치

# --- cell 8 ---
# [magic] !pip install -q langchain-openai langchain-community

# --- cell 9 ---
# --- markdown ---
# * 라이브러리 로딩

# --- cell 10 ---
import pandas as pd
import numpy as np
import os
import openai
import ast

from typing import TypedDict, Annotated, List, Optional, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph, MessagesState
from langchain_openai import ChatOpenAI

from langsmith.evaluation import evaluate

# --- cell 11 ---
# --- markdown ---
# ### (3) OpenAI API Key 확인

# --- cell 12 ---
def load_api_keys(filepath="api_key.txt"):
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

path = '/content/drive/MyDrive/ai_agent/'

# API 키 로드 및 환경변수 설정
load_api_keys(path + 'api_key.txt')

# --- cell 13 ---
print(os.environ['OPENAI_API_KEY'][:30])
print(os.environ['LANGSMITH_API_KEY'][:30])

# --- cell 14 ---
# --- markdown ---
# ## **2. Agent 평가**

# --- cell 15 ---
# --- markdown ---
# ### (1) Agent 준비

# --- cell 16 ---
# --- markdown ---
# * 환경 설정

# --- cell 17 ---
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_PROJECT"] = "test_proj1"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"

# --- cell 18 ---
# --- markdown ---
# * State 준비

# --- cell 19 ---
class State(TypedDict):
    messages: Annotated[list, add_messages]

# --- cell 20 ---
# --- markdown ---
# * LLM 준비

# --- cell 21 ---
llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.9)

# --- cell 22 ---
# --- markdown ---
# * Node 준비

# --- cell 23 ---
def movie_recommender(state: State):
    sys_msg = """
# 역할 : 너는 영화 추천 큐레이터.

# 지침
- 사용자가 말한 오늘 기분에 맞춰 영화 2편을 추천해.
- 출력 형식 : 반드시 리스트 안의 딕셔너리 형태로 출력해.
[
  {"rank": 1, "title": "영화 제목", "reason": "추천 이유"},
  {"rank": 2, "title": "영화 제목", "reason": "추천 이유"}
]

- 항목은 정확히 2개
- rank 는 1, 2
- title, reason 은 비어 있으면 안 됨
- 리스트 외의 설명, 마크다운, 코드블록 출력 금지
"""
    messages = [SystemMessage(content=sys_msg)] + state["messages"]
    result = llm.invoke(messages)
    return {"messages": [result]}

# --- cell 24 ---
# --- markdown ---
# * 그래프

# --- cell 25 ---
builder = StateGraph(State)
builder.add_node("movie_recommender", movie_recommender)
builder.set_entry_point("movie_recommender")
builder.set_finish_point("movie_recommender")
graph = builder.compile()

# --- cell 26 ---
graph

# --- cell 27 ---
# --- markdown ---
# ### (2) Trace

# --- cell 28 ---
# --- markdown ---
# * agent 실행

# --- cell 29 ---
input_text = "오늘 하루종일 일하느라 피곤해.스트레스가 심하고 예민해. 좀 진정되고 싶어."
out = graph.invoke({"messages": [HumanMessage(content=input_text)]})

print(out["messages"][-1].content)

# --- cell 30 ---
# --- markdown ---
# ### (3) 실행
# * 방금 생성한 Agent를 5번 실행하면서 결과가 적절한 구조로 나오는지 확인해 봅시다.
#     * 단 입력 텍스트를 수정해서 다양한 입력에 다양한 결과가 나오도록 합니다.

# --- cell 31 ---
input_text = "역사적 배경이지만 픽션인 영화"
out = graph.invoke({"messages": [HumanMessage(content=input_text)]})

print(out["messages"][-1].content)

# --- cell 33 ---
# --- markdown ---
# ### (4) 평가1 : 테스트 데이터셋으로 평가
# * 데이터 : 테스트 데이터셋 구성
# * 평가 : [Colab]평가 함수 코드 실행
# * 결과 확인 : [LangSmith] 대시보드
# 
# 

# --- cell 34 ---
# --- markdown ---
# * 평가 함수 준비

# --- cell 35 ---
def _list_score_and_reason(text: str):
    try:                                    # 결과가 파이썬 자료형?
        data = ast.literal_eval(text)
    except Exception as e:
        return 0, f"parse error: {e}"

    if not isinstance(data, list):    # recommendations 리스트 확인
        return 0, "recommendations must be a list"

    if len(data) != 2:        # recommendations 2개 확인
        return 0, f"expected 2 recommendations, got {len(data)}"

    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):  # recommendations의 항목 dict 형식 확인
            return 0, f"item {i} is not an object"

        if item.get("rank") != i:       # recommendations 순번(rank)과 인덱스 비교
            return 0, f"item {i} rank must be {i}"

        title = item.get("title")
        reason = item.get("reason")

        if not isinstance(title, str) or not title.strip(): # title 문자열 확인
            return 0, f"item {i} title invalid"

        if not isinstance(reason, str) or not reason.strip():
            return 0, f"item {i} reason invalid"

    return 1, "pass"

# --- cell 36 ---
def perform_eval(run, example):  # example : 데이터셋 기반 평가시 필요
    msg = run.outputs["messages"][-1]   # langsmith의 runtree obejct로 처리됨.
    text = msg.content

    score, reason = _list_score_and_reason(text)   # 규칙 평가 함수
    return {"key": "format", "score": score, "comment": reason}

# --- cell 37 ---
# --- markdown ---
# * 등록한 데이터셋으로 평가해보기

# --- cell 38 ---
from langsmith.evaluation import evaluate

# 실행 함수
def target_fn(inputs):
    out = graph.invoke({
        "messages": [HumanMessage(content=inputs["messages"][0]["content"])]
    })
    return out

# LangSmith 평가 실행
experiment = evaluate(
    target_fn,
    data="test_set",  # 등록된 데이터셋 이름
    evaluators=[perform_eval],   # 평가 함수
    experiment_prefix="movie-format-test"
)

# --- cell 39 ---
# --- markdown ---
# ### (5) 평가2 : Agent 실행 추적 시 평가 수행
# * 평가 : [LangSmith] Evaluator  등록
# * 결과 확인 : [LangSmith] 추적 결과, 대시보드

# --- cell 40 ---
# --- markdown ---
# * 평가 : [LangSmith] Evaluator  등록
#     * LangSmith에서, New Evaluator로 아래 코드를 custom code로 등록하기

# --- cell 41 ---
import ast

def _list_score_and_reason(text: str):
    try:                                    # 결과가 파이썬 자료형?
        data = ast.literal_eval(text)
    except Exception as e:
        return 0, f"parse error: {e}"

    if not isinstance(data, list):    # 리스트 확인
        return 0, "recommendations must be a list"

    if len(data) != 2:        # 추천영화 2개 확인
        return 0, f"expected 2 recommendations, got {len(data)}"

    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):  # 각 항목 dict 형식 확인
            return 0, f"item {i} is not an object"

        r = item.get("rank")
        if r != i:       # 추천영화 순번(rank)과 인덱스 비교
            return 0, f"item {r} rank must be {i}"

        title = item.get("title")
        reason = item.get("reason")

        if not isinstance(title, str) or not title.strip(): # title 문자열 확인
            return 0, f"item {i} title invalid"

        if not isinstance(reason, str) or not reason.strip():
            return 0, f"item {i} reason invalid"

    return 1, "pass"

def perform_eval(run):   # 실행에 대한 평가이므로 run만 필요.
    msg = run["outputs"]["messages"][-1]  # dict로 처리됨.
    text = msg.get("content")

    score, reason = _list_score_and_reason(text)   # 규칙 평가 함수
    return {"key": "format", "score": score, "comment": f"{reason} : {msg}"}

# --- cell 42 ---
# --- markdown ---
# * 추적 및 평가 테스트

# --- cell 43 ---
input_text = "하루종일 스트레스를 받았더니 머리가 너무 복잡해"
out = graph.invoke({"messages": [HumanMessage(content=input_text)]})

print(out["messages"][-1].content)

# --- cell 44 ---
text = out["messages"][-1].content
_list_score_and_reason(text)

# --- cell 45 ---
# --- markdown ---
# ## **3. 실습**
# 
# * 보고서 생성 Agent
#     * 사용자 요구사항을 받아 요건에 맞게 보고서를 작성하는 Agent
#         * ① 요청사항과 주제(topic), outline 입력
#         * ② 지침에 맞게 보고서 초안 생성
#         * ③ 검토(적합/부적합 판정)
#         * ④ 부적합일 경우 ② 단계로 이동 / 적합일 경우, 종료
# 
#     * 구현 및 평가
#         * 간단한 AI Agent 생성(LangGraph)
#         * Agent 실행(LangGraph)
#         * 실행 추적(LangSmith)
#         * 실행 결과 평가(LangSmith) : LLM-AS-JUDGE

# --- cell 46 ---
# --- markdown ---
# ![image.png]([image data omitted])

# --- cell 47 ---
# --- markdown ---
# ### (1) 환경준비
# * [중요!] 세션 다시 시작

# --- cell 48 ---
import pandas as pd
import numpy as np
import os
import openai
import ast

from typing import TypedDict, Annotated, List, Optional, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph, MessagesState
from langchain_openai import ChatOpenAI

from langsmith.evaluation import evaluate

# --- cell 49 ---
def load_api_keys(filepath="api_key.txt"):
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

path = '/content/drive/MyDrive/ai_agent/'

# API 키 로드 및 환경변수 설정
load_api_keys(path + 'api_key.txt')

# --- cell 50 ---
print(os.environ['OPENAI_API_KEY'][:30])
print(os.environ['LANGSMITH_API_KEY'][:30])

# --- cell 51 ---
# --- markdown ---
# ### (2) Trace

# --- cell 52 ---
# --- markdown ---
# * 환경 설정

# --- cell 53 ---
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_PROJECT"] = "test_proj2"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"

# --- cell 54 ---
# --- markdown ---
# ### (3) Agent 준비

# --- cell 55 ---
# --- markdown ---
# #### 1) State & LLM

# --- cell 56 ---
class ReportState(TypedDict):
    messages: Annotated[List, add_messages]      # 대화/로그 누적
    topic: str                                   # 보고서 주제
    outline: Optional[str]                       # (선택) 개요
    draft: Optional[str]                         # 초안
    review: Optional[str]                        # 리뷰(피드백/점수/OK 여부 포함)
    final: Optional[str]                         # 최종본
    revision_count: int                          # 수정 횟수
    max_revisions: int                           # 최대 수정 허용
    next_step: Optional[Literal["draft", "review", "revise", "final"]]  # supervisor가 결정

# --- cell 57 ---
llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.2)

# --- cell 58 ---
# --- markdown ---
# #### 2) Agent node 준비

# --- cell 59 ---
# --- markdown ---
# * Worker Agents

# --- cell 60 ---
def draft_agent(state: ReportState) -> dict:
    print("\n[STEP] Draft Agent 실행")
    topic = state["topic"]
    outline = state.get("outline") or ""

    sys_msg = '''
    # 역할 : 너는 전문 리포트 작성자야.
    # 형식: 제목/요약/본문(소제목)/결론/권고사항.
    # 작성 지침
    - 주제에 대한 1페이지 분량의 간결한 보고서 초안을 작성해.
    - 초안의 주요 항목에 대해서 근거를 일반적 사실 수준에서 논리적으로 제시해(출처 URL은 쓰지 마).
    '''
    human_msg = f"주제: {topic}\n개요(있으면 참고):\n{outline}"

    resp = llm.invoke([SystemMessage(content=sys_msg),
                       HumanMessage(content=human_msg)])

    return {"draft": resp.content,
            "messages": [AIMessage(content=f"[DRAFT]\n{resp.content}")]}

# --- cell 61 ---
def review_agent(state: ReportState) -> dict:
    print("\n[STEP] Critic Agent 실행")
    topic = state["topic"]
    draft = state.get("draft") or ""

    sys_msg = '''
    # 역할 : 너는 보고서 검토자. 칭찬/점수 매기지 말고 문제점만 찾아.
    # 검토 지침 : 아래 중 하나라도 해당하면 반드시 REVISE:
    - 실행 주체/책임이 모호함
    - 리스크는 있으나 대응 시나리오가 없음
    - 지나치게 일반론(교과서 표현) 위주
    - 의사결정자 관점의 쟁점/질문을 다루지 않음
    - 실패 가능성/조직 저항/책임 이슈를 과소평가
    # 출력 형식(엄수):
    [문제점]
    - ...
    [수정 지시]
    - ... (3~7개)
    [판정]
    VERDICT: OK 또는 VERDICT: REVISE
    (문제점이 1개라도 있으면 VERDICT: REVISE)
    '''
    human_msg = f"[주제]\n{topic}\n\n[초안]\n{draft}"

    resp = llm.invoke([SystemMessage(content=sys_msg),
                       HumanMessage(content=human_msg)])

    return {"review": resp.content,
            "messages": [AIMessage(content=f"[REVIEW]\n{resp.content}")]}

# --- cell 62 ---
def revise_agent(state: ReportState) -> dict:
    print("\n[STEP] Revise Agent 실행")

    draft = state.get("draft") or ""
    review = state.get("review") or ""

    sys_msg = '''
    # 역할 : 너는 보고서 편집자다. 리뷰의 [수정 지시]를 최우선으로 반영해 초안을 실무 제출 가능 수준으로 재작성해.
    # 편집 규칙:
    - 리뷰의 [문제점]/[수정 지시]를 모두 해결(누락 금지)
    - 실행 주체/책임/절차가 모호한 문장은 구체화
    - 리스크에는 대응 시나리오(예: 예방/탐지/대응/복구 중 택1) 추가
    - 결과는 개선된 초안만 출력
    - 전체적으로 간결한 보고서가 되도록 편집
    '''
    human_msg = f"[초안]\n{draft}\n\n[리뷰]\n{review}"

    resp = llm.invoke([SystemMessage(content=sys_msg),
                       HumanMessage(content=human_msg)])

    return {"draft": resp.content,
            "revision_count": state["revision_count"] + 1,
            "messages": [AIMessage(content=f"[REVISED DRAFT]\n{resp.content}")]}

# --- cell 63 ---
def final_agent(state: ReportState) -> dict:
    # 최종본은 draft를 그대로 쓰거나, 포맷팅을 한 번 더 할 수도 있음
    print("\n[STEP] Final Agent 실행")
    draft = state.get("draft") or ""
    sys_msg = '''
    # 역할 : 너는 최종 편집자야. 아래 초안을 최종본으로 다듬어.
    # 편집 지침 :
    - 어색한 문장 다듬기
    - 섹션 헤더 정리
    - 핵심 권고사항을 마지막에 3개로 요약
    - 전체적으로 간결한 보고서가 되도록 최종본 작성
    '''
    human_msg = f"[초안]\n{draft}"

    resp = llm.invoke([SystemMessage(content=sys_msg),
                       HumanMessage(content=human_msg)])

    return {"final": resp.content,
            "messages": [AIMessage(content=f"[FINAL]\n{resp.content}")]}

# --- cell 64 ---
# --- markdown ---
# * Supervisor(Orchestrator)

# --- cell 65 ---
def supervisor(state: ReportState) -> dict:
    print("\n[STEP] Supervisor 실행")

    draft = state.get("draft")
    review = state.get("review")
    rev_n = state["revision_count"]
    max_rev = state["max_revisions"]

    # 1) 초안이 없으면 Draft부터
    if not draft:
        return {"next_step": "draft"}
    # 2) 초안은 있으나 리뷰가 없으면 Review
    elif not review:
        return {"next_step": "review"}
    else:
        verdict_line = (
            review.strip().splitlines()[-1] if review.strip() else ""
        ).upper()
        # 3) 리뷰 통과 → Final
        if "VERDICT: OK" in verdict_line:
            return {"next_step": "final"}
        # 4) 수정 필요하지만, 최대 수정 횟수 초과 → Final(강제 종료)
        elif rev_n >= max_rev:
            return {"next_step": "final"}
        # 5) 수정 필요 → Revise
        else:
            return {"next_step": "revise"}

# --- cell 66 ---
# --- markdown ---
# * route_next 함수

# --- cell 67 ---
def route_next(state: ReportState) -> str:
    return state["next_step"] or "draft"

# --- cell 68 ---
# --- markdown ---
# #### 3) 그래프

# --- cell 69 ---
builder = StateGraph(ReportState)

builder.add_node("supervisor", supervisor)
builder.add_node("draft", draft_agent)
builder.add_node("review", review_agent)
builder.add_node("revise", revise_agent)
builder.add_node("final", final_agent)

builder.add_edge(START, "supervisor")
builder.add_conditional_edges("supervisor", route_next,
    {"draft": "draft", "review": "review",
     "revise": "revise", "final": "final"},
)

builder.add_edge("draft", "supervisor")
builder.add_edge("review", "supervisor")
builder.add_edge("revise", "supervisor")
builder.add_edge("final", END)

graph = builder.compile()

# --- cell 70 ---
graph

# --- cell 71 ---
# --- markdown ---
# ### (4) 실행 및 평가
# * LLM-AS-JUDGE 평가 지표 추가
# * 예제 코드 실행하여 추적 및 평가 결과 확인

# --- cell 72 ---
# --- markdown ---
# #### LLM-AS-JUDGE Evaluator 생성
# * 다음 양식에 맞게 시스템 프롬프트 완성합니다.
# * langsmith의 test_proj2 에 LLM-AS-JUDGE Evaluator 생성하기

# --- cell 73 ---
# --- markdown ---
#         당신은 생성된 보고서의 실무 품질을 평가하는 전문가입니다.
# 
#         <Rubric>
#         좋은 보고서는 다음을 만족해야 합니다.
#         - 주제에 맞는 핵심 내용을 명확하게 다룬다.
#         - 실행 주체, 책임, 절차가 구체적이다.
#         - 리스크와 대응 방안이 현실적으로 제시된다.
#         - 단순 일반론이 아니라 실제 의사결정에 도움이 된다.
#         - 전체적으로 논리적이고 설득력이 있다.
# 
#         다음과 같은 경우 낮게 평가합니다.
#         - 추상적이고 교과서적인 내용 위주인 경우
#         - 실행 방안이 불명확한 경우
#         - 리스크 또는 대응 전략이 부족한 경우
#         - 의사결정 관점에서 중요한 쟁점을 다루지 않은 경우
#         </Rubric>
# 
#         <Instructions>
#         평가 지침
#         - 주제와 보고서를 함께 읽고 내용의 적절성을 평가하시오.
#         - 보고서가 실제 업무에 활용 가능한 수준인지 판단하시오.
#         - 실행 가능성, 구체성, 설득력을 중심으로 평가하시오.
#         - 형식이 아니라 내용 품질에 집중하시오.
#         </Instructions>
# 
#         <Reminder>
#         알림
#         - 목표는 “읽고 바로 의사결정에 활용 가능한 보고서”를 높게 평가하는 것입니다.
#         - 엄격하지만 공정하게 평가하십시오.
#         </Reminder>

# --- cell 74 ---
# --- markdown ---
# #### 실행 및 평가 결과 확인
# * 다음 코드를 수정해서 실행하고, langsmith에서 결과를 확인해 봅시다.

# --- cell 75 ---
initial_state: ReportState = {
    "messages": [HumanMessage(content="공공기관 대상 보고서 작성 시작")],
    "topic": "공공기관에서 생성형 AI 도입 시 기대 효과와 주요 리스크, 그리고 단계적 도입 전략",
    "outline": '''
1. 생성형 AI 개요 및 공공기관 활용 맥락
2. 기대 효과
3. 주요 리스크
4. 단계적 도입 전략
5. 결론 및 정책적 시사점
''',
    "draft": None,
    "review": None,
    "final": None,
    "revision_count": 0,
    "max_revisions": 1,
    "next_step": None
}

result = graph.invoke(initial_state)

print("\n==== FINAL OUTPUT ====\n")
print(result["final"])
print("\n---- revisions ----")
print(result["revision_count"])
