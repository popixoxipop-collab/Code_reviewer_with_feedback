import re
import os
import sys
import json

# D2: Tier A(구조 스캔) / Tier B(위험 트리거 내용 스캔) 이원화
#   WHY: 그래프/import 스캔(저비용)만으로는 handleFirestoreError 같은 "내용 기반" 이슈를 못 잡음
#        (2026-07-01 Study-Match- 실측: 그래프에서 fan-in 최고였던 firebase.ts가 아니라
#         파일 전체를 읽어야만 보이는 인증정보 유출이 진짜 위험이었음)
#   COST: 위험 키워드 사전에 없는 새로운 패턴의 이슈는 여전히 놓침. 정규식 기반이라 오탐 발생
#   EXIT: RISK_TRIGGERS에 항목 추가/수정. 또는 judgment 블록의 tier_b_hook 재귀 업데이트로 대체
#
# D12: fan-in 계산을 (src,dst) 파일쌍 단위로 dedupe한 뒤 집계 (이중계산 버그 수정)
#   WHY: 같은 모듈을 import문 여러 줄로 나눠 쓰면(예: AuthScreen.tsx가 '../firebase'를 두 줄로
#        나눠 import) 기존 로직은 import문 개수만큼 fan-in을 올렸음(firebase.ts 실측 7→8 부풀림)
#   COST: 정말로 같은 파일을 "두 가지 다른 이유로" import했다는 정보(다중성)는 사라짐 —
#        지금은 "연결되어 있다/없다"만 본다는 판단 블록 요구사항엔 dedupe가 맞는 선택
#   EXIT: 다중성 자체가 필요해지면 edges를 (src,dst,count) 튜플로 바꾸면 됨, fan_in 계산 로직은 불변
#
# D13: 인지 블록을 JS/TS 외 언어(Python/Java/C/C++)로 확장
#   WHY: judgment/idiom_filter.py의 LANG_EXT_MAP은 이미 다국어를 가정하는데 정작 인지 블록의
#        SRC_EXTS는 JS/TS뿐이라 다른 언어 repo를 스캔하면 파일이 전부 누락되는 불일치가 있었음
#   COST: 언어마다 import 구문이 달라 언어별 정규식이 늘어남(Swift는 로컬 파일간 import가 없어
#        구조 스캔 자체가 의미 없음 — 모듈 단위 가시성이라 파일 단위 그래프로 표현 불가, 문서화된 한계)
#   EXIT: 새 언어는 EXT_GROUPS에 확장자 추가 + extract_targets_for_file에 분기 추가

SRC_EXTS = (
    ".ts", ".tsx", ".js", ".jsx",
    ".py",
    ".java",
    ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp",
    ".swift",
)
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv"}

JS_EXTS = (".ts", ".tsx", ".js", ".jsx")
C_LIKE_EXTS = (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp")

JS_IMPORT_RE = re.compile(r"import\s+.*?from\s+['\"](.+?)['\"]")
PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))", re.MULTILINE)
JAVA_IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w\.]+)\s*;", re.MULTILINE)
C_INCLUDE_RE = re.compile(r'#include\s*"([^"]+)"')  # 따옴표 include만 로컬로 간주(<> 시스템 헤더는 제외)

