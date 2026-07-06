"""No-network structural check for the NVIDIA tool-call parsing path (D56).

Feeds parse_nvidia_tool_response() fixtures shaped like NVIDIA Build's
OpenAI-compatible /v1/chat/completions response, so the parsing/validation
logic can be verified without an NVIDIA_API_KEY.

What this DOES verify: parse_nvidia_tool_response() correctly extracts the
7 depth-ladder fields from a well-formed tool_calls response, and raises the
right exception type when a field is missing or when the model skips
tool_choice entirely.

What this does NOT verify: whether nvidia/qwen3.5-397b-a17b actually returns
this shape on a live call. That needs a real NVIDIA_API_KEY_1 in the
environment — run generate_questions.py against real judgment output once one
is available, and update the D56 comment in generate_questions.py with the
result either way.

Run: python3 feedback/smoke_test_nvidia_parsing.py
"""
import sys

from generate_questions import DEPTH_LADDER_KEYS, parse_nvidia_tool_response

VALID_ARGS = (
    '{"what": "w", "how": "h", "why": "y", "alternative": "a", '
    '"trade_off": "t", "constraint": "c", "reflection": "r"}'
)

VALID_RESPONSE = {
    "choices": [{
        "message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "depth_ladder_questions", "arguments": VALID_ARGS},
            }],
        }
    }]
}

MISSING_FIELD_RESPONSE = {  # valid JSON, but "reflection" absent
    "choices": [{"message": {"tool_calls": [{"function": {
        "name": "depth_ladder_questions",
        "arguments": '{"what": "w", "how": "h", "why": "y", "alternative": "a", '
                     '"trade_off": "t", "constraint": "c"}',
    }}]}}]
}

NO_TOOL_CALL_RESPONSE = {  # model answered in prose instead of honoring tool_choice
    "choices": [{"message": {"content": "Sure, here are some questions...", "tool_calls": None}}]
}


def check(label, fn):
    try:
        fn()
    except AssertionError as e:
        print(f"FAIL: {label} -- {e}")
        sys.exit(1)
    print(f"PASS: {label}")


def test_valid_response_parses_all_fields():
    result = parse_nvidia_tool_response(VALID_RESPONSE)
    assert set(result.keys()) == set(DEPTH_LADDER_KEYS), result.keys()


def test_missing_field_raises_value_error():
    try:
        parse_nvidia_tool_response(MISSING_FIELD_RESPONSE)
    except ValueError:
        return
    raise AssertionError("expected ValueError for a response missing 'reflection'")


def test_no_tool_call_raises_runtime_error():
    try:
        parse_nvidia_tool_response(NO_TOOL_CALL_RESPONSE)
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError when the model skips tool_choice")


if __name__ == "__main__":
    check("well-formed tool_calls parses all 7 depth-ladder fields", test_valid_response_parses_all_fields)
    check("missing field raises ValueError", test_missing_field_raises_value_error)
    check("no tool_calls raises RuntimeError with model content echoed", test_no_tool_call_raises_runtime_error)
    print(
        "\nAll structural checks passed. NOT verified: whether NVIDIA Build actually\n"
        "returns this shape for qwen/qwen3.5-397b-a17b on a live call (no NVIDIA_API_KEY\n"
        "in this session) -- see D56 in generate_questions.py."
    )
