# source notebook: Ch07. [Trace] 실행 관측 (Observability).ipynb

# --- cell 0 ---
# --- markdown ---
# # **[Trace] 실행 관측 (Observability)**

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
# [magic] !pip install -q langchain-openai langchain-community langsmith PyPDF2

# --- cell 9 ---
# --- markdown ---
# * 라이브러리 로딩

# --- cell 10 ---
import pandas as pd
import numpy as np
import os
import openai

from typing import TypedDict, Annotated, List, Optional, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph, MessagesState
from langchain_openai import ChatOpenAI

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
# ## **2. 무작정 따라하기**

# --- cell 15 ---
# --- markdown ---
# ### (1) 추적 환경 설정

# --- cell 16 ---
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_PROJECT"] = "test_proj1"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"

# --- cell 17 ---
# --- markdown ---
# ### (2) 실행

# --- cell 18 ---
llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
result = llm.invoke([HumanMessage(content="LangSmith에 대해서 간결하게 알려줘")])
print(result.content[:200])

# --- cell 19 ---
# --- markdown ---
# ## **3. Supervisor 패턴**

# --- cell 20 ---
# --- markdown ---
# ### (1) State & LLM

# --- cell 21 ---
NextStep = Literal["planner", "executor", "critic", "end"]

class AgentState(TypedDict):
    messages: Annotated[List, add_messages]

    plan: Optional[str]
    execution_result: Optional[str]
    critique: Optional[str]

    iteration: int
    max_iterations: int

    next_step: NextStep

    # 추가
    current_agent: Optional[str]

# --- cell 22 ---
llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.3)

# --- cell 23 ---
# --- markdown ---
# ### (2) Agent node

# --- cell 24 ---
# --- markdown ---
# * Planner

# --- cell 25 ---
def planner(state: AgentState):
    user_input = state["messages"][0].content
    prev_critique = state.get("critique" , "")  # 직전 평가

    # REJECTED 이유가 있으면, 다음 계획에 반영하도록 컨텍스트로 제공
    critique_hint = ""
    if prev_critique and ("REJECTED" in prev_critique):
        critique_hint = f"\n\n[이전 Critic 피드백]\n{prev_critique}\n"

    sys_msg = '''
    # 역할 : 너는 Planner.
    # 지침 : 사용자의 요청사항을 2 ~ 3개의 명확한 실행 단계로 분해.
    - 만약 이전 Critic 피드백(특히 REJECTED)이 있다면, 그 이유를 반영해 계획을 개선.
    - 출력은 '1) ... 2) ... 3) ...' 형식으로 간결히 작성.
    '''
    human_msg = f"[사용자 요청]\n{user_input} {critique_hint}"

    response = llm.invoke([SystemMessage(content=sys_msg),
                           HumanMessage(content=human_msg)])

    return {"messages": [response], "plan": response.content, "next_step": "executor",
            "current_agent": "planner"}

# --- cell 26 ---
# --- markdown ---
# * Executor

# --- cell 27 ---
def executor(state: AgentState):
    plan = state["plan"]
    sys_msg = '''
    # 역할 : 너는 Executor.
    # 지침 : 주어진 계획을 실행하고 최종 결과를 생성해.
    '''
    human_msg = f"# Plan:\n{plan}"

    response = llm.invoke([SystemMessage(content=sys_msg), HumanMessage(content=human_msg)])

    return {"messages": [response], "execution_result": response.content, "next_step": "critic",
            "current_agent": "executor"}

# --- cell 28 ---
# --- markdown ---
# * Critic

# --- cell 29 ---
def critic(state: AgentState):
    result = state["execution_result"]
    sys_msg = '''
    # 역할 : 너는 Critic.
    # 지침 : 결과의 정확성과 명확성을 평가해.
    - 평가 결과 : 반드시 다음 두가지 중 하나 선택. APPROVED | REJECTED
    APPROVED는 충분히 적절하고 개선이 필요 없을 때만 사용.
    조금이라도 부족하면 REJECTED로 판단.
    - 평가 이유 : 평가 결과를 선정한 이유를 간결한 한문장으로 기술.
    '''
    human_msg = f"# Result:\n{result}"

    response = llm.invoke([SystemMessage(content=sys_msg), HumanMessage(content=human_msg)])

    return {"messages": [response], "critique": response.content, "next_step": "supervisor",
            "iteration": state.get("iteration", 0) + 1, "current_agent": "critic"}

# --- cell 30 ---
# --- markdown ---
# * Supervisor

