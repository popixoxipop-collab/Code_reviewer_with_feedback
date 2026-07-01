# D54: Project Ownership Verification 인터뷰(examples/lms/d_plan/, POC 발표문)에서 쓴
#   3축(구조_인지도/트레이드오프_인지도/대안_탐색_능력) 점수가 지금까지는 레벨별 정의 없이
#   1~5 정수만 매겨져 있었다 — subrubric.py(D27)가 정적분석 3축(design_intent/
#   question_value/risk)에 대해 이미 겪은 문제("근거 없는 한 줄 판정")를 인터뷰 채점 쪽도
#   똑같이 겪고 있었다는 뜻.
#   WHY: 사용자가 축별 5단계 레벨 설명을 명시적으로 제공 — 이걸 파이썬 dict로 코드화해두면
#        ①미래 인터뷰 채점이 이 기준을 그대로 재사용 가능 ②이미 매긴 점수(9개: 3개 의사결정
#        × 3축)를 레벨 텍스트와 실제 대조해 "왜 이 점수인가"를 사후적으로 검증 가능해짐.
#        subrubric.py처럼 서브축으로 더 잘게 쪼개지는 않음 — 이건 정적분석 신호가 아니라
#        사람(LLM)이 대화를 읽고 총체적으로 판단하는 축이라 잘게 쪼갤 근거 신호가 없다.
#        대신 "왜 이 레벨인가"를 텍스트 근거(evidence)와 함께 명시하도록 강제한다.
#   COST: 레벨 설명 자체가 사용자가 준 텍스트를 그대로 옮긴 것이라, "3점과 4점의 경계가
#        어디인가" 같은 애매한 케이스(예: 반례에 빠르게 반응했지만 완전한 이해는 아닌 경우)의
#        판정은 여전히 채점자 재량. 서브루브릭처럼 하위 신호로 더 분해하지 않아 판정 재현성은
#        subrubric.py보다 낮음
#   EXIT: 경계 케이스가 반복되면 각 레벨을 다시 2~3개 하위 신호로 쪼개 subrubric.py 방식
#        (근거 필드 → 가중합)으로 승격 가능. RUBRIC 딕셔너리 구조만 유지하면 됨

RUBRIC = {
    "구조_인지도": {
        5: "구성 요소 간 관계와 데이터 흐름을 정확히 설명",
        4: "흐름은 맞지만 일부 연결 관계 불명확",
        3: "각 구성 요소는 알지만 연결 관계 설명 불가",
        2: "개별 요소 설명은 가능하나 전체 구조 파악 안 됨",
        1: '"그냥 이렇게 했습니다" 수준',
    },
    "트레이드오프_인지도": {
        5: "반례를 스스로 먼저 언급하거나, 던졌을 때 즉각 인지",
        4: "반례를 이해하고 부분적 대응 가능",
        3: "반례를 들었을 때 이해는 하나 대안 없음",
        2: '반례를 인지했지만 "문제없다"고 주장',
        1: "반례를 던져도 이해 불가",
    },
    "대안_탐색_능력": {
        5: "구체적인 기술적 대안을 즉시 제시",
        4: "대안 방향은 명확하나 구현 방법 일부 불명확",
        3: "대안이 존재한다는 것은 알지만 구체화하지 못함",
        2: "대안 탐색 시도 자체를 하지 않고 현재 방식을 그대로 고수",
        1: "대안이라는 개념 자체를 이해하지 못함",
    },
}

AXES = tuple(RUBRIC.keys())


def describe(axis, score):
    """axis(3개 중 하나)의 score(1~5) 레벨 설명 텍스트를 반환."""
    if axis not in RUBRIC:
        raise ValueError(f"unknown axis '{axis}', must be one of {AXES}")
    if score not in RUBRIC[axis]:
        raise ValueError(f"score must be 1~5, got {score}")
    return RUBRIC[axis][score]


def score_card(axis, score, evidence):
    """채점 결과 1건을 감사 가능한 형태로 만든다 — subrubric.py의 finding["subrubric"]와
    동일한 목적(점수만 있고 근거가 없는 상태를 막는 것)."""
    return {
        "axis": axis,
        "score": score,
        "criterion": describe(axis, score),
        "evidence": evidence,
    }
