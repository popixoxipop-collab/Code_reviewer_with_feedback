import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "judgment"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "feedback"))
from isolation_classifier import classify_justification  # noqa: E402
from isolation_hook import record_feedback as isolation_feedback, recursive_update as isolation_update  # noqa: E402
from reflection_signal import evaluate_reflection  # noqa: E402
from reflection_hook import record_feedback as reflection_feedback, recursive_update as reflection_update  # noqa: E402
from evidence_bridge import finding_category  # noqa: E402
from followup_generator import generate_followup  # noqa: E402

# D49: keyword hook 검출 실패 시 Socratic+Depth Ladder로 escalate하고, escalation이
#   성공하면(judge 확인) 그 결과를 hook에 재귀적으로 되먹임 — D37/D39~41에서 내가
#   수작업으로 하던 "새 데이터 → hook 후보 등록" 루프를 자동화
#   WHY: 사용자 제안 — "keyword hook 검출 실패 시 소크라틱+DepthLadder로 보내고
#        hook을 업데이트한다"는 재귀적 업데이트 규칙. followup_generator.py가
#        이미 escalation 질문 생성까지는 하지만, 그 결과를 hook에 다시 먹이는
#        루프는 없었다 — 이 모듈이 그 마지막 연결을 완성한다
#   COST: escalation이 "성공"했는지 판정(judge)은 결정론적 규칙으로 할 수 없다
#        (자연어 답변이 "이제는 충분한가"를 판단하는 건 그 자체로 LLM 판단이 필요).
#        그래서 judge_verdict는 이 모듈 밖(Codex 등 실제 LLM 호출)에서 받아와야
#        하고, 이 모듈은 "판정을 hook에 안전하게 반영하는 절차"만 담당한다 —
#        완전 자동 폐루프가 아니라 사람/LLM 판정 1단계가 여전히 낀 반자동 루프
#   EXIT: judge 자체를 이 모듈 안에서 규칙으로 대체하려면(예: 서브축 재사용) 이미
#        있는 evaluate_reflection/classify_justification을 재적용하면 되지만,
#        그러면 "escalation의 의미"(더 깊이 파고들어야만 보이는 신호를 hook이 아직
#        모른다는 것) 자체가 사라짐 — escalation judge는 hook과 반드시 독립적이어야 함


def check_escalation_needed(finding_id, first_answer):
    """hook이 첫 답변을 이미 confirmed로 판정했으면 escalation 불필요."""
    category = finding_category(finding_id)
    if category == "cognition-isolation":
        result = classify_justification(first_answer)
        already_confirmed = result["justified"]
    else:
        result = evaluate_reflection(first_answer)
        already_confirmed = result["reflection_present"]

    if already_confirmed:
        return {"escalation_needed": False, "hook_result": result}

    followup = generate_followup(finding_id, first_answer)
    return {"escalation_needed": True, "hook_result": result, "followup_question": followup["followup_question"], "followup_trigger": followup["trigger"]}


def apply_escalation_result(finding_id, judge_verdict, judge_reason, target, pattern_id, phrase):
    """judge_verdict(사람 또는 LLM이 내린 True/False)를 hook에 재귀적으로 반영.

    D51 교훈: pattern_id/phrase를 자동 추출하지 않고 반드시 호출자가 명시한다 — 자동
    추출은 (a) 파일명 기반이면 findings마다 pattern_id가 달라져 threshold까지 절대
    누적되지 않고, (b) 텍스트 휴리스틱이면 의미 없는 단어를 뽑을 위험이 있다. 사람이
    실제 문구를 읽고 "이건 기존 카테고리/서브신호의 어떤 표현과 같은 부류인가"를
    판단해 pattern_id를 고르는 게 D37/D39~41에서 실제로 하던 방식과 일치한다.

    judge_verdict=False면 아무것도 안 함(성급한 신뢰 금지, D6 계승) — escalation
    자체가 실패했다는 뜻이라 hook에 넣을 근거가 없다.

    target: isolation이면 카테고리명(role_separation 등), reflection이면 서브신호명
    (self_error_recognition 등).
    """
    category = finding_category(finding_id)
    if not judge_verdict:
        return {"hook_updated": False, "reason": f"judge rejected: {judge_reason}"}

    regex = re.escape(phrase)
    if category == "cognition-isolation":
        isolation_feedback(target, pattern_id, regex, "genuine_justification",
                            note=f"escalation 성공(judge: {judge_reason})", source_finding=finding_id)
        data, promotions, demotions = isolation_update(target)
        confirmations = next((p["confirmations"] for p in data["patterns"] if p["id"] == pattern_id), 0)
        return {"hook_updated": True, "category": target, "pattern_id": pattern_id, "confirmations": confirmations, "promotions": promotions, "demotions": demotions}

    reflection_feedback(target, pattern_id, regex, "genuine_signal",
                         note=f"escalation 성공(judge: {judge_reason})", source_finding=finding_id)
    data, promotions, demotions = reflection_update(target)
    confirmations = next((p["confirmations"] for p in data["patterns"] if p["id"] == pattern_id), 0)
    return {"hook_updated": True, "sub_signal": target, "pattern_id": pattern_id, "confirmations": confirmations, "promotions": promotions, "demotions": demotions}


def main():
    if len(sys.argv) < 3:
        print("usage: escalation_hook.py check <finding_id> <first_answer>", file=sys.stderr)
        print("       escalation_hook.py apply <finding_id> <true|false> <reason> <target> <pattern_id> <phrase>", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "check":
        print(json.dumps(check_escalation_needed(sys.argv[2], sys.argv[3]), ensure_ascii=False, indent=2))
    elif cmd == "apply":
        verdict = sys.argv[3].lower() == "true"
        print(json.dumps(apply_escalation_result(sys.argv[2], verdict, sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7]), ensure_ascii=False, indent=2))
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