AUTH_KEYWORDS = re.compile(r"\b(uid|email|token|password|apiKey|currentUser|authInfo)\b")
STRINGIFY_RE = re.compile(r"JSON\.stringify")
THROW_RE = re.compile(r"\bthrow\b")
# D17: eval( 앞이 '.'이면(메서드 호출) 제외 — RunPod_Deploy_Agent 실측: "model.eval()"은
#   PyTorch 표준 API(평가모드 전환, 안전)인데 기존 정규식이 위험한 전역 eval()과 구분 못했음
#   WHY: (?<!\.) 부정 후방탐색으로 "obj.eval("류 메서드 호출을 전부 배제 — 진짜 위험한 전역
#        eval(...)은 앞에 '.'이 오지 않으므로 그대로 잡힘
#   COST: 아주 드물게 `some_dict.get('eval')(...)` 처럼 변수명이 우연히 eval인 메서드 호출도
#        같이 배제될 수 있음(발생 가능성 낮음, 발견되면 tier_b_hook 억제 루프로 개별 처리)
#   EXIT: 이후 언어별 오탐이 더 쌓이면 tier_b_hook.py의 재귀 억제 루프로 이관
# 안전 확인: 아래는 eval()을 실행하는 코드가 아니라 스캔 대상 파일에서 위험한 eval() 호출
# "문자열 패턴"을 탐지만 하는 정규식이다. 이 스크립트 자체는 eval()을 호출하지 않는다.
EVAL_RE = re.compile(r"(?<!\.)\beval\(|dangerouslySetInnerHTML")
# D12-secret: \b로 단어경계 강제 + 최소 길이 요구 (Competitions.tsx의 "risk-stability" 오탐 수정)
#   기존 SECRET_RE=r"(sk-|AKIA|...)"는 "risk-stability" 안의 "sk-" 부분일치를 그대로 매치했음.
#   "sk-"는 항상 'i' 같은 단어문자 뒤가 아니라 인용부호/문자열 시작 뒤에 오므로 \b가 정확히 구분해줌.
SECRET_RE = re.compile(
    r"(\bsk-[A-Za-z0-9_-]{8,}|\bAKIA[A-Z0-9]{12,}|api[_-]?key\s*=\s*['\"][^'\"]{4,}['\"])",
    re.I,
)


def find_src_files(repo_root):
    files = []
    for root, dirs, fnames in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in fnames:
            if f.endswith(SRC_EXTS):
                files.append(os.path.join(root, f))
    return files


# D18: '@/' 경로 별칭(alias) import도 로컬 import로 인식
#   WHY: jxxnixx/LMS 실측 — Vite/TS의 흔한 관례(`"@": "./src"`)로 만든 `@/api/...` 형태
#        import가 99건인데 기존 코드는 "." 로 시작하는 상대경로만 인식해서 전부 누락됨.
#        누락 시 fan-in 그래프가 사실상 텅 비어 인지 블록이 무의미해짐(실측: 최대 fan_in=2/51파일)
#   COST: alias 접두어를 tsconfig/vite.config에서 동적으로 읽지 않고 '@/' 하드코딩 —
#        다른 접두어(예: '~/', 'src/')를 쓰는 프로젝트는 여전히 놓침
#   EXIT: LOCAL_IMPORT_PREFIXES에 접두어 추가, 또는 tsconfig paths를 파싱해 동적 목록 생성으로 교체
LOCAL_IMPORT_PREFIXES = (".", "@/")


def extract_js_targets(text):
    return [m.group(1) for m in JS_IMPORT_RE.finditer(text) if m.group(1).startswith(LOCAL_IMPORT_PREFIXES)]


def extract_py_targets(text):
    targets = []
    for m in PY_IMPORT_RE.finditer(text):
        mod = m.group(1) or m.group(2)
        if mod:
            targets.append(mod.split(".")[-1])
    return targets


def extract_java_targets(text):
    return [m.group(1).split(".")[-1] for m in JAVA_IMPORT_RE.finditer(text)]


def extract_c_targets(text):
    return [m.group(1) for m in C_INCLUDE_RE.finditer(text)]


def extract_targets_for_file(fp, text):
    ext = os.path.splitext(fp)[1]
    if ext in JS_EXTS:
        return extract_js_targets(text)
    if ext == ".py":
        return extract_py_targets(text)
    if ext == ".java":
        return extract_java_targets(text)
    if ext in C_LIKE_EXTS:
        return extract_c_targets(text)
    if ext == ".swift":
        return []  # Swift는 모듈 단위 가시성 — 파일간 로컬 import가 없어 구조 스캔 대상 아님(문서화된 한계)
    return []


