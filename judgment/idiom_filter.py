import json
import os

# D5: 관용 패턴 목록을 코드가 아니라 별도 상태 파일(idioms/<lang>/idiom_patterns.json)로 분리
#   WHY: 관용 패턴 목록은 계속 늘어나는 "데이터"이지 "로직"이 아님 —
#        코드와 분리해야 재귀 업데이트(idiom_hook.py)가 score_findings.py 재배포 없이 가능
#   COST: 상태 파일이 stale하면 같은 코드에서도 실행 결과가 달라짐(재현성 저하)
#   EXIT: idiom_patterns.json을 git에 커밋해 버전관리 → 이상 동작 시 git revert로 특정 시점 상태 복원
#
# D7: 관용 패턴 저장소를 언어별로 분리(judgment/idioms/<lang>/)
#   WHY: "관용 패턴"은 언어/프레임워크에 강하게 종속됨 — JS의 Context, Java의 static
#        Singleton, C의 전역 변수는 서로 다른 위험/설계의도 프로파일을 가짐. 하나로 합치면
#        한 언어에서 학습한 관용패턴이 다른 언어의 진짜 위험 신호까지 걸러버릴 수 있음
#   COST: 언어 수만큼 상태 파일/로그가 늘어나 관리 포인트 증가. 언어 판별(확장자 기반)이
#        틀리면(예: .h가 C인지 C++인지 애매) 잘못된 저장소를 참조할 위험
#   EXIT: 새 언어는 LANG_EXT_MAP에 확장자 매핑만 추가하면 됨. 언어 판별을 확장자가 아니라
#        AST/툴체인 기반으로 바꾸고 싶으면 resolve_lang()만 교체

IDIOMS_ROOT = os.path.join(os.path.dirname(__file__), "idioms")

LANG_EXT_MAP = {
    ".ts": "javascript", ".tsx": "javascript", ".js": "javascript", ".jsx": "javascript",
    ".py": "python",
    ".java": "java",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".swift": "swift",
}
SUPPORTED_LANGS = sorted(set(LANG_EXT_MAP.values()))

DOWNGRADE_MAP = {"상": "하", "중": "하", "하": "하"}


def resolve_lang(filename):
    _, ext = os.path.splitext(filename)
    return LANG_EXT_MAP.get(ext)


def patterns_path_for(lang):
    return os.path.join(IDIOMS_ROOT, lang, "idiom_patterns.json")


def log_path_for(lang):
    return os.path.join(IDIOMS_ROOT, lang, "idiom_feedback_log.jsonl")


def load_patterns(lang):
    path = patterns_path_for(lang)
    if not os.path.exists(path):
        return {"promotion_threshold": 3, "patterns": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def apply_idiom_filter(findings):
    """finding["file"]의 확장자로 언어를 판별해 그 언어 저장소의 confirmed 패턴만 적용한다.

    candidate 상태인 패턴은 적용하지 않는다 — threshold 미달 신호를 신뢰하지 않는다는
    판단 블록의 원칙(D6) 그대로. 언어를 판별 못하면(확장자 미매핑) 필터를 건너뛴다.
    """
    cache = {}
    for finding in findings:
        pattern_key = finding.get("pattern_key")
        file = finding.get("file")
        if not pattern_key or not file:
            continue

        lang = resolve_lang(file)
        if lang is None:
            finding["idiom_note"] = f"언어 미판별(확장자 미지원) — {file} 관용 패턴 필터 건너뜀"
            continue

        if lang not in cache:
            cache[lang] = load_patterns(lang)
        confirmed_lookup = {p["id"]: p for p in cache[lang]["patterns"] if p["status"] == "confirmed"}

        if pattern_key in confirmed_lookup:
            p = confirmed_lookup[pattern_key]
            original = finding["question_value"]
            finding["question_value"] = DOWNGRADE_MAP.get(original, original)
            finding["idiom_filtered"] = True
            finding["idiom_lang"] = lang
            finding["idiom_note"] = (
                f"[{lang}] 관용 패턴으로 판단(pattern={pattern_key}, "
                f"confirmations={p['confirmations']}) — 질문가치 {original}→{finding['question_value']}"
            )
            if "priority" in finding:
                finding["priority"] = f"{finding['priority']} → 관용 패턴 필터 적용됨(우선순위 낮음)"
    return findings
