import json
import os
import sys

# D11: 피드백 블록 7단계 질문 생성을 실제 LLM 호출(Anthropic tool-use)로 자동화
#   WHY: 지금까지는 사람이 findings.md를 수기로 채웠음(README "다음 단계" 3번) — 즉흥 생성
#        편차 문제(D1)를 코드 레벨에서 해소하려면 스키마를 tool-use로 강제해야 함
#   COST: Anthropic API 키/네트워크 의존성 생김, 호출당 비용 발생, 오프라인 실행 불가
#   EXIT: ANTHROPIC_API_KEY 없으면 조용히 실패하지 않고 여기서 즉시 중단. API 없이 쓰려면
#        feedback/depth_ladder_template.md의 수기 체크리스트로 되돌아가면 됨(코드 삭제 불필요)
#
# 검증 상태(정직하게 기록): 이 스크립트는 문법/인자파싱/스키마 강제 로직까지는 실행해 확인했으나,
# 실제 Anthropic API를 호출한 결과(생성된 질문의 품질)는 이 세션에서 검증하지 않았다
# (API 키/과금이 필요해 실행 보류). README "알려진 한계"에 동일하게 기록되어 있다.

try:
    import anthropic
except ImportError:
    anthropic = None

DEPTH_LADDER_KEYS = ["what", "how", "why", "alternative", "trade_off", "constraint", "reflection"]

DEPTH_LADDER_TOOL = {
    "name": "depth_ladder_questions",
    "description": "판단 블록 finding에 대한 Ownership Cycle 7단계 질문을 전부 채워 반환한다. "
                    "하나라도 비면 안 된다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "what": {"type": "string", "description": "무엇을 했는지 사실 확인 질문"},
            "how": {"type": "string", "description": "구체적 구현 메커니즘을 묻는 질문"},
            "why": {"type": "string", "description": "그 방식을 선택한 이유를 묻는 질문"},
            "alternative": {"type": "string", "description": "대안을 인지하고 있는지 묻는 질문"},
            "trade_off": {"type": "string", "description": "선택지 간 트레이드오프 비교를 요구하는 질문"},
            "constraint": {"type": "string", "description": "제약조건(시간/기술/팀) 반영 여부를 묻는 질문"},
            "reflection": {"type": "string", "description": "자기 수정을 유도하는 질문"},
        },
        "required": DEPTH_LADDER_KEYS,
    },
}

MODEL = os.environ.get("FEEDBACK_MODEL", "claude-sonnet-5")


def build_prompt(finding):
    return (
        "다음은 코드 리뷰 판단 블록이 뽑아낸 finding이다. 이 finding을 근거로 학생/지원자의 "
        "코드 이해도(Ownership)를 검증하는 Depth Ladder 7단계 질문을 생성하라. "
        "각 질문은 반례나 트레이드오프를 스스로 떠올리게 유도해야 하며, 단순 정답 확인 질문이면 안 된다. "
        "finding이 이미 관용 패턴으로 판정되어 강등된 경우(idiom_filtered=true)에는 "
        "질문 난이도를 낮추고 짧게 생성하라.\n\n"
        f"finding: {finding.get('finding')}\n"
        f"file: {finding.get('file')}\n"
        f"design_intent: {finding.get('design_intent')}\n"
        f"priority: {finding.get('priority')}\n"
        f"idiom_filtered: {finding.get('idiom_filtered', False)}\n"
    )


def generate_for_finding(client, finding):
    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        tools=[DEPTH_LADDER_TOOL],
        tool_choice={"type": "tool", "name": "depth_ladder_questions"},
        messages=[{"role": "user", "content": build_prompt(finding)}],
    )
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "depth_ladder_questions":
            result = block.input
            missing = [k for k in DEPTH_LADDER_KEYS if not result.get(k)]
            if missing:
                raise ValueError(f"7단계 중 누락된 필드: {missing}")
            return result
    raise RuntimeError("tool_use 블록을 찾지 못함 — 모델이 스키마를 안 지킴")


def to_markdown(results_with_findings):
    lines = ["# 피드백 블록 자동 생성 결과 (Depth Ladder 7단계)\n"]
    labels = {
        "what": "What", "how": "How", "why": "Why", "alternative": "Alternative",
        "trade_off": "Trade-off", "constraint": "Constraint", "reflection": "Reflection",
    }
    for item in results_with_findings:
        lines.append(f"## {item['finding_id']}\n")
        if "error" in item:
            lines.append(f"> 생성 실패: {item['error']}\n")
            continue
        for i, key in enumerate(DEPTH_LADDER_KEYS, start=1):
            lines.append(f"{i}. **{labels[key]}** — {item['questions'][key]}")
        lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("usage: generate_questions.py <judgment_output.json> [top_n] [--md]", file=sys.stderr)
        sys.exit(1)
    if anthropic is None:
        print("anthropic 패키지가 없습니다. `pip install anthropic` 실행 후 재시도하세요.", file=sys.stderr)
        sys.exit(1)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY 환경변수가 없습니다. 조용히 실패하지 않고 여기서 중단합니다.", file=sys.stderr)
        sys.exit(1)

    args = [a for a in sys.argv[1:] if a != "--md"]
    want_md = "--md" in sys.argv[1:]

    with open(args[0], encoding="utf-8") as f:
        data = json.load(f)
    top_n = int(args[1]) if len(args) > 1 else None

    findings = data["findings"]
    if top_n:
        findings = findings[:top_n]

    client = anthropic.Anthropic(api_key=api_key)
    results = []
    for finding in findings:
        try:
            questions = generate_for_finding(client, finding)
            results.append({"finding_id": finding["id"], "questions": questions})
        except Exception as e:
            results.append({"finding_id": finding["id"], "error": str(e)})

    if want_md:
        print(to_markdown(results))
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
