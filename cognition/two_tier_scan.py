import re
import os
import sys
import json

# D2: Tier A(구조 스캔) / Tier B(위험 트리거 내용 스캔) 이원화
#   WHY: 그래프/import 스캔(저비용)만으로는 handleFirestoreError 같은 "내용 기반" 이슈를 못 잡음
#        (2026-07-01 Study-Match- 실측: 그래프에서 fan-in 최고였던 firebase.ts가 아니라
#         파일 전체를 읽어야만 보이는 인증정보 유출이 진짜 위험이었음)
#   COST: 위험 키워드 사전에 없는 새로운 패턴의 이슈는 여전히 놓침. 정규식 기반이라 오탐 발생
#        (실측: Competitions.tsx의 캐글 URL 문자열 안 "risk-stability"가 우연히 "sk-"와 매치되어 오탐)
#   EXIT: RISK_TRIGGERS에 항목 추가/수정. 또는 judgment 블록의 hook 재귀 업데이트로
#        (발동 로그 → 오탐 빈도 → 트리거 정규식 자동 보정) 대체

SRC_EXTS = (".ts", ".tsx", ".js", ".jsx")
SKIP_DIRS = {"node_modules", ".git", "dist", "build"}

IMPORT_RE = re.compile(r"import\s+.*?from\s+['\"](.+?)['\"]")

AUTH_KEYWORDS = re.compile(r"\b(uid|email|token|password|apiKey|currentUser|authInfo)\b")
STRINGIFY_RE = re.compile(r"JSON\.stringify")
THROW_RE = re.compile(r"\bthrow\b")
EVAL_RE = re.compile(r"\beval\(|dangerouslySetInnerHTML")
SECRET_RE = re.compile(r"(sk-|AKIA|api[_-]?key\s*=\s*['\"])", re.I)


def find_src_files(repo_root):
    files = []
    for root, dirs, fnames in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in fnames:
            if f.endswith(SRC_EXTS):
                files.append(os.path.join(root, f))
    return files


def tier_a_structural_scan(files):
    """저비용: import문만 정규식으로 추출, 파일 전체 의미는 안 봄.

    알려진 한계(실측): 같은 모듈을 여러 import문으로 나눠 쓰면(예: '../firebase'를
    두 줄로 나눠 import) 파일 단위가 아니라 import문 단위로 세어 fan-in이 부풀려짐.
    """
    fan_in = {os.path.basename(f): 0 for f in files}
    edges = []
    for fp in files:
        text = open(fp, encoding="utf-8", errors="ignore").read()
        for m in IMPORT_RE.finditer(text):
            target = m.group(1)
            if not target.startswith("."):
                continue
            target_base = os.path.basename(target)
            for candidate in fan_in:
                stem = os.path.splitext(candidate)[0]
                if stem == target_base or stem == target_base.split("/")[-1]:
                    fan_in[candidate] += 1
                    edges.append((os.path.basename(fp), candidate))
    isolated = [os.path.basename(fp) for fp in files if fan_in.get(os.path.basename(fp), 0) == 0]
    return {"fan_in": fan_in, "edges": edges, "zero_fan_in_files": isolated}


def tier_b_risk_triggered_scan(files):
    """고비용이지만 조건부 발동: 키워드 사전 매치가 없는 파일은 깊게 읽지 않음
    (=deep_read_count를 늘리지 않음). 이게 인지 블록의 비용 절감 핵심 장치.
    """
    flagged = {}
    deep_read_count = 0
    for fp in files:
        text = open(fp, encoding="utf-8", errors="ignore").read()
        hits = []
        if AUTH_KEYWORDS.search(text) and STRINGIFY_RE.search(text) and THROW_RE.search(text):
            hits.append("auth_info_leak_via_thrown_error")
        if EVAL_RE.search(text):
            hits.append("eval_or_dangerous_html")
        if SECRET_RE.search(text):
            hits.append("hardcoded_secret_pattern")
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
