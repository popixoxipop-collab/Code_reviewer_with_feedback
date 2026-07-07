# D65 (Phase 2 재설계, 기획명세서_AI기반_프로젝트교육품질관리플랫폼.xlsx 00시트 "확정 설계
#   결정" 그대로): MEAS-02 Decision Point 추출을 순수 LLM으로 구현 — 정적분석
#   (cognition/two_tier_scan.py + judgment/score_findings.py·subrubric.py) 미사용.
#   WHY: 팀이 이미 "Decision Point 추출 = 순수 LLM(정적 분석 미사용) — AST·CodeSearchNet
#        매칭 방식은 폐기. 코드 조각+요구사항을 LLM에 투입해 판단 지점 추출"로 확정(Locked)함.
#        이 저장소의 cognition/judgment 정적분석 블록은 팀이 이미 폐기하기로 결정한 방식이라
#        재사용·통합 대상이 아니다(이전 계획의 하이브리드 Method B 설계는 폐기됨).
#   COST: 정적분석 대비 결정론성이 없음(같은 입력이라도 모델이 다른 지점을 뽑을 수 있음) —
#        benchmarks/meas02_run_benchmark.py의 재현성 축이 정확히 이 COST를 실측한다.
#        API 키/네트워크 의존, 호출당 비용 발생.
#   EXIT: 팀이 정적분석 재도입(또는 하이브리드)을 결정하면 score_findings.py/subrubric.py와
#        병행 비교를 이 모듈과 별도로 재설계.
#
# D69: 기획명세서 00시트가 "미확정/리스크"로 명시한 "Qwen 스펙(컨텍스트 길이·가격) 미검증 —
#   락 전 실측 필요"를, 이 모듈의 벤치마크 실행(코드조각+요구사항을 실제 이 shape로 호출)이
#   부산물로 함께 검증한다 — 결과 문서에 이 대응관계를 명시한다.
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "feedback"))

try:
    from nvidia_client import NvidiaRotatingClient
    from nvidia_key_pool import NvidiaKeyPool
except ImportError:
    NvidiaRotatingClient = None
    NvidiaKeyPool = None

# 기획명세서 01시트 ③단계 그대로의 출력 스키마: Decision Point 세트[파일·함수·판단유형·근거·연결요구사항]
DECISION_POINT_TOOL = {
    "name": "extract_decision_points",
    "description": (
        "코드 조각과 프로젝트 요구사항을 보고, 설계 판단(design judgment)이 개입된 지점을 "
        "전부 찾아 Decision Point 세트로 추출한다. 단순 문법/스타일 지적이 아니라 "
        "'왜 이렇게 설계했는가'를 물을 가치가 있는 지점만 포함한다."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "decision_points": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "description": "파일명"},
                        "function": {"type": "string", "description": "함수/메서드명(모듈 스코프면 파일명과 동일하게)"},
                        "judgment_type": {
                            "type": "string",
                            "description": "예: 아키텍처 선택/에러 처리/데이터 모델링/성능 트레이드오프/보안 판단/상태 관리 방식",
                        },
                        "evidence": {"type": "string", "description": "이 지점이 판단 지점이라는 근거(실제 코드 인용 포함)"},
                        "linked_requirement": {"type": "string", "description": "연결되는 요구사항 문구(없으면 빈 문자열)"},
                    },
                    "required": ["file", "function", "judgment_type", "evidence"],
                },
            }
        },
        "required": ["decision_points"],
    },
}


def _as_openai_tool(anthropic_tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": anthropic_tool["name"],
            "description": anthropic_tool["description"],
            "parameters": anthropic_tool["input_schema"],
        },
    }


PROVIDER = os.environ.get("FEEDBACK_PROVIDER", "nvidia")
_DEFAULT_MODEL = "qwen/qwen3-next-80b-a3b-instruct" if PROVIDER == "nvidia" else "claude-sonnet-5"
MODEL = os.environ.get("MEAS02_MODEL", os.environ.get("FEEDBACK_MODEL", _DEFAULT_MODEL))


