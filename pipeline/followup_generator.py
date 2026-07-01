import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "judgment"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "feedback"))
from isolation_classifier import classify_justification  # noqa: E402
from reflection_signal import evaluate_reflection  # noqa: E402
from evidence_bridge import finding_category  # noqa: E402

# D48: D안에 적응형 Follow-up 질문 생성을 실제로 구현 (팀 문서 §3 "적응형 후속 질문
#   전략"표를 코드 규칙으로 그대로 이식)
#   WHY: 사용자가 팀 비교표(질문 생성/Follow-up 질문 칸)를 보여주며 "우리 진행 방식을
#        저기에 맞춰야지, 구현을 잘못했다"고 정정 — D안이 단발 질문만 생성하고
#        Follow-up이 "없음"인 채로 두는 건 팀 표준(모든 방법론이 실제 Follow-up을
#        가짐)에 안 맞음. 팀 자체 문서(코드이해도_평가_질문및채점기준.md §3)의
#        "1차 답변 상태 → 후속 질문 방향" 표를 그대로 규칙으로 옮기되, "1차 답변 상태"
#        판정은 새 LLM 호출 없이 이미 만든 isolation_classifier/reflection_signal로 함
#   COST: 진짜 LLM 기반 적응형 질문(A/B안처럼 매번 새로 생성)은 아니다 — 고정된
#        분기 트리 안에서 사전 정의된 5개 방향 중 하나를 고른다. API 없이 만들 수
#        있는 한도 내에서의 "규칙 기반 적응형"이지 "생성형 적응형"이 아님
#   EXIT: API가 생기면 이 규칙 트리의 각 분기점에서 Codex/Claude를 호출해 방향은
#        같지만 문구를 매번 새로 생성하도록 교체 가능(분기 로직은 그대로 재사용)

RISK_TYPE_CATEGORIES = ("tier-b-risk", "repeated-pattern", "architecture-diffusion")


def _risk_type_followup(first_answer):
    r = evaluate_reflection(first_answer)
    sub = r["sub_signals"]
    if not sub["self_error_recognition"]["matched"]:
        return (
            "그런데 만약 악의적인 사용자가 이 부분의 입력값을 의도적으로 조작한다면"
            " 어떤 일이 벌어질까요?",
            "오개념 감지(self_error_recognition 미확인) → 소크라테스식 반례로 스스로 모순 발견 유도",
        )
    if not sub["reason_explanation"]["matched"]:
        return (
            "구체적으로 어떤 코드 라인이나 함수가 이 판단의 직접적인 근거인가요?",
            "답변이 모호/추상적(reason_explanation 미확인) → 코드 라인/함수명으로 구체화 요청",
        )
    if not sub["concrete_improvement"]["matched"]:
        return (
            "그 문제를 해결할 다른 방법은 없었나요? 있다면 무엇인가요?",
            "대안 미언급(concrete_improvement 미확인) → 대안 탐색 질문",
        )
    if not sub["new_judgment"]["matched"]:
        return (
            "만약 이 조건이 조금 다르게(예: 외부 API가 아니라 사용자 직접 입력이라면)"
            " 바뀐다면 이 코드는 어떻게 동작할까요?",
            "암기한 듯 매끄러우나 근거 얕음(new_judgment 미확인) → 변형 질문으로 순간 대응력 확인",
        )
    return (
        "잘 설명하셨습니다. 그럼 지금 다시 설계한다면 이 부분에서 그대로 유지할 것과"
        " 바꿀 것은 각각 무엇인가요?",
        "4개 서브신호 전부 확인됨 → 답변이 충분히 깊음, 다음 축(설계추론/트레이드오프)으로 이동",
    )


def _isolation_followup(first_answer):
    c = classify_justification(first_answer)
    if not c["justified"]:
        return (
            "구체적으로 어떤 코드 라인이나 함수가 이 판단의 근거인가요?",
            "카테고리 미매치(justified=False) → 답변이 모호/추상적, 코드 라인으로 구체화 요청",
        )
    if len(c["matched_categories"]) == 1:
        return (
            "만약 이 파일이 나중에 다른 화면에서도 재사용된다면, 지금의 판단이 그대로"
            " 유효할까요? 왜 그런가요?",
            f"카테고리 1개만 매치({c['matched_categories']}) → 암기한 듯 매끄러우나 근거 얕음, 변형 질문",
        )
    return (
        "잘 설명하셨습니다. 그럼 이런 구조를 팀 컨벤션으로 문서화해둔 게 있나요, 아니면"
        " 이번에 처음 이렇게 판단하신 건가요?",
        f"카테고리 {len(c['matched_categories'])}개 동시 매치({c['matched_categories']}) → 답변이 충분히 깊음, 다음 축(설계 일관성)으로 이동",
    )


def generate_followup(finding_id, first_answer):
    category = finding_category(finding_id)
    if category == "cognition-isolation":
        question, trigger = _isolation_followup(first_answer)
    elif category in RISK_TYPE_CATEGORIES:
        question, trigger = _risk_type_followup(first_answer)
    else:
        question, trigger = ("이 부분에 대해 조금 더 구체적으로 설명해줄 수 있나요?", "분류 대상 category 아님 — 기본 질문")
    return {"finding_id": finding_id, "followup_question": question, "trigger": trigger}


def main():
    if len(sys.argv) < 3:
        print("usage: followup_generator.py <finding_id> <first_answer_text>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(generate_followup(sys.argv[1], sys.argv[2]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
