# source notebook: Step1. 상품리뷰분석 Agent 1.ipynb (cell 52, %%writefile app.py)
# NOTE: the student wrote this Streamlit file's agent/state/graph definitions inline
# instead of importing them from the notebook's own earlier cells (see state.py/nodes.py/
# agent_graph.py in this same directory) -- analyzer_node/critic_node/supervisor_node/ReviewState
# below are near-verbatim duplicates of those files, not shared imports. Preserved as-is.
import streamlit as st
import sqlite3
import json
import re
import os
import pandas as pd
from typing import TypedDict, Optional, Dict, Any, Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

# ── 기본 설정 ──────────────────────────────────────────────
DB_PATH = "/content/drive/MyDrive/proj2_agent/reviews.db"
st.set_page_config(page_title="상품 리뷰 분석 Agent", layout="wide")

def _load_api_keys(filepath="/content/drive/MyDrive/proj2_agent/api_key.txt"):
    try:
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()
    except FileNotFoundError:
        pass

_load_api_keys()

# ==================================================
# 1. Agent
# ==================================================
# State 준비
class ReviewState(TypedDict):
    review:          str
    analyzer_result: Optional[Dict[str, Any]]
    critic_result:   Optional[Dict[str, Any]]
    retry_count:     int
    max_retries:     int
    next_agent:      Literal["analyzer", "critic", "end"]

# LLM 준비
@st.cache_resource
def get_llm():
    return ChatOpenAI(model="gpt-4.1-mini", temperature=0)

# 노드1 : analyzer_node
def analyzer_node(state: ReviewState):
    llm    = get_llm()
    review = state["review"]

    system_prompt = """당신은 화장품 리뷰의 속성별 감성 분석(ABSA) 전문가입니다.
주어진 리뷰에서 언급된 속성과 해당 감성을 추출하세요.

분석 대상 속성: 보습, 가격, 향, 포장

출력 규칙:
- 코드블록 없이 JSON 1개만 출력
- items는 list, 각 item은 {aspect, label, evidence} 필수
- label은 0(부정) 또는 1(긍정)만 허용
- aspect는 {보습, 가격, 향, 포장} 중 하나만 사용
- evidence는 리뷰 원문에서 그대로 복사한 연속 문자열(substring)만 사용
- 리뷰에 언급되지 않은 속성은 포함하지 말 것

출력 형식:
{"items": [{"aspect": "속성명", "label": 0또는1, "evidence": "리뷰 원문 substring"}]}"""

    repair_directive = ""
    if state.get("critic_result") and state["critic_result"].get("repair_directive"):
        repair_directive = f"\n\n[수정 지시사항]: {state['critic_result']['repair_directive']}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"리뷰: {review}{repair_directive}")
    ]
    response      = llm.invoke(messages)
    content       = response.content.strip()
    try:
        content_clean = re.sub(r'```(?:json)?\s*', '', content)
        content_clean = re.sub(r'```\s*', '', content_clean).strip()
        result        = json.loads(content_clean)
    except json.JSONDecodeError:
        result = {"items": [], "parse_error": content}
    return {"analyzer_result": result}

