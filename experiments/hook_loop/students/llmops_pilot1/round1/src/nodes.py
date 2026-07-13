# source notebook: Step1. 상품리뷰분석 Agent 1.ipynb (cells 33, 35, 37, 40)
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from state import ReviewState, llm


def analyzer_node(state: ReviewState):
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

    # 재시도 시 수정 지시사항 추가
    repair_directive = ""
    if state.get("critic_result") and state["critic_result"].get("repair_directive"):
        repair_directive = f"\n\n[수정 지시사항]: {state['critic_result']['repair_directive']}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"리뷰: {review}{repair_directive}")
    ]

    response = llm.invoke(messages)
    content  = response.content.strip()

    # JSON 파싱 (코드블록 제거 후)
    try:
        content_clean = re.sub(r'```(?:json)?\s*', '', content)
        content_clean = re.sub(r'```\s*', '', content_clean).strip()
        result = json.loads(content_clean)
    except json.JSONDecodeError:
        result = {"items": [], "parse_error": content}

    return {"analyzer_result": result}


def critic_node(state: ReviewState):
    review          = state["review"]
    analyzer_result = state.get("analyzer_result", {})

    system_prompt = """당신은 화장품 리뷰 분석 결과를 검증하는 전문가입니다.

검증 기준:
- OUTPUT_ERROR: JSON 파싱 불가, items가 list가 아님, aspect/label/evidence 누락, label이 0 또는 1이 아님
- SCOPE_ERROR: aspect가 {보습, 가격, 향, 포장} 외의 값 사용
- EVIDENCE_ERROR: evidence가 리뷰 원문에 없거나 요약·변형된 형태
- QUALITY_ERROR: 환각, 감성 판단 모호, 반복해도 개선 어려운 근본적 오류

모든 기준 통과 시 Conformity(적합), 위반 시 Non-conformity(부적합).

출력 형식 (코드블록 없이 JSON 1개):
{"verdict": "Conformity" 또는 "Non-conformity", "reason": "판단 이유", "reason_code": null 또는 "OUTPUT_ERROR|SCOPE_ERROR|EVIDENCE_ERROR|QUALITY_ERROR", "repair_directive": null 또는 "수정 지시"}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"리뷰 원문: {review}\n\n분석 결과: {json.dumps(analyzer_result, ensure_ascii=False)}")
    ]

    response = llm.invoke(messages)
    content  = response.content.strip()

    try:
        content_clean = re.sub(r'```(?:json)?\s*', '', content)
        content_clean = re.sub(r'```\s*', '', content_clean).strip()
        result = json.loads(content_clean)
    except json.JSONDecodeError:
        result = {
            "verdict": "Non-conformity",
            "reason": "critic 출력 파싱 실패",
            "reason_code": "OUTPUT_ERROR",
            "repair_directive": "코드블록 없이 JSON 1개만 출력. items는 list, 각 item은 {aspect, label, evidence} 필수. label은 0 또는 1만 허용."
        }

    return {"critic_result": result}


def supervisor_node(state: ReviewState):
    analyzer_result = state.get("analyzer_result")
    critic_result   = state.get("critic_result")
    retry_count     = state.get("retry_count", 0)
    max_retries     = state.get("max_retries", 2)

    # analyzer 미실행 → analyzer로
    if analyzer_result is None:
        return {"next_agent": "analyzer"}

    # critic 미실행 또는 재시도 후 pending 상태 → critic으로
    if critic_result is None or critic_result.get("verdict") == "pending":
        return {"next_agent": "critic"}

    verdict     = critic_result.get("verdict", "")
    reason_code = critic_result.get("reason_code", "")

    # 적합 → 종료
    if verdict == "Conformity":
        return {"next_agent": "end"}

    # QUALITY_ERROR 또는 최대 재시도 초과 → 종료
    if reason_code == "QUALITY_ERROR" or retry_count >= max_retries:
        return {"next_agent": "end"}

    # 재시도: repair_directive 보존, critic 결과 pending 처리
    repair_directive = critic_result.get("repair_directive")
    return {
        "next_agent":   "analyzer",
        "retry_count":  retry_count + 1,
        "critic_result": {"verdict": "pending", "repair_directive": repair_directive}
    }


def route_next(state: ReviewState) -> str:
    return state.get("next_agent", "end")
