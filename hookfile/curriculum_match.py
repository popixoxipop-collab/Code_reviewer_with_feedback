"""D129 -- 실제 커리큘럼 매칭기 (curriculum-fixed 트랙 전용).

_find_curriculum_ref()(generate_hook_file.py, baseline 트랙)는 unit_map의 첫 항목만
무조건 반환하는 1차 placeholder였다(D121이 이미 자체 문서화). 이 모듈이 그 자리를
대신할 "실제" 매칭을 구현한다 -- D127 종합 리포트에서 4라운드 22개 규칙 전부 동일
인용이 나온다는 게 실측 확인된 뒤, 사용자 지시로 baseline(대조군)과 나란히 상시
병행 생성하는 curriculum-fixed 트랙에서만 쓰인다.

WHY 키워드 겹침(결정론, LLM 콜 없음)을 택했나:
  P02와 같은 원칙(콜 0건)을 유지하고, "왜 이 concept이 뽑혔는지"를 겹친 토큰
  그대로 보여줘 사람이 감사 가능하게 하기 위해서다. LLM 매칭도 가능하지만 그러면
  unit_map을 다시 프롬프트에 태워야 하고(비용 발생) 결과가 검사불가 블랙박스가 된다.
COST: 짧은 키워드 겹침은 재현율이 낮다 -- 특히 P02 코드채널 finding(fan-in/허브
  구조 등 아키텍처 취약점)은 이 커리큘럼(자바 문법 입문, Unit01~06 concept 이름
  전수 확인 결과 변수/자료형/연산자/조건문/반복문/String/Scanner뿐)에 대응 개념이
  거의 없다 -- 매칭 없음(None)이 흔하게 나올 것으로 예상되고, 이는 매칭기 결함이
  아니라 커리큘럼 커버리지 자체의 한계다(가짜로 아무거나 붙이지 않는 게 이 모듈의
  핵심 설계 원칙).
EXIT: 재현율을 올리려면 (a) 커리큘럼에 실제 소프트웨어 설계원칙 유닛을 추가하거나
  (b) 결정론 겹침 대신 LLM 기반 의미매칭으로 바꾸면 됨 -- 이 함수의 시그니처만
  유지하면 generate_hook_file.py 쪽은 무변경.

알려진 데이터 결함 하나(이 스코프에서 원인 수정 안 함): unit_map의 Unit05("조건문")와
Unit06("반복문")의 concepts가 완전히 동일하다(M2 청킹 단계 버그로 추정) -- 이 유닛이
매칭되면 match_basis에 겹친 토큰이 그대로 드러나므로 결과를 읽는 사람이 알아챌 수
있게만 해둔다(추가 은폐 없음).
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AUDIT_PATH = REPO / "benchmarks" / "curriculum_provenance_audit.json"

_STOPWORDS = {
    "으로", "에서", "하는", "있는", "것을", "합니다", "한다", "이다", "것이다",
    "위해", "때", "경우", "그리고", "그런데", "이런", "저런", "통해", "대한",
}


def _tokenize(text):
    if not text:
        return set()
    raw = re.findall(r"[\w가-힣]+", text.lower())
    return {t for t in raw if len(t) >= 2 and t not in _STOPWORDS}


def _load_grounded_concept_ids(audit_path=AUDIT_PATH):
    """tier1_pass=true 이거나 tier2에서 grounded=true인 concept id 집합.
    §4.1 선행 게이트("검증 통과 concept만 인용")의 실제 구현 -- D121이 문서화만
    해두고 미구현이던 부분."""
    if not audit_path.exists():
        return set()
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    grounded = {item["id"] for item in audit.get("tier1_detail", []) if item.get("tier1_pass")}
    grounded |= {item["id"] for item in audit.get("tier2_detail", []) if item.get("grounded")}
    return grounded


_MAX_DOC_FREQ_RATIO = 0.10  # 이 비율 이상의 concept에 등장하는 토큰은 변별력 없음(예: "java","코드")
_MIN_DISTINCTIVE_OVERLAP = 2  # 흔한 토큰 제거 후에도 최소 2개는 겹쳐야 매칭 인정(D129 1차 실측: 임계 1은 스퓨리어스)


def build_concept_index(unit_map, audit_path=AUDIT_PATH):
    """unit_map x audit 교차 -- 검증된(grounded) concept만 매칭 후보로 인덱싱.
    concept_id 재구성(concepts:{unit_id}:{1-based 순번})이 audit의 id 스킴과
    정확히 일치하는지 두 파일 여러 항목 교차로 확인함(예: concepts:01:4 ==
    unit_map['01']['concepts'][3] == '변수 초기화 필요성').

    참고(3번째 알려진 데이터 결함): audit은 236개 concept을 참조하지만 현재
    unit_map 캐시엔 155개뿐이다(unit_map/audit이 서로 다른 M2 스냅샷) -- 존재하지
    않는 concept_id는 자연히 인덱싱 대상에서 빠진다(별도 처리 불필요, 조용히
    스킵되는 게 올바른 동작).

    D129 1차 실측에서 발견: 단순 토큰 겹침(임계=1)은 "java"/"코드" 같은 흔한 토큰
    하나만 겹쳐도 스퓨리어스 매칭을 만들었다(예: 모든 *.java finding이 우연히
    "Main 클래스 생성" concept에 매칭). document frequency(이 concept 집합 내에서
    등장 비율)로 흔한 토큰을 걸러내는 IDF 비슷한 필터를 추가해 재수집."""
    grounded_ids = _load_grounded_concept_ids(audit_path)
    raw = []
    for unit_id, unit in unit_map.items():
        for i, concept in enumerate(unit.get("concepts", []), 1):
            concept_id = f"concepts:{unit_id}:{i}"
            if concept_id not in grounded_ids:
                continue
            text = " ".join(filter(None, [
                concept.get("name", ""), concept.get("summary", ""), concept.get("evidence", ""),
            ]))
            raw.append({
                "concept_id": concept_id, "unit_id": unit_id, "unit_title": unit.get("unit_title", ""),
                "concept_name": concept.get("name", ""), "source_pages": concept.get("source_pages", []),
                "raw_tokens": _tokenize(text),
            })
    if not raw:
        return []

    n = len(raw)
    doc_freq = {}
    for entry in raw:
        for tok in entry["raw_tokens"]:
            doc_freq[tok] = doc_freq.get(tok, 0) + 1
    common_tokens = {tok for tok, df in doc_freq.items() if df / n > _MAX_DOC_FREQ_RATIO}

    index = []
    for entry in raw:
        entry["tokens"] = entry.pop("raw_tokens") - common_tokens
        index.append(entry)
    return index, common_tokens


def find_curriculum_ref_fixed(candidate_text, unit_map, concept_index=None, common_tokens=None, audit_path=AUDIT_PATH):
    """candidate_text(finding 텍스트 또는 인터뷰 criterion+evidence)와 검증된 concept
    중, 흔한 토큰을 제외한 겹침이 가장 큰 것을 반환. 겹침이 _MIN_DISTINCTIVE_OVERLAP
    미만이면 None -- 억지 매칭 금지가 이 모듈의 핵심 설계 원칙(대신 아무 인용 없음)."""
    if concept_index is None:
        concept_index, common_tokens = build_concept_index(unit_map, audit_path)
    if not concept_index:
        return None
    cand_tokens = _tokenize(candidate_text)
    if common_tokens:
        cand_tokens = cand_tokens - common_tokens
    if not cand_tokens:
        return None
    best, best_overlap = None, 0
    for entry in concept_index:
        overlap = len(cand_tokens & entry["tokens"])
        if overlap > best_overlap:
            best, best_overlap = entry, overlap
    if best is None or best_overlap < _MIN_DISTINCTIVE_OVERLAP:
        return None
    matched = sorted(cand_tokens & best["tokens"])
    return {
        "unit": best["unit_id"], "unit_title": best["unit_title"],
        "concept_name": best["concept_name"], "source_pages": best["source_pages"],
        "match_basis": f"keyword-overlap(n={best_overlap}: {', '.join(matched[:5])})",
    }