# 노드2 : critic_node
def critic_node(state: ReviewState):
    llm             = get_llm()
    review          = state["review"]
    analyzer_result = state.get("analyzer_result", {})

    system_prompt = """당신은 화장품 리뷰 분석 결과를 검증하는 전문가입니다.

검증 기준:
- OUTPUT_ERROR: JSON 파싱 불가, items가 list가 아님, aspect/label/evidence 누락, label이 0 또는 1이 아님
- SCOPE_ERROR: aspect가 {보습, 가격, 향, 포장} 외의 값 사용
- EVIDENCE_ERROR: evidence가 리뷰 원문에 없거나 요약·변형된 형태
- QUALITY_ERROR: 환각, 감성 판단 모호, 반복해도 개선 어려운 오류

모든 기준 통과 시 Conformity(적합), 위반 시 Non-conformity(부적합).

출력 형식 (코드블록 없이 JSON 1개):
{"verdict": "Conformity" 또는 "Non-conformity", "reason": "판단 이유", "reason_code": null 또는 오류코드, "repair_directive": null 또는 "수정 지시"}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"리뷰 원문: {review}\n\n분석 결과: {json.dumps(analyzer_result, ensure_ascii=False)}")
    ]
    response = llm.invoke(messages)
    content  = response.content.strip()
    try:
        content_clean = re.sub(r'```(?:json)?\s*', '', content)
        content_clean = re.sub(r'```\s*', '', content_clean).strip()
        result        = json.loads(content_clean)
    except json.JSONDecodeError:
        result = {"verdict": "Non-conformity", "reason": "파싱 실패", "reason_code": "OUTPUT_ERROR",
                  "repair_directive": "JSON만 출력하세요."}
    return {"critic_result": result}

# 노드3 : supervisor_node
def supervisor_node(state: ReviewState):
    analyzer_result = state.get("analyzer_result")
    critic_result   = state.get("critic_result")
    retry_count     = state.get("retry_count", 0)
    max_retries     = state.get("max_retries", 2)

    if analyzer_result is None:
        return {"next_agent": "analyzer"}
    if critic_result is None or critic_result.get("verdict") == "pending":
        return {"next_agent": "critic"}

    verdict     = critic_result.get("verdict", "")
    reason_code = critic_result.get("reason_code", "")

    if verdict == "Conformity":
        return {"next_agent": "end"}
    if reason_code == "QUALITY_ERROR" or retry_count >= max_retries:
        return {"next_agent": "end"}

    repair_directive = critic_result.get("repair_directive")
    return {
        "next_agent":    "analyzer",
        "retry_count":   retry_count + 1,
        "critic_result": {"verdict": "pending", "repair_directive": repair_directive}
    }

# 라우팅 함수
def route_next(state: ReviewState) -> str:
    return state.get("next_agent", "end")

# 그래프
@st.cache_resource
def build_graph():
    builder = StateGraph(ReviewState)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("analyzer",   analyzer_node)
    builder.add_node("critic",     critic_node)
    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor", route_next,
        {"analyzer": "analyzer", "critic": "critic", "end": END}
    )
    builder.add_edge("analyzer", "supervisor")
    builder.add_edge("critic",   "supervisor")
    return builder.compile()

agent_app = build_graph()

# ==================================================
# 2. DB 함수 준비
# ==================================================
# DB 및 테이블 생성 함수
def init_db():
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            review       TEXT,
            agent_aspect TEXT,
            agent_label  TEXT,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# agent 실행 후, 결과 DB 저장 함수
def save_result(review: str, items: list) -> int:
    aspects = json.dumps([item["aspect"] for item in items], ensure_ascii=False)
    labels  = json.dumps([item["label"]  for item in items])
    conn    = sqlite3.connect(DB_PATH)
    cursor  = conn.cursor()
    cursor.execute(
        "INSERT INTO reviews (review, agent_aspect, agent_label) VALUES (?, ?, ?)",
        (review, aspects, labels)
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id

# ==================================================
# 3. Streamlit UI
# ==================================================
init_db()

st.title("상품 리뷰 분석 Agent")

col1, col2 = st.columns(2)

# 리뷰 입력
with col1:
    st.subheader("리뷰 입력")
    review_input = st.text_area(
        "리뷰를 입력하세요", height=200,
        placeholder="예: 보습력이 좋아요. 향도 좋고 가격도 합리적이에요."
    )
    run_btn = st.button("분석 실행", type="primary")

# 속성 분석 결과
with col2:
    st.subheader("Agent 실행 결과")
    result_area = st.empty()

# 버튼 클릭시 Agent 실행
if run_btn:
    if not review_input.strip():
        st.warning("리뷰를 입력해주세요.")
    else:
        with st.spinner("분석 중..."):
            state = {
                "review":          review_input.strip(),
                "analyzer_result": None,
                "critic_result":   None,
                "retry_count":     0,
                "max_retries":     2,
                "next_agent":      "analyzer"
            }
            result = agent_app.invoke(state)

        items = result.get("analyzer_result", {}).get("items", [])

        if items:
            row_id = save_result(review_input.strip(), items)
            st.success(f"DB에 {row_id}번 행 입력됨")

            with col2:
                df_result = pd.DataFrame(items)
                df_result["label"] = df_result["label"].map({1: "긍정", 0: "부정"})
                df_result = df_result.rename(columns={
                    "aspect": "속성", "label": "감성", "evidence": "근거"
                })
                st.dataframe(df_result, use_container_width=True)
        else:
            with col2:
                st.error("분석 결과를 추출하지 못했습니다.")
            st.json(result.get("analyzer_result", {}))
