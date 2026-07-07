"""D70: examples/*/*/judgment_output.json 전체를 언어별로 집계해 리포트한다.

WHY: mine_repo.py로 언어마다 finding을 뽑아도, "언어별로 실제 뭐가 나왔는지" 한눈에
     비교할 방법이 없으면 사용자가 요청한 "언어별로 정리"가 산출물로 남지 않는다.
COST: finding-type 분류는 id 접두어(cognition-isolation/architecture-diffusion/
     tier-b-risk/repeated-pattern) 문자열 매치라 score_findings.py의 id 포맷이
     바뀌면 이 스크립트도 같이 바뀌어야 한다.
EXIT: 새 finding 타입이 추가되면 FINDING_TYPE_PREFIXES에 한 줄 추가.

usage: python3 dataset/corpus_report.py
"""
import glob
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES_DIR = os.path.join(REPO_ROOT, "examples")

sys.path.insert(0, os.path.join(REPO_ROOT, "judgment"))
from idiom_filter import resolve_lang  # noqa: E402

# D75/D76: repo 태그(폴더명) 하나로 그 repo의 finding 전부를 그 언어로 집계했는데,
#   two_tier_scan.py의 SRC_EXTS는 언어 무관하게 확장자로만 파일을 훑는다 -- 실측 확인:
#   examples/python/API-Manager는 Django static/js/ 아래 번들된 서드파티 JS가, Java repo
#   Modern-API-Development는 자체 React 프론트엔드가 finding으로 잡혀 repo 태그 언어
#   통계에 섞여 들어갔다(D75, 21/120건=17.5%). D76에서 근본 수정 2가지를 적용:
#   (1) two_tier_scan.py의 SKIP_DIRS에 static/vendor 추가로 서드파티 자산 자체를 차단
#   (2) score_findings.py가 각 finding에 lang 필드를 스키마로 직접 기록(_tag_lang())
#   이 스크립트는 이제 finding["lang"](스키마 제공, .h 파일도 내용 기반 재판정 포함)을
#   최우선으로 쓰고, 그 필드가 없는 구 스키마 fixture(D76 이전에 생성된 lms/study_match)만
#   judgment/idiom_filter.py의 resolve_lang()으로 하위호환 계산한다.
LANG_TAG_TO_RESOLVE_LANGS = {
    "javascript": {"javascript"},
    "python": {"python"},
    "java": {"java"},
    "c_cpp": {"c", "cpp"},
}

FINDING_TYPE_PREFIXES = [
    "cognition-isolation",
    "architecture-diffusion",
    "tier-b-risk",
    "repeated-pattern",
]

# D70: 기존 fixture(examples/lms/, examples/study_match/)는 mine_repo.py 도입 전부터
#   있던 "flat" 레이아웃(examples/<repo>/judgment_output*.json, 언어 중첩 없음) -- 둘 다
#   JS/TS라 언어 구분이 필요 없었기 때문. mine_repo.py는 이번에 새로 "examples/<lang>/<repo>/..."
#   중첩 레이아웃을 도입했으므로, 두 레이아웃을 모두 인식해야 기존 12개 finding이 리포트에서
#   누락되지 않는다. 새 레이아웃으로 기존 fixture를 옮기는(breaking) 대신 매핑으로 해소.
FLAT_LAYOUT_LANG = {
    "lms": "javascript",
    "study_match": "javascript",
    "shadowbroker": "python+javascript",  # judgment_output.json 없음(scan_output.json만) -- 집계 제외됨
}


def classify(finding_id):
    for prefix in FINDING_TYPE_PREFIXES:
        if finding_id.startswith(prefix):
            return prefix
    return "other"


def main():
    # 두 레이아웃 다 훑는다: flat(examples/<repo>/judgment_output*.json) +
    # nested(examples/<lang>/<repo>/judgment_output*.json)
    paths = sorted(set(
        glob.glob(os.path.join(EXAMPLES_DIR, "*", "judgment_output*.json"))
        + glob.glob(os.path.join(EXAMPLES_DIR, "*", "*", "judgment_output*.json"))
    ))

    by_lang = {}
    noise = []  # (repo_tag_lang, actual_lang, repo, finding_id, file)
    for path in paths:
        rel = os.path.relpath(path, EXAMPLES_DIR)
        parts = rel.split(os.sep)
        if len(parts) == 2:  # flat: <repo>/file.json
            repo = parts[0]
            lang = FLAT_LAYOUT_LANG.get(repo, "unknown")
        else:  # nested: <lang>/<repo>/file.json
            lang, repo = parts[0], parts[1]
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        findings = data.get("findings", [])
        entry = by_lang.setdefault(lang, {"repos": set(), "findings": 0, "types": {}})
        entry["repos"].add(repo)

        expected = LANG_TAG_TO_RESOLVE_LANGS.get(lang)
        for finding in findings:
            fname = finding.get("file")
            # D76: 스키마에 lang이 이미 있으면(신규 fixture) 그걸 그대로 쓴다 -- .h 파일
            # 내용 기반 재판정까지 포함된 정확한 값. 없으면(구 fixture) 파일명만으로 재계산.
            if "lang" in finding:
                actual_lang = finding["lang"]
            else:
                actual_lang = resolve_lang(fname) if fname else None
            if expected is not None and actual_lang is not None and actual_lang not in expected:
                noise.append((lang, actual_lang, repo, finding.get("id"), fname))
                continue  # 이 언어의 통계에서 제외 -- repo 태그와 실제 파일 언어가 다름
            entry["findings"] += 1
            t = classify(finding.get("id", ""))
            entry["types"][t] = entry["types"].get(t, 0) + 1

    print(f"{'language':<12} {'repos':>5} {'findings':>9}  types")
    print("-" * 70)
    total_findings = 0
    for lang in sorted(by_lang):
        e = by_lang[lang]
        total_findings += e["findings"]
        type_str = ", ".join(f"{k}={v}" for k, v in sorted(e["types"].items())) or "(none)"
        print(f"{lang:<12} {len(e['repos']):>5} {e['findings']:>9}  {type_str}")
    print("-" * 70)
    print(f"total: {len(by_lang)} languages, {total_findings} findings (cross-language noise 제외)")

    print("\nrisk-trigger coverage (tier-b-risk present?):")
    for lang in sorted(by_lang):
        has_risk = "tier-b-risk" in by_lang[lang]["types"]
        print(f"  {lang:<12} {'yes' if has_risk else 'NO -- structural-only'}")

    if noise:
        print(f"\ncross-language noise excluded ({len(noise)}건 -- repo 태그 언어와 실제 파일 확장자가 다름):")
        for repo_lang, actual_lang, repo, fid, fname in noise:
            print(f"  [{repo_lang} repo, actual={actual_lang}] {repo}: {fid} ({fname})")


if __name__ == "__main__":
    main()