# --- cell 31 ---
def supervisor(state: AgentState):

    critique = state.get("critique", "")
    iteration = state.get("iteration", 0)
    max_it = state.get("max_iterations", 3)

    if not state.get("plan"):
        return {"next_step": "planner", "current_agent": "supervisor"}

    if not state.get("execution_result"):
        return {"next_step": "executor", "current_agent": "supervisor"}

    critique = state.get("critique")
    if critique is None:
        return {"next_step": "critic", "current_agent": "supervisor"}

    if "APPROVED" in critique:
        return {"next_step": "end", "current_agent": "supervisor"}

    return {
        "iteration": state.get("iteration", 0) + 1,
        "execution_result": None,
        "critique": None,
        "next_step": "executor",
        "current_agent": "supervisor"
    }

# --- cell 32 ---
# --- markdown ---
# ### (3) Graph

# --- cell 33 ---
# --- markdown ---
# * 조건부 함수

# --- cell 34 ---
def route(state: AgentState):
    return state["next_step"]

# --- cell 35 ---
# --- markdown ---
# * 그래프

# --- cell 36 ---
workflow = StateGraph(AgentState)

workflow.add_node("planner", planner)
workflow.add_node("executor", executor)
workflow.add_node("critic", critic)
workflow.add_node("supervisor", supervisor)

workflow.add_edge(START, "supervisor")
workflow.add_edge("planner", "supervisor")
workflow.add_edge("executor", "supervisor")
workflow.add_edge("critic", "supervisor")

workflow.add_conditional_edges("supervisor", route,
    {"planner": "planner", "executor": "executor",
        "critic": "critic", "end": END  }
)

graph = workflow.compile()

# --- cell 37 ---
graph

# --- cell 38 ---
# --- markdown ---
# ### (4) 실행 및 추적

# --- cell 39 ---
input_text = "친환경 물병 출시 전략을 McKinsey 컨설팅 수준으로 작성하되, 3줄 이내로 요약해라."
initial_state: AgentState = {"messages": [HumanMessage(content=input_text)]}

# --- cell 40 ---
result = graph.invoke(initial_state)

for msg in result["messages"]:
    print(msg.content)

# --- cell 41 ---
# --- markdown ---
# * 코드 실행 후 langsmith의 추적 결과를 살펴봅시다.

# --- cell 42 ---
# --- markdown ---
# ## **4. 도구 사용 Agent**

# --- cell 43 ---
# [magic] !pip install -q wikipedia arxiv

# --- cell 44 ---
from langchain_community.utilities import WikipediaAPIWrapper, ArxivAPIWrapper
from langchain_community.tools import WikipediaQueryRun, ArxivQueryRun
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

# --- cell 45 ---
# --- markdown ---
# ### (1) State & LLM

# --- cell 46 ---
# --- markdown ---
# * State

# --- cell 47 ---
class State(TypedDict):
    messages: Annotated[list, add_messages]

# --- cell 48 ---
# --- markdown ---
# * LLM 준비

# --- cell 49 ---
llm = ChatOpenAI(model="gpt-4.1-mini")

# --- cell 50 ---
# --- markdown ---
# ### (2) 도구 준비

# --- cell 51 ---
# --- markdown ---
# * 도구 준비 및 도구 리스트 만들기

# --- cell 52 ---
# 위키피디아
wiki_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())

# Arxiv(논문 검색)
arxiv_tool = ArxivQueryRun(api_wrapper=ArxivAPIWrapper())

# 통합 리스트 만들기
tools = [wiki_tool, arxiv_tool]

# --- cell 53 ---
# --- markdown ---
# 
# * ToolNode 생성

# --- cell 54 ---
tool_node = ToolNode(tools)

# --- cell 55 ---
llm_with_tools = llm.bind_tools(tools)

# --- cell 56 ---
# --- markdown ---
# ### (3) Graph

# --- cell 57 ---
# --- markdown ---
# * Node 와 분기 함수(conditional edge를 위한 함수)

# --- cell 58 ---
# 모델 호출 함수 (GPT 호출)
def call_model(state: State):
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# 조건 분기 함수: 툴 호출이 필요한가?
def should_continue(state: State) -> Literal["tools", END]:  # 출력은 반드시 "tools" 혹은 END 여야 함.
    messages = state["messages"]
    last_message = messages[-1]  # 가장 최근 message
    if last_message.tool_calls:
        return "tools"
    return END

# --- cell 59 ---
# --- markdown ---
# * 그래프 구성

# --- cell 60 ---
builder = StateGraph(State)

# 노드 추가
builder.add_node("call_model", call_model)
builder.add_node("tools", tool_node)

# 연결
builder.set_entry_point("call_model")
builder.add_conditional_edges("call_model", should_continue)
builder.add_edge("tools", "call_model")  # 루프 연결

# 컴파일
graph = builder.compile()

# --- cell 61 ---
graph

# --- cell 62 ---
# --- markdown ---
# ### (4) 실행 및 추적

# --- cell 63 ---
# --- markdown ---
# ### ※ 주의wikipidia 사용 시, 사용자가 몰리면 접속을 제한할 수 있습니다.(접속 제한으로 인한 오류 발생)
# - 그럴 경우, 잠시 후에 다시 시도하면 정상 작동하게 됩니다.