def build_extraction_prompt(file_name: str, code_snippet: str, requirements: str, focus_area) -> str:
    focus_line = f"\n이번 회차 포커스: {focus_area}\n" if focus_area else ""
    return (
        "다음 코드 조각을 분석해서, 설계 판단이 개입된 지점(Decision Point)을 전부 추출하라. "
        "판단 지점이란 '왜 이렇게 했는가'를 물었을 때 정답이 하나로 정해지지 않고 대안이 "
        "실재하는 지점이다(예: 이 자료구조를 쓴 이유, 이 에러를 이렇게 처리한 이유, 이 상태를 "
        "여기 둔 이유). 단순 문법 오류나 스타일 지적은 포함하지 마라. 각 지점마다 근거로 실제 "
        "코드를 인용하고, 아래 요구사항과 연결되는 지점이면 어느 요구사항인지 명시하라."
        f"{focus_line}\n"
        f"파일: {file_name}\n\n"
        f"요구사항:\n{requirements}\n\n"
        f"코드:\n```\n{code_snippet}\n```\n"
    )


def _validate_extraction(result: dict) -> dict:
    points = result.get("decision_points")
    if not isinstance(points, list):
        raise ValueError("decision_points가 배열이 아님")
    for i, p in enumerate(points):
        for key in ("file", "function", "judgment_type", "evidence"):
            if not p.get(key):
                raise ValueError(f"decision_points[{i}].{key}가 비어있음")
    return result


def parse_nvidia_tool_response(response: dict) -> dict:
    choice = response["choices"][0]["message"]
    for call in choice.get("tool_calls") or []:
        if call["function"]["name"] == "extract_decision_points":
            result = json.loads(call["function"]["arguments"])
            return _validate_extraction(result)
    raise RuntimeError(
        "tool_calls를 찾지 못함 — 모델이 이 요청에서 tool_choice를 지키지 않았을 수 있음. "
        f"content={choice.get('content')!r}"
    )


def rank_by_focus(decision_points: list, focus_area) -> list:
    """기획명세서 01시트 ③단계의 "포커스 매칭 가중·랭킹"을 반영한다.

    focus_area가 없으면 원 순서 그대로. 있으면 judgment_type/evidence에 focus_area
    키워드를 포함한 항목을 앞으로 정렬한다 — 스펙에 구체적 가중 알고리즘이 없어 가장 단순한
    해석(키워드 매칭)으로 시작하고, 실측 후 필요하면 정교화한다.
    """
    if not focus_area:
        return decision_points

    def _matches(p):
        haystack = f"{p.get('judgment_type', '')} {p.get('evidence', '')}"
        return focus_area.lower() in haystack.lower()

    matched = [p for p in decision_points if _matches(p)]
    unmatched = [p for p in decision_points if not _matches(p)]
    return matched + unmatched


def extract_decision_points(client, file_name: str, code_snippet: str, requirements: str, focus_area=None) -> dict:
    response = client.chat(
        model=MODEL,
        messages=[{"role": "user", "content": build_extraction_prompt(file_name, code_snippet, requirements, focus_area)}],
        tools=[_as_openai_tool(DECISION_POINT_TOOL)],
        tool_choice={"type": "function", "function": {"name": "extract_decision_points"}},
        max_tokens=2048,
        temperature=0.0,
    )
    result = parse_nvidia_tool_response(response)
    result["decision_points"] = rank_by_focus(result["decision_points"], focus_area)
    return result


def _build_client():
    if NvidiaRotatingClient is None:
        print("nvidia_client 모듈을 찾을 수 없습니다.", file=sys.stderr)
        sys.exit(1)
    try:
        pool = NvidiaKeyPool.from_env()
    except ValueError as e:
        print(f"{e}", file=sys.stderr)
        sys.exit(1)
    return NvidiaRotatingClient(pool=pool)


def main():
    if len(sys.argv) < 3:
        print("usage: meas02_decision_point_extractor.py <source_file> <requirements.txt> [focus_area]", file=sys.stderr)
        sys.exit(1)
    source_file, requirements_file = sys.argv[1], sys.argv[2]
    focus_area = sys.argv[3] if len(sys.argv) > 3 else None

    with open(source_file, encoding="utf-8", errors="ignore") as f:
        code_snippet = f.read()
    with open(requirements_file, encoding="utf-8") as f:
        requirements = f.read()

    client = _build_client()
    result = extract_decision_points(client, os.path.basename(source_file), code_snippet, requirements, focus_area)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
