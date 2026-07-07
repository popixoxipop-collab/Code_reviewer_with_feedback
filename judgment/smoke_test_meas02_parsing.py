"""No-network structural check for meas02_decision_point_extractor.py's parsing path.

Mirrors feedback/smoke_test_nvidia_parsing.py exactly — feeds parse_nvidia_tool_response()
fixtures shaped like NVIDIA Build's OpenAI-compatible response, so the
DECISION_POINT_TOOL parsing/validation/ranking logic can be verified without an
NVIDIA_API_KEY.

Run: python3 judgment/smoke_test_meas02_parsing.py
"""
import json
import sys

from meas02_decision_point_extractor import parse_nvidia_tool_response, rank_by_focus, _validate_extraction


def _response(arguments):
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "extract_decision_points", "arguments": arguments},
                }],
            }
        }]
    }


VALID_ARGS = json.dumps({
    "decision_points": [
        {"file": "firebase.ts", "function": "signIn", "judgment_type": "에러 처리",
         "evidence": "JSON.stringify(authInfo)를 Error에 실어 throw", "linked_requirement": ""},
        {"file": "firebase.ts", "function": "module scope", "judgment_type": "아키텍처 선택",
         "evidence": "SDK 초기화를 모듈 최상단에서 1회만 수행", "linked_requirement": ""},
    ]
}, ensure_ascii=False)

MISSING_FIELD_ARGS = json.dumps({
    "decision_points": [{"file": "x.ts", "function": "f", "judgment_type": "", "evidence": "y"}]
}, ensure_ascii=False)

NO_TOOL_CALL_RESPONSE = {
    "choices": [{"message": {"content": "Here are the decision points...", "tool_calls": None}}]
}


def check(label, fn):
    try:
        fn()
    except AssertionError as e:
        print(f"FAIL: {label} -- {e}")
        sys.exit(1)
    print(f"PASS: {label}")


def test_valid_response_parses_decision_points():
    result = parse_nvidia_tool_response(_response(VALID_ARGS))
    assert len(result["decision_points"]) == 2
    assert result["decision_points"][0]["file"] == "firebase.ts"


def test_missing_field_raises_value_error():
    try:
        parse_nvidia_tool_response(_response(MISSING_FIELD_ARGS))
    except ValueError:
        return
    raise AssertionError("expected ValueError for empty judgment_type")


def test_no_tool_call_raises_runtime_error():
    try:
        parse_nvidia_tool_response(NO_TOOL_CALL_RESPONSE)
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError when the model skips tool_choice")


def test_rank_by_focus_moves_matches_first():
    points = [
        {"judgment_type": "데이터 모델링", "evidence": "스키마 설계"},
        {"judgment_type": "보안 판단", "evidence": "인증 토큰 검증 로직"},
    ]
    ranked = rank_by_focus(points, "보안")
    assert ranked[0]["judgment_type"] == "보안 판단", ranked


def test_rank_by_focus_noop_without_focus_area():
    points = [{"judgment_type": "a", "evidence": "1"}, {"judgment_type": "b", "evidence": "2"}]
    assert rank_by_focus(points, None) == points


def test_validate_extraction_rejects_non_list():
    try:
        _validate_extraction({"decision_points": "not a list"})
    except ValueError:
        return
    raise AssertionError("expected ValueError when decision_points isn't a list")


if __name__ == "__main__":
    check("well-formed tool_calls parses decision_points", test_valid_response_parses_decision_points)
    check("missing/empty field raises ValueError", test_missing_field_raises_value_error)
    check("no tool_calls raises RuntimeError", test_no_tool_call_raises_runtime_error)
    check("rank_by_focus moves focus-matching points first", test_rank_by_focus_moves_matches_first)
    check("rank_by_focus is a no-op without focus_area", test_rank_by_focus_noop_without_focus_area)
    check("non-list decision_points raises ValueError", test_validate_extraction_rejects_non_list)
    print(
        "\nAll structural checks passed. NOT verified: whether any real model actually\n"
        "returns this shape live -- see benchmarks/meas02_run_benchmark.py."
    )