# --- cell 64 ---
result = graph.invoke({
    "messages": [HumanMessage(content="가장 인용수가 많은 LLM 논문이 뭐야?")]
})

# 출력
for message in result["messages"]:
    message.pretty_print()

# --- cell 66 ---
# --- markdown ---
# ## **5. 실습 : Network 패턴 실행 관측**
# 
# * Network 패턴 (기본 코드 제공)
#     * 고객의 요청사항에 대해
#     * 접수, 환불지원, 기술지원을 수행
#     * 환불지원, 기술지원 업무 상담 이력을 요약
#     * 필요시, 기본 코드를 조금 수정/보완
# * 실행한 후 추적 결과를 Langsmith에서 관찰하기

# --- cell 67 ---
# --- markdown ---
# ![image.png]([image data omitted])

# --- cell 68 ---
# --- markdown ---
# ### (1) State & LLM

# --- cell 69 ---
NextAgent = Literal["triage", "tech_support", "refund_support", "close"]

class HandoffState(TypedDict):
    messages: Annotated[List, add_messages]
    next_agent: NextAgent
    hop_count: int
    max_hops: int
    support_turn_count: int   # triage 제외, support 계열만 카운트
    history_summary: str      # 상담 요약

# --- cell 70 ---
llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.2)

# --- cell 71 ---
# --- markdown ---
# ### (2) Agent node

# --- cell 72 ---
# --- markdown ---
# * 공통 유틸

# --- cell 73 ---
def _first_line(text: str) -> str:
    lines = (text or "").strip().splitlines()
    return lines[0].strip() if lines else ""

def _guard(state: HandoffState) -> bool:
    return state.get("hop_count", 0) >= state.get("max_hops", 10)

def _normalize_agent(text: str) -> NextAgent:
    value = _first_line(text).strip("'\"").lower()
    if value not in {"triage", "tech_support", "refund_support", "close"}:
        return "close"
    return value

# --- cell 74 ---
# --- markdown ---
# * Agent 준비

# --- cell 75 ---
# 요약함수

def update_summary(old_summary: str, messages: List) -> str:
    sys_msg = """
# 역할
너는 고객센터 상담 이력을 요약하는 요약 담당자다.

# 지침
- 기존 요약과 최근 대화를 참고하여 상담 핵심 내용을 2~3문장으로 요약하라.
- 현재까지의 주요 문제, 처리 내용, 남아 있는 이슈를 포함하라.
- 불필요한 세부 문장은 줄이고 핵심만 남겨라.
"""

    human_msg = f'''
    [기존 요약]\n{old_summary}
    [최근 대화]\n{messages[-4:]}
    '''

    resp = llm.invoke([SystemMessage(content=sys_msg),
                       HumanMessage(content=human_msg)])

    return resp.content

# --- cell 76 ---
# triage : 요약하지 않음. 기존 내용과 동일

def triage_agent(state: HandoffState):
    print("--- [Triage] 접수 데스크입니다. ---")

    if _guard(state):
        return {
            "messages": [AIMessage(content="상담 가능 횟수를 초과하여 종료합니다.")],
            "next_agent": "close",
            "hop_count": state["hop_count"] + 1,
        }

    sys_msg = """
# 역할
너는 고객센터 접수 담당자다.

# 지침
- 직접 문제를 해결하지 말고 다음 담당자 중 한 명으로 연결하라.
- 기술적 문제(에러, 고장, 설치, 접속 등) -> tech_support
- 결제/취소/환불 등 금전 문제 -> refund_support
- 단순 인사, 종료 요청, 더 이상 처리할 내용이 없음 -> close

# 출력 형식
첫 줄: tech_support 또는 refund_support 또는 close 중 하나만 출력
"""

    resp = llm.invoke([SystemMessage(content=sys_msg)] + state["messages"])
    next_dest = _normalize_agent(resp.content)

    print(f"[Triage] 판단: {next_dest}")
    return {"next_agent": next_dest, "hop_count": state["hop_count"] + 1}

# --- cell 77 ---
# 2번째 support 실행부터 요약

