# D61 (계속): 재현성을 구조화 필드 exact-match로 계산 — nvidia-build DECISIONS.md D9가
#   시도했지만 한 번도 커밋하지 못한 부분(세션 스크래치패드에서만 존재, 수동 보정).
#   WHY: D9는 자유서술 응답에 regex 패턴을 걸어 Jaccard 유사도로 재현성을 근사할 수밖에
#        없었다(모델 응답이 자연어라 정확 비교가 불가능했음). 이 repo의 새 벤치마크(채점,
#        MEAS-02 추출)는 둘 다 스키마강제 tool-calling(D56/D58 패턴)이라 출력이 이미
#        구조화 JSON이다 — regex 근사 없이 필드 단위 정확 비교가 가능하다.
#   COST: 자유서술 출력(예: generate_questions.py의 Depth Ladder 7필드 자체는 이미 구조화돼
#        있지만 그 "값"은 여전히 자유서술 문장)에는 이 exact-match가 너무 엄격할 수 있음 —
#        그런 경우 여전히 D9식 Jaccard/사람 대조가 필요하다(이 모듈은 그 대체가 아니라
#        "값 자체가 정수/enum처럼 이산적인 필드"에 한정된 도구).
#   EXIT: 자유서술 필드까지 다뤄야 하면 D9의 패턴매칭 Jaccard 함수를 이 모듈에 추가.
from __future__ import annotations


def _get_path(d: dict, path: str):
    node = d
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def field_agreement(run_a: dict, run_b: dict, fields: list) -> dict:
    """두 구조화 출력(동일 입력, 동일 모델, temperature=0 2회 호출)을 필드 단위로 비교한다.

    fields: 점(.)으로 중첩 경로를 표현한 dict 키 리스트, 예: "구조_인지도.score".
    반환: {"agree": [...], "disagree": [{"field","run_a","run_b"}, ...], "rate": float}
    """
    agree, disagree = [], []
    for path in fields:
        val_a, val_b = _get_path(run_a, path), _get_path(run_b, path)
        (agree if val_a == val_b else disagree).append(
            path if val_a == val_b else {"field": path, "run_a": val_a, "run_b": val_b}
        )
    rate = len(agree) / len(fields) if fields else 1.0
    return {"agree": agree, "disagree": disagree, "rate": rate}


def aggregate_reproducibility(pairs: list, fields: list) -> dict:
    """pairs: (run_a, run_b) dict 튜플 리스트(같은 입력을 2회 호출한 결과들).

    반환: {"pairs": [field_agreement 결과, ...], "mean_rate": float}
    """
    scored = [field_agreement(a, b, fields) for a, b in pairs]
    mean_rate = sum(s["rate"] for s in scored) / len(scored) if scored else 0.0
    return {"pairs": scored, "mean_rate": mean_rate}
