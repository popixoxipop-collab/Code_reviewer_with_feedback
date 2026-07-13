# source notebook: Step1. 상품리뷰분석 Agent 1.ipynb (cells 33, 35, 37, 40)
#
# ── 역할 요약 (Step1 리뷰 피드백: "planner->executor->critic 흐름의 역할을 각 파일에서
#    명확히 하라") ──────────────────────────────────────────────────────────
#   analyzer_node   = Executor : 리뷰 원문 -> 속성별 감성 추출 (실제 "일"을 하는 노드)
#   critic_node     = Critic   : analyzer 결과를 검증하고 표준 reason_code를 매긴다
#   supervisor_node = Planner  : 위 두 결과를 보고 다음 행선지(analyzer/critic/end)와
#                                 재시도 여부만 결정한다 -- 분석/검증 로직은 절대 갖지 않는다
#   route_next      : supervisor_node가 정한 next_agent를 그래프 조건부 엣지가 읽을 수
#                     있는 문자열로 변환해주는 얇은 어댑터
#
# v2.0 변경 (미션④: Reason Code 기반 재시도 정책 고도화):
#   critic이 반환하는 reason_code는 프롬프트로 4종(OUTPUT/SCOPE/EVIDENCE/QUALITY_ERROR)을
#   지시하고 있지만, LLM 출력이라 그 지시를 안 지킬 수 있다 (reason_code를 비우거나
#   목록에 없는 값을 줄 수 있음). v1.0 supervisor_node는 `reason_code == "QUALITY_ERROR"`
#   문자열 하나만 비교했기 때문에, 그 외의 이상값은 전부 "재시도 가능"으로 잘못 분류되고
#   있었다 (retry_count 상한 덕분에 무한루프는 아니었지만, 재시도해도 의미 없는 케이스를
#   재시도로 취급하는 것 자체가 설계상 허점). 아래 REASON_CODE_POLICY + normalize_reason_code
#   로 이 판단을 표로 명시하고, 목록에 없는/빈 reason_code는 UNKNOWN으로 정규화해 안전하게
#   종료(END)하도록 바꿨다 -- "통제 가능한 운영 시스템"이라는 미션 취지에 맞춰, 분류 불가능한
#   신호를 재시도로 밀어붙이지 않고 사람이 확인할 수 있게 멈추는 쪽을 택함.
import json
import re
from typing import Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from state import ReviewState, llm


def analyzer_node(state: ReviewState):
    """Executor: 리뷰 원문에서 속성(보습/가격/향/포장)별 감성을 추출한다."""
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
    """Critic: analyzer 결과를 검증하고 verdict/reason_code/repair_directive를 매긴다."""
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


# ── 미션④: 표준 reason_code 사전 + reason_code별 Retry/종료 정책 ──────────────
# critic_node의 시스템 프롬프트가 지시하는 표준 4종. 이 밖의 값(빈 문자열, None,
# LLM이 지어낸 다른 문자열 등)은 전부 UNKNOWN으로 취급한다.
VALID_REASON_CODES = {"OUTPUT_ERROR", "SCOPE_ERROR", "EVIDENCE_ERROR", "QUALITY_ERROR"}

# reason_code -> "RETRY"(analyzer에게 repair_directive를 주고 다시 시도) 또는
#                "END"(재시도해도 개선 가능성이 낮다고 보고 즉시 종료)
REASON_CODE_POLICY: Dict[str, str] = {
    # 형식/스코프/근거 오류: repair_directive로 analyzer가 실제로 고칠 수 있는 문제 -> 재시도
    "OUTPUT_ERROR":   "RETRY",
    "SCOPE_ERROR":    "RETRY",
    "EVIDENCE_ERROR": "RETRY",
    # 환각/모호성 등 근본적 오류: 반복해도 개선되기 어려움 -> 즉시 종료
    "QUALITY_ERROR":  "END",
    # critic이 표준 코드를 안 지켰거나 비워둔 경우: 신뢰할 수 없는 신호이므로
    # 재시도로 밀어붙이지 않고 안전하게 종료 (사람이 확인하도록 남겨둠)
    "UNKNOWN":        "END",
}


def normalize_reason_code(raw_reason_code: Optional[str]) -> str:
    """critic_node가 반환한 reason_code를 표준 4종 + UNKNOWN으로 정규화한다."""
    if raw_reason_code in VALID_REASON_CODES:
        return raw_reason_code
    return "UNKNOWN"


def supervisor_node(state: ReviewState):
    """Planner/Router: analyzer(Executor)/critic(Critic) 실행 결과를 보고 다음 행선지와
    재시도 여부를 결정한다. 분석/검증 로직은 이 함수에 두지 않는다."""
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

    verdict = critic_result.get("verdict", "")

    # 적합 → 종료
    if verdict == "Conformity":
        return {"next_agent": "end"}

    # 표준 reason_code로 정규화 후 정책 조회 (미션④)
    reason_code = normalize_reason_code(critic_result.get("reason_code"))
    policy      = REASON_CODE_POLICY[reason_code]

    # 정책이 END이거나 최대 재시도 횟수를 넘었으면 종료 (retry_count 상한은 정책과
    # 무관하게 항상 최우선 안전장치로 유지)
    if policy == "END" or retry_count >= max_retries:
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
