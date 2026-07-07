"""No-network structural check for turn_engine.classify_answer() (D87).

Locks in the level-based classification fix found via live smoke test (D87):
evaluate_reflection()'s self_error_recognition requirement is only meaningful
at level="reflection" (post-challenge self-correction) -- applying it to
level="l1"/"l2"/"l3" made even a genuinely strong initial answer classify as
"surface", because a good first answer has no reason to contain "I was wrong"
language. This test would have caught that regression without needing a live
NVIDIA_API_KEY_1.

What this DOES verify: classify_answer()'s level-interpretation logic in
isolation, via a monkeypatched evaluate_reflection() returning fixed fixture
dicts -- so the test's pass/fail depends only on the branching code, not on
whether reflection_signal's confirmed-pattern DB happens to be populated
right now. (D87 COST already documents that DB is currently empty for
tier-b-risk/repeated-pattern/architecture-diffusion -- an earlier version of
this test called the real evaluate_reflection() and always got "surface"
regardless of level, which was correctly reproducing that data gap but told
us nothing about whether the *branching logic* itself was correct. This
version isolates the two concerns.)

What this does NOT verify: whether reflection_signal's confirmed patterns are
rich enough to distinguish real student answers -- that's a data-population
concern tracked separately (D87 EXIT), not a code-correctness concern.

Run: python3 feedback/smoke_test_turn_engine.py
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "judgment"))
import turn_engine  # noqa: E402

# 실제 evaluate_reflection() 반환 모양을 그대로 흉내낸 fixture -- self_error_recognition은
# 매치 안 됐지만(자기교정 언어 없음) 나머지 3개 optional 서브신호는 2개 매치된 "강하지만
# 반성은 아닌" 답변 상황을 재현한다.
FIXTURE_STRONG_NOT_SELF_CORRECTING = {
    "reflection_present": False,  # required_ok=False라서 원래 정의로도 항상 False
    "matched_count": 2,
    "total_sub_signals": 4,
    "required_ok": False,
    "optional_matches": 2,
    "min_optional_required": 2,
    "sub_signals": {
        "self_error_recognition": {"matched": False, "pattern_id": None},
        "reason_explanation": {"matched": True, "pattern_id": "fixture"},
        "concrete_improvement": {"matched": False, "pattern_id": None},
        "new_judgment": {"matched": True, "pattern_id": "fixture"},
    },
}


def check(condition, message):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {message}")
    return condition


def main():
    ok = True

    with patch.object(turn_engine, "evaluate_reflection", return_value=FIXTURE_STRONG_NOT_SELF_CORRECTING):
        for level in ("l1", "l2", "l3"):
            result = turn_engine.classify_answer("architecture-diffusion", "(fixture 답변, 텍스트는 안 씀)", level=level)
            # self_error_recognition이 없어도(자기교정 언어 없음) optional 2개 매치면
            # l1/l2/l3 기준으로는 defended여야 한다 -- D87 이전 버그(항상 surface)가
            # 재발하면 이 assert가 실패한다.
            ok &= check(
                result["verdict"] == "defended",
                f"level={level}: 자기교정 언어 없어도 optional 2개 매치면 defended (verdict={result['verdict']})",
            )

        reflection_result = turn_engine.classify_answer("architecture-diffusion", "(fixture 답변)", level="reflection")
        ok &= check(
            reflection_result["verdict"] == "surface",
            f"level=reflection: required_ok=False(자기교정 언어 없음)면 optional 매치와 무관하게 surface "
            f"(verdict={reflection_result['verdict']}) -- reflection 단계에서만 self_error_recognition을 "
            "필수로 요구하는 원래 의도가 유지됨",
        )

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
