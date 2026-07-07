"""No-network structural check for llm_interview_grader.py's parsing path (D61).

Mirrors smoke_test_nvidia_parsing.py exactly — feeds parse_nvidia_tool_response()
fixtures shaped like NVIDIA Build's OpenAI-compatible response, so the 5축
GRADING_TOOL parsing/validation logic can be verified without an NVIDIA_API_KEY.

What this DOES verify: well-formed tool_calls parses all 5 FR-04-01 axes;
missing axis / out-of-range score / empty evidence / no-tool-call all raise
the right exception.

What this does NOT verify: whether any real model actually returns this shape
live. That needs benchmarks/grading_run_benchmark.py with a real NVIDIA_API_KEY_1.

Run: python3 feedback/smoke_test_grading_parsing.py
"""
import json
import sys

from llm_interview_grader import FR_AXES, parse_nvidia_tool_response, _validate_grading


def _args(overrides=None):
    payload = {ax: {"score": 4, "evidence": f"근거-{ax}"} for ax in FR_AXES}
    if overrides:
        payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _response(arguments):
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "grade_interview_answer", "arguments": arguments},
                }],
            }
        }]
    }


NO_TOOL_CALL_RESPONSE = {
    "choices": [{"message": {"content": "Sure, here's my grading...", "tool_calls": None}}]
}


def check(label, fn):
    try:
        fn()
    except AssertionError as e:
        print(f"FAIL: {label} -- {e}")
        sys.exit(1)
    print(f"PASS: {label}")


def test_valid_response_parses_all_axes():
    result = parse_nvidia_tool_response(_response(_args()))
    assert set(result.keys()) == set(FR_AXES), result.keys()
    assert all(1 <= v["score"] <= 5 for v in result.values())


def test_missing_axis_raises_value_error():
    payload = {ax: {"score": 4, "evidence": "x"} for ax in FR_AXES}
    del payload[FR_AXES[0]]
    try:
        parse_nvidia_tool_response(_response(json.dumps(payload, ensure_ascii=False)))
    except ValueError:
        return
    raise AssertionError(f"expected ValueError for a response missing {FR_AXES[0]!r}")


def test_out_of_range_score_raises_value_error():
    try:
        _validate_grading({ax: {"score": 9, "evidence": "x"} for ax in FR_AXES})
    except ValueError:
        return
    raise AssertionError("expected ValueError for score=9 (out of 1-5 range)")


def test_empty_evidence_raises_value_error():
    payload = {ax: {"score": 3, "evidence": "x"} for ax in FR_AXES}
    payload[FR_AXES[0]]["evidence"] = ""
    try:
        _validate_grading(payload)
    except ValueError:
        return
    raise AssertionError("expected ValueError for empty evidence string")


def test_no_tool_call_raises_runtime_error():
    try:
        parse_nvidia_tool_response(NO_TOOL_CALL_RESPONSE)
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError when the model skips tool_choice")


if __name__ == "__main__":
    check("well-formed tool_calls parses all 5 FR-04-01 axes", test_valid_response_parses_all_axes)
    check("missing axis raises ValueError", test_missing_axis_raises_value_error)
    check("out-of-range score raises ValueError", test_out_of_range_score_raises_value_error)
    check("empty evidence raises ValueError", test_empty_evidence_raises_value_error)
    check("no tool_calls raises RuntimeError with model content echoed", test_no_tool_call_raises_runtime_error)
    print(
        "\nAll structural checks passed. NOT verified: whether any real model actually\n"
        "returns this shape live for GRADING_TOOL -- see benchmarks/grading_run_benchmark.py."
    )
