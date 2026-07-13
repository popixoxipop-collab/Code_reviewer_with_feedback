# source notebook: Step1. 상품리뷰분석 Agent 1.ipynb (cell 52, %%writefile app.py)
#
# v2.0 변경 (Step1 리뷰 피드백 반영):
# v1.0에서는 이 파일이 state.py/nodes.py/agent_graph.py의 ReviewState / analyzer_node /
# critic_node / supervisor_node / route_next / build_graph를 전부 다시 정의하고 있었다
# (원본 노트북에서 `%%writefile app.py` 셀로 뜯어낸 결과라, 노트북 앞쪽 셀들을 import할
# 방법이 없어 통째로 복붙된 것). 리뷰에서 "import를 쓰지 않은 이유를 설명하라"는 지적을
# 받았는데, 그 이유는 "당시엔 진짜로 import가 불가능한 노트북 구조였다"였다.
#
# 지금은 상황이 다르다 -- app.py도 state.py/nodes.py/agent_graph.py/db.py/config.py와
# 같은 src/ 디렉터리에 있는 평범한 파일이고, `streamlit run app.py`로 실행해도 Streamlit이
# 스크립트가 있는 디렉터리를 sys.path에 넣어주기 때문에 나머지 모듈을 그냥 import하면
# 된다. 즉 "정말 독립 실행이 필요한 예외 케이스"에 더 이상 해당하지 않는다고 판단해서,
# 아래처럼 전부 import로 바꿨다 (자체 정의 0개). Agent 로직(누가 실행되고 언제 재시도할지)
# 은 이제 nodes.py / agent_graph.py 딱 한 곳에만 존재한다.
#
# 부수 효과: v1.0에서는 ChatOpenAI 재생성을 막으려고 @st.cache_resource로 감싼
# get_llm()/build_graph()가 따로 있었다. 이제는 llm(state.py)과 컴파일된 그래프
# (agent_graph.py)가 모듈 최상위에서 한 번만 만들어지고, Streamlit이 매 인터랙션마다
# app.py 본문을 재실행해도 이미 import된 모듈은 Python의 sys.modules 캐시 덕분에
# 다시 실행되지 않는다 -- 그래서 Streamlit 전용 캐싱 데코레이터 없이도 v1.0과 동일한
# "LLM/그래프를 한 번만 생성" 효과를 얻는다.
import json

import pandas as pd
import streamlit as st

from agent_graph import app as agent_app  # 컴파일된 LangGraph. 노드/그래프 정의는 여기 안 둔다.
from config import load_api_keys
from db import fetch_history, init_db, insert_review
from monitoring import setup_langsmith_tracing, trace_run_config

# ── 기본 설정 ──────────────────────────────────────────────
st.set_page_config(page_title="상품 리뷰 분석 Agent", layout="wide")

load_api_keys()

# 미션③ [필수]: LangSmith trace 환경변수 설정. 이후 agent_app.invoke() 호출은
# (LANGSMITH_API_KEY가 유효하다면) 자동으로 LangSmith 프로젝트에 기록된다.
setup_langsmith_tracing()

init_db()

st.title("상품 리뷰 분석 Agent")

tab_run, tab_history = st.tabs(["분석 실행", "실행 이력"])

# ==================================================
# 탭 1. 분석 실행 (v1.0 UI 유지)
# ==================================================
with tab_run:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("리뷰 입력")
        review_input = st.text_area(
            "리뷰를 입력하세요", height=200,
            placeholder="예: 보습력이 좋아요. 향도 좋고 가격도 합리적이에요."
        )
        run_btn = st.button("분석 실행", type="primary")

    with col2:
        st.subheader("Agent 실행 결과")
        result_area = st.empty()

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
                result = agent_app.invoke(
                    state,
                    config=trace_run_config(
                        run_name="streamlit-analyze",
                        review_len=len(review_input.strip()),
                    ),
                )

            items         = result.get("analyzer_result", {}).get("items", [])
            critic_result = result.get("critic_result") or {}
            verdict       = critic_result.get("verdict")
            reason_code   = critic_result.get("reason_code")
            retry_count   = result.get("retry_count", 0)

            if items:
                # 미션④: critic의 최종 verdict/reason_code, 재시도 횟수까지 함께 저장해서
                # "실행 이력" 탭에서 재시도 정책이 실제로 어떻게 동작했는지 볼 수 있게 한다.
                row_id = insert_review(
                    review_input.strip(), items,
                    verdict=verdict, reason_code=reason_code, retry_count=retry_count,
                )
                st.success(f"DB에 {row_id}번 행 입력됨 (verdict={verdict}, 재시도={retry_count}회)")

                with col2:
                    df_result = pd.DataFrame(items)
                    df_result["label"] = df_result["label"].map({1: "긍정", 0: "부정"})
                    df_result = df_result.rename(columns={
                        "aspect": "속성", "label": "감성", "evidence": "근거"
                    })
                    st.dataframe(df_result, use_container_width=True)

                    if verdict != "Conformity":
                        st.caption(
                            f"참고: critic 최종 판정 = {verdict} / reason_code = {reason_code} "
                            f"(재시도 {retry_count}회 후 종료됨)"
                        )
            else:
                with col2:
                    st.error("분석 결과를 추출하지 못했습니다.")
                st.json(result.get("analyzer_result", {}))

# ==================================================
# 탭 2. 실행 이력 (미션⑤ 신규)
# ==================================================
with tab_history:
    st.subheader("실행 이력 (과거 분석 결과)")
    st.caption("reviews 테이블에 저장된 과거 실행 결과를 최신순으로 보여줍니다.")

    st.button("새로고침", key="history_refresh")  # 클릭 시 Streamlit이 스크립트를 재실행 -> 재조회
    history_df = fetch_history()

    if history_df.empty:
        st.info("아직 저장된 분석 이력이 없습니다.")
    else:
        def _decode_json_list(raw, label_map=None):
            """DB에 JSON 문자열로 저장된 agent_aspect/agent_label 컬럼을 사람이 읽기
            좋은 문자열로 풀어준다. 파싱 실패 시 원본 값을 그대로 반환한다(방어적)."""
            if not isinstance(raw, str):
                return ""
            try:
                values = json.loads(raw)
            except json.JSONDecodeError:
                return raw
            if label_map:
                values = [label_map.get(v, v) for v in values]
            return ", ".join(str(v) for v in values)

        display_df = history_df.copy()
        display_df["agent_aspect"] = display_df["agent_aspect"].apply(_decode_json_list)
        display_df["agent_label"] = display_df["agent_label"].apply(
            lambda raw: _decode_json_list(raw, {1: "긍정", 0: "부정"})
        )
        display_df = display_df.rename(columns={
            "id": "ID",
            "review": "리뷰",
            "agent_aspect": "속성",
            "agent_label": "감성",
            "verdict": "검증결과",
            "reason_code": "사유코드",
            "retry_count": "재시도횟수",
            "updated_at": "기록시각",
        })

        st.dataframe(display_df, use_container_width=True)

        total = len(history_df)
        conform = int((history_df["verdict"] == "Conformity").sum())
        st.caption(f"총 {total}건 · Conformity {conform}건 · Non-conformity/미기록 {total - conform}건")