def tech_support(state: HandoffState):
    print("--- [Tech] 기술 지원 팀입니다. ---")

    if _guard(state):
        return {
            "messages": [AIMessage(content="처리 횟수 제한으로 상담을 종료합니다.")],
            "next_agent": "close",
            "hop_count": state["hop_count"] + 1,
        }

    sys_msg = f"""
# 역할
너는 기술 지원 전문가다.

# 현재 상담 요약
{state.get("history_summary", "")}

# 지침
- 사용자의 기술적 문제에 대해 해결 가이드 또는 점검 방법을 안내하라.
- 답변 후 현재 상황을 기준으로 다음 담당자를 판단하라.
- 환불, 결제, 취소 이슈가 핵심으로 드러나면 첫 줄에 refund_support 를 출력하라.
- 기술 문제 해결을 위해 반드시 사용자의 추가 답변이나 확인이 필요하면 첫 줄에 close 를 출력하라.
- 기술 문제가 아직 해결되지 않았다고 판단되면 첫 줄에 tech_support 를 출력하라.
- 문제 해결이 완료되었으면 첫 줄에 close 를 출력하라.

# 출력 형식
첫 줄: tech_support 또는 refund_support 또는 close 중 하나만 출력
둘째 줄 이하: 사용자에게 보여줄 답변
"""

    resp = llm.invoke([SystemMessage(content=sys_msg)] + state["messages"])
    next_dest = _normalize_agent(resp.content)

    new_support_count = state.get("support_turn_count", 0) + 1

    # support 2회차 이상부터 요약
    if new_support_count >= 2:
        new_summary = update_summary(
            state.get("history_summary", ""),
            state["messages"] + [resp]
        )
    else:
        new_summary = state.get("history_summary", "")

    print(f"[Tech] 다음 경로: {next_dest}")
    print(f"[Tech] support_turn_count: {new_support_count}")

    return {
        "messages": [resp],
        "next_agent": next_dest,
        "hop_count": state["hop_count"] + 1,
        "support_turn_count": new_support_count,
        "history_summary": new_summary,
    }

# --- cell 78 ---
def refund_support(state: HandoffState):
    print("--- [Refund] 환불 지원 팀입니다. ---")

    if _guard(state):
        return {
            "messages": [AIMessage(content="처리 횟수 제한으로 상담을 종료합니다.")],
            "next_agent": "close",
            "hop_count": state["hop_count"] + 1,
        }

    sys_msg = f"""
# 역할
너는 환불/결제/취소 지원 전문가다.

# 현재 상담 요약
{state.get("history_summary", "")}

# 지침
- 사용자의 환불, 결제, 취소 관련 문제를 안내하라.
- 기술적 이슈가 핵심이면 첫 줄에 tech_support 를 출력하라.
- 추가 환불 상담이 더 필요하면 첫 줄에 refund_support 를 출력하라.
- 상담이 완료되었거나 사용자의 추가 응답이 필요하면 첫 줄에 close 를 출력하라.

# 출력 형식
첫 줄: tech_support 또는 refund_support 또는 close 중 하나만 출력
둘째 줄 이하: 사용자에게 보여줄 답변
"""

    resp = llm.invoke([SystemMessage(content=sys_msg)] + state["messages"])
    next_dest = _normalize_agent(resp.content)

    new_support_count = state.get("support_turn_count", 0) + 1

    # support 2회차 이상부터 요약
    if new_support_count >= 2:
        new_summary = update_summary(
            state.get("history_summary", ""),
            state["messages"] + [resp]
        )
    else:
        new_summary = state.get("history_summary", "")

    print(f"[Refund] 다음 경로: {next_dest}")
    print(f"[Refund] support_turn_count: {new_support_count}")

    return {
        "messages": [resp],
        "next_agent": next_dest,
        "hop_count": state["hop_count"] + 1,
        "support_turn_count": new_support_count,
        "history_summary": new_summary,
    }

# --- cell 79 ---
# --- markdown ---
# ### (3) Graph

# --- cell 80 ---
# 분기함수
def route_handoff(state: HandoffState) -> Literal["triage", "tech_support", "refund_support", "__end__"]:
    next_agent = state.get("next_agent")

    if next_agent in {"triage", "tech_support", "refund_support"}:
        return next_agent

    return END

# --- cell 81 ---
workflow = StateGraph(HandoffState)
workflow.add_node("triage", triage_agent)
workflow.add_node("tech_support", tech_support)
workflow.add_node("refund_support", refund_support)

workflow.add_edge(START, "triage")
workflow.add_conditional_edges("triage", route_handoff)
workflow.add_conditional_edges("tech_support", route_handoff)
workflow.add_conditional_edges("refund_support", route_handoff)
graph = workflow.compile()

# --- cell 82 ---
graph

# --- cell 83 ---
# --- markdown ---
# ### (4) 실행 및 추적
# * 실행후 Langsmith에서 추적 결과를 살펴봅시다.

# --- cell 84 ---
input_text = "앱 설치하는데 몇몇 오류가 발생했습니다. 겨우 설치했는데, 결제도 문제가 있어요. 취소 해주세요."
initial = {"messages": [HumanMessage(content=input_text)],
           "next_agent": "triage", "hop_count": 0, "max_hops": 3}
result = graph.invoke(initial)
for i, msg in enumerate(result["messages"], 1):
    print(f"[{i}] : {msg.content}")
    print("-" * 50)
