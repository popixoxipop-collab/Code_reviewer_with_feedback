import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reflection_hook import SUB_SIGNALS, load_patterns  # noqa: E402

# D33: reflection_present는 4개 서브신호가 전부 confirmed 패턴으로 매치돼야 True (AND 조건)
#   WHY: POC_TEST.md 문제6(Ownership vs Knowledge)의 핵심 도구 — "답을 조금 고쳤다"가 아니라
#        자기오류인식+이유설명+새판단+개선안 4단계가 다 있어야 진짜 Reflection이라는 ROAF-B
#        정의를 그대로 코드화. 4개 중 하나라도 없으면 "아직 Knowledge 수준"으로 간주
#   COST: 매우 보수적 — 실측 결과 팀이 직접 작성한 "모범 Reflection 예시" 문장 하나조차
#         AND 조건을 다 통과하지 못했다(아래 실행 로그 참고). 단일 발화 평가에는 너무 엄격할
#         수 있고, 여러 턴에 걸친 근거를 모아야 할 가능성을 시사함(Aggregation 필요, 문제5)
#   EXIT: 단일 발화 기준이 너무 엄격하다고 판명되면 4개 중 3개 이상(OR-3)으로 완화하거나,
#         여러 턴의 텍스트를 합쳐서 검사하도록 evaluate_reflection에 turns: list[str] 지원 추가


def detect_sub_signal(text, sub_signal):
    """confirmed 상태인 정규식 패턴만으로 텍스트를 검사한다 — candidate 패턴은 신뢰 안 함(D6 계승)."""
    data = load_patterns(sub_signal)
    for p in data["patterns"]:
        if p["status"] != "confirmed":
            continue
        if re.search(p["regex"], text):
            return True, p["id"]
    return False, None


def evaluate_reflection(text):
    """4개 서브신호가 전부 confirmed 패턴으로 매치돼야 reflection_present=True."""
    results = {}
    for sub in SUB_SIGNALS:
        matched, pattern_id = detect_sub_signal(text, sub)
        results[sub] = {"matched": matched, "pattern_id": pattern_id}
    reflection_present = all(r["matched"] for r in results.values())
    matched_count = sum(1 for r in results.values() if r["matched"])
    return {
        "reflection_present": reflection_present,
        "matched_count": matched_count,
        "total_sub_signals": len(SUB_SIGNALS),
        "sub_signals": results,
    }


def main():
    if len(sys.argv) < 2:
        print("usage: reflection_signal.py \"<text>\"", file=sys.stderr)
        sys.exit(1)
    import json
    print(json.dumps(evaluate_reflection(sys.argv[1]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