def resolve_matches(target, fan_in_keys):
    """target에 확장자가 있으면(C의 #include "utils.h") 파일명 정확매치, 없으면(JS/Py/Java) stem매치."""
    target_base = os.path.basename(target)
    _, ext = os.path.splitext(target_base)
    matches = []
    for candidate in fan_in_keys:
        if ext:
            if candidate == target_base:
                matches.append(candidate)
        else:
            if os.path.splitext(candidate)[0] == target_base:
                matches.append(candidate)
    return matches


def tier_a_structural_scan(files):
    """저비용: import/include문만 정규식으로 추출, 파일 전체 의미는 안 봄.

    edge를 (src,dst) 집합(set)으로 먼저 dedupe한 뒤 fan_in을 집계한다(D12) — 같은 모듈을
    여러 줄로 나눠 import해도 fan-in이 한 번만 올라간다.
    """
    fan_in_keys = [os.path.basename(f) for f in files]
    edge_set = set()
    for fp in files:
        text = open(fp, encoding="utf-8", errors="ignore").read()
        src = os.path.basename(fp)
        for target in extract_targets_for_file(fp, text):
            for dst in resolve_matches(target, fan_in_keys):
                if dst != src:
                    edge_set.add((src, dst))

    fan_in = {k: 0 for k in fan_in_keys}
    for _src, dst in edge_set:
        fan_in[dst] += 1

    edges = sorted(edge_set)
    isolated = [f for f in fan_in_keys if fan_in[f] == 0]
    return {"fan_in": fan_in, "edges": edges, "zero_fan_in_files": isolated}


def tier_b_risk_triggered_scan(files):
    """고비용이지만 조건부 발동: 키워드 사전 매치가 없는 파일은 깊게 읽지 않음
    (=deep_read_count를 늘리지 않음). 이게 인지 블록의 비용 절감 핵심 장치.

    각 히트에 실제 매치된 텍스트(matched_text)도 함께 기록한다 — 판단 블록의
    tier_b_hook 재귀 억제 필터가 (trigger, matched_text) 단위로 오탐을 학습하기 위함.
    """
    flagged = {}
    deep_read_count = 0
    for fp in files:
        text = open(fp, encoding="utf-8", errors="ignore").read()
        hits = []
        if AUTH_KEYWORDS.search(text) and STRINGIFY_RE.search(text) and THROW_RE.search(text):
            hits.append({"trigger": "auth_info_leak_via_thrown_error", "matched_text": AUTH_KEYWORDS.search(text).group(0)})
        m = EVAL_RE.search(text)
        if m:
            hits.append({"trigger": "eval_or_dangerous_html", "matched_text": m.group(0)})
        m = SECRET_RE.search(text)
        if m:
            hits.append({"trigger": "hardcoded_secret_pattern", "matched_text": m.group(0)})
        if hits:
            flagged[os.path.basename(fp)] = hits
            deep_read_count += 1
    return {"flagged": flagged, "deep_read_count": deep_read_count, "total_files": len(files)}


def scan(repo_root):
    files = find_src_files(repo_root)
    tier_a = tier_a_structural_scan(files)
    tier_b = tier_b_risk_triggered_scan(files)
    return {
        "repo": repo_root,
        "total_source_files": len(files),
        "tier_a_structural": {
            "fan_in": tier_a["fan_in"],
            "zero_fan_in_files": tier_a["zero_fan_in_files"],
            "edges": tier_a["edges"],
        },
        "tier_b_risk_triggered": {
            "flagged_files": tier_b["flagged"],
            "deep_read_count": tier_b["deep_read_count"],
            "total_files": tier_b["total_files"],
            "cost_saved_ratio": round(1 - tier_b["deep_read_count"] / max(tier_b["total_files"], 1), 3),
        },
    }


def main():
    repo_root = sys.argv[1] if len(sys.argv) > 1 else "."
    print(json.dumps(scan(repo_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
