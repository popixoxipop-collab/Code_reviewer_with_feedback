import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from idiom_filter import resolve_lang, load_patterns  # noqa: E402

# D29: SUBRUBRIC_DRAFT.md(D27/D28)를 score_findings.py에 실제로 연결하는 구현체
#   WHY: 초안 문서만으로는 실행 가능한 채점이 안 됨 — 인지 블록이 이미 만들어내는 필드
#        (fan_in/pattern_key/matched_text/트리거/idiom 로그)만으로 4서브축×3축을 계산해
#        새 스캔 로직 추가 없이 감사 가능한 점수를 만든다
#   COST: score_findings.py의 각 finding 생성 지점마다 증거값을 조립하는 코드가 늘어남
#        (finding 종류별로 쓸 수 있는 증거가 달라 공용 함수 하나로 뭉치지 못함)
#   EXIT: 증거 조립이 너무 번잡해지면 finding 종류별 evidence dataclass로 리팩터링 검토
#
# D30: 서브축 점수 컷오프는 SUBRUBRIC_DRAFT.md와 동일하게 상=9~12/중=5~8/하=0~4 유지
#   WHY: 문서와 코드가 다른 값을 쓰면 팀 합의가 깨짐 — 이 구현의 목적은 문서를 실행
#        가능하게 만드는 것이지 새 기준을 도입하는 게 아님
#   COST: 컷오프가 실측 데이터 없이 여전히 임의값(D28와 동일 COST를 계승)
#   EXIT: THRESHOLDS만 바꾸면 판단 블록 전체가 재보정됨(단일 지점)
THRESHOLDS = {"상": 9, "중": 5}


def bucket(total):
    """0~12 총점을 기존 상/중/하 문자열로 재매핑한다(D28).

    idiom_filter.DOWNGRADE_MAP은 정확히 "상"/"중"/"하" 키만 인식하므로, 여기서 반환하는
    문자열은 절대 다른 텍스트를 덧붙이면 안 된다(하위호환 필수 조건).
    """
    if total >= THRESHOLDS["상"]:
        return "상"
    if total >= THRESHOLDS["중"]:
        return "중"
    return "하"


def _clamp(x):
    return max(0, min(3, x))


def idiom_evidence(pattern_key, file):
    """pattern_key가 있으면 해당 언어 idiom 저장소에서 (status, confirmations)를 조회한다.

    pattern_key가 없거나 언어 판별이 안 되면 ("none", 0) — "이 finding은 알려진 프레임워크
    관용 패턴과 아직 매치되지 않았다"는 뜻이지 "관용 패턴이 아니다"라는 확정 판정이 아니다.
    """
    if not pattern_key or not file:
        return "none", 0
    lang = resolve_lang(file)
    if lang is None:
        return "none", 0
    data = load_patterns(lang)
    for p in data["patterns"]:
        if p["id"] == pattern_key:
            return p["status"], p["confirmations"]
    return "none", 0


def score_design_intent(*, repetition, idiom_status, location_signal, mitigation_present):
    """설계의도 축 — 이 구조가 의식적 설계 결정인가, 방치/누락인가.

    repetition: 이 패턴/구조가 repo 내 몇 곳에서 더 나타나는가(정수, 0~3+ clamp)
    idiom_status: idiom_evidence()의 status — confirmed일수록 "생각해서 짠 것"이 아니라
                  "그냥 따라간 컨벤션"에 가까우므로 역채점(confirmed=0, candidate=1, none=3)
    location_signal: 파일명/구조가 의도적 분리를 암시하는가(bool)
    mitigation_present: 완화/방어 시도가 코드에 보이는가(bool). 해당 없는 finding
                         종류는 None → 중립값(1) 부여
    """
    sub = {
        "repetition_consistency": _clamp(repetition),
        "idiom_conformance_reverse": {"confirmed": 0, "candidate": 1, "none": 3}[idiom_status],
        "location_signal": 3 if location_signal else 0,
        "mitigation_present": 1 if mitigation_present is None else (3 if mitigation_present else 0),
    }
    return sum(sub.values()), sub


def score_question_value(*, tradeoff_signal, repo_specificity, idiom_downgrade_votes, ladder_richness):
    """질문가치 축 — 이 finding을 물었을 때 이해도 격차가 실제로 드러나는가.

    tradeoff_signal: "왜 이렇게 했나"에 정답이 하나로 안 정해지고 대안이 실재하는가(bool)
    repo_specificity: 범용 지식으론 답 못하고 이 코드를 봐야만 답할 수 있는가(bool)
    idiom_downgrade_votes: idiom_evidence()의 confirmations — 과거에 "그냥 컨벤션"으로
                           강등된 표수가 많을수록 질문가치가 낮아지므로 역채점
    ladder_richness: Depth Ladder 7단계를 채울 정보량(정수, 0~3+ clamp)
    """
    sub = {
        "tradeoff_existence": 3 if tradeoff_signal else 0,
        "repo_specificity": 3 if repo_specificity else 0,
        "idiom_contamination_reverse": _clamp(3 - idiom_downgrade_votes),
        "ladder_richness": _clamp(ladder_richness),
    }
    return sum(sub.values()), sub


def score_risk(*, trigger_confirmed, exposure_client, scenario_specific, spread_count):
    """위험도 축 — 실제 보안/신뢰성 문제인가.

    trigger_confirmed: 이 히트가 오탐 억제 필터를 통과했고 매치 조건 자체도 신뢰도가
                        높은가(bool). Tier B 미해당 finding은 None → 중립값(1)
    exposure_client: 문제 코드/데이터가 외부 접근 가능 경로에 있는가(bool). 불명은 None → 중립값(1)
    scenario_specific: matched_text만으로 구체적 공격/오류 시나리오 서술이 가능한가(bool)
    spread_count: 동일 위험 패턴이 몇 개 파일에 반복되는가(정수, 0~3+ clamp)
    """
    sub = {
        "trigger_confidence": 1 if trigger_confirmed is None else (3 if trigger_confirmed else 0),
        "exposure_scope": 1 if exposure_client is None else (3 if exposure_client else 0),
        "scenario_specificity": 3 if scenario_specific else 0,
        "spread_scope": _clamp(spread_count),
    }
    return sum(sub.values()), sub


def apply_subrubric(finding, design_intent_evidence, question_value_evidence, risk_evidence):
    """세 축을 계산해 finding에 상/중/하 문자열(하위호환) + subrubric 감사 트레일을 채운다."""
    di_total, di_sub = score_design_intent(**design_intent_evidence)
    qv_total, qv_sub = score_question_value(**question_value_evidence)
    rk_total, rk_sub = score_risk(**risk_evidence)

    finding["design_intent"] = bucket(di_total)
    finding["question_value"] = bucket(qv_total)
    finding["risk"] = bucket(rk_total)
    finding["subrubric"] = {
        "design_intent": {"sub": di_sub, "total": di_total},
        "question_value": {"sub": qv_sub, "total": qv_total},
        "risk": {"sub": rk_sub, "total": rk_total},
    }
    return finding
