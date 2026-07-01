import json
import os
import re
import sys

# D3: 판단 블록 = 규칙 기반 정성 채점(상/중/하), ML 아님
#   WHY: 사례가 적고(4건) 기준이 명확해 규칙 기반이 더 투명하고 디버깅 가능 —
#        "설계의도/질문가치/위험도" 3축은 2026-07-01 수동 분석에서 검증된 기준을 그대로 코드화
#   COST: 새로운 패턴이 생기면 사람이 직접 규칙을 추가해야 함(자동 일반화 안 됨).
#        예: useAuth Context 같은 "관용 패턴"과 "진짜 설계 결정"을 구분하는 필터는 아직 없음
#   EXIT: 규칙이 늘어나 유지보수가 안 되면 judgment_rules.yaml로 분리하거나,
#        hook 발동 로그 기반 자동 승격(WARN→BLOCK류)으로 대체

ENTRY_POINT_HINTS = ("main.", "index.")
REPEATED_PATTERN_MIN_FILES = 2
REPEATED_PATTERN_MIN_HITS = 2


def find_hub(fan_in):
    """entry point(main.tsx 등)를 제외한 fan-in 최고 파일 = 인지 블록이 뽑은 '허브'."""
    candidates = {k: v for k, v in fan_in.items() if not any(k.startswith(h) for h in ENTRY_POINT_HINTS)}
    if not candidates:
        return None
    return max(candidates, key=candidates.get)


def find_isolated_from_hub(edges, fan_in, hub):
    """앱에 라우팅되어 쓰이는데(fan_in>=1) 허브로 가는 edge가 없는 파일.

    실측(Study-Match-): fan-in 지표만 보면 이런 파일을 놓친다 — 이 파일도 fan_in=1로
    '정상'처럼 보이기 때문. 반드시 edge의 목적지(dst)까지 봐야 드러남.
    """
    routed = {f for f, n in fan_in.items() if n >= 1 and f != hub}
    connected_to_hub = {src for src, dst in edges if dst == hub}
    return sorted(routed - connected_to_hub)


def find_repeated_pattern_files(repo_root, pattern, min_hits):
    hits = {}
    for root, dirs, fnames in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "dist", "build"}]
        for fn in fnames:
            if not fn.endswith((".ts", ".tsx", ".js", ".jsx")):
                continue
            text = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
            c = len(re.findall(re.escape(pattern), text))
            if c >= min_hits:
                hits[fn] = c
    return hits


def score(scan_result, repo_root):
    tier_a = scan_result["tier_a_structural"]
    tier_b = scan_result["tier_b_risk_triggered"]
    fan_in, edges = tier_a["fan_in"], tier_a["edges"]

    findings = []

    hub = find_hub(fan_in)
    if hub:
        for f in find_isolated_from_hub(edges, fan_in, hub):
            findings.append({
                "id": f"cognition-isolation:{f}",
                "finding": f"{f} — 허브 모듈({hub})로 가는 edge 없음. fan_in={fan_in.get(f)}만 보면 정상으로 보임",
                "design_intent": "불명(의도적 스코프 축소 vs 미완성 방치 구분 불가)",
                "question_value": "상",
                "risk": "하",
                "priority": "최우선",
            })

    for f, hits in tier_b["flagged_files"].items():
        if "auth_info_leak_via_thrown_error" in hits:
            findings.append({
                "id": f"tier-b-risk:{f}",
                "finding": f"{f} — 인증정보(uid/email 등)가 JSON.stringify되어 throw된 Error에 담김",
                "design_intent": "중(에러 컨텍스트를 남기려는 의도는 있어 보임)",
                "question_value": "중",
                "risk": "상",
                "priority": "Important(🔴)",
            })
        if "hardcoded_secret_pattern" in hits:
            findings.append({
                "id": f"tier-b-risk:{f}:secret",
                "finding": f"{f} — 시크릿 패턴 매치(오탐 가능성 있음, 육안 확인 필요)",
                "design_intent": "확인 필요",
                "question_value": "하",
                "risk": "확인 전까지 중",
                "priority": "검토 대상(자동 신뢰 금지)",
            })

    for pattern, min_files in {"onSnapshot": REPEATED_PATTERN_MIN_FILES}.items():
        repeated = find_repeated_pattern_files(repo_root, pattern, REPEATED_PATTERN_MIN_HITS)
        if len(repeated) >= min_files:
            findings.append({
                "id": f"repeated-pattern:{pattern}",
                "finding": f"'{pattern}' 반복 등장 파일: {repeated}",
                "design_intent": "하(리팩토링 누락 가능성)",
                "question_value": "상",
                "risk": "하(유지보수성)",
                "priority": "질문 대상",
            })

    return {"hub": hub, "findings": findings}


def main():
    if len(sys.argv) < 3:
        print("usage: score_findings.py <scan_output.json> <repo_root>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        scan_result = json.load(f)
    print(json.dumps(score(scan_result, sys.argv[2]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
