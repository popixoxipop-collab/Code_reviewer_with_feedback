import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from idiom_filter import apply_idiom_filter  # noqa: E402

# D3: 판단 블록 = 규칙 기반 정성 채점(상/중/하), ML 아님
#   WHY: 사례가 적고(4건) 기준이 명확해 규칙 기반이 더 투명하고 디버깅 가능 —
#        "설계의도/질문가치/위험도" 3축은 2026-07-01 수동 분석에서 검증된 기준을 그대로 코드화
#   COST: 새로운 패턴이 생기면 사람이 직접 규칙을 추가해야 함(자동 일반화 안 됨)
#   EXIT: 규칙이 늘어나 유지보수가 안 되면 judgment_rules.yaml로 분리하거나,
#        hook 발동 로그 기반 자동 승격(WARN→BLOCK류)으로 대체
#
# D3-COST 해소: "관용 패턴 vs 진짜 설계 결정" 구분은 idiom_filter.py + idiom_hook.py로 분리 구현
#   (useAuth Context 같은 프레임워크 관례가 질문가치를 과대평가받던 문제, 아래 find_architecture_diffusion_point 참고)

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


def find_architecture_diffusion_point(fan_in, hub, repo_root):
    """허브 다음으로 fan-in이 높은 파일 = 여러 컴포넌트가 공유해서 쓰는 두 번째 확산 지점.

    이 자체는 관용 패턴(React Context 등)일 수도, 진짜 설계 판단일 수도 있다 —
    여기서는 후보만 뽑고, "관용 패턴인지"는 pattern_key를 붙여 idiom_filter가 판정하게 넘긴다.
    """
    candidates = {k: v for k, v in fan_in.items() if k != hub and v >= 2}
    if not candidates:
        return None
    top_file = max(candidates, key=candidates.get)

    pattern_key = None
    for root, dirs, fnames in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "dist", "build"}]
        for fn in fnames:
            if fn == top_file:
                text = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
                if re.search(r"createContext\s*(<[^>]*>)?\s*\(", text):
                    pattern_key = "react-context-global-state"
                break
    return {"file": top_file, "fan_in": candidates[top_file], "pattern_key": pattern_key}


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
                "file": f,
                "finding": f"{f} — 허브 모듈({hub})로 가는 edge 없음. fan_in={fan_in.get(f)}만 보면 정상으로 보임",
                "design_intent": "불명(의도적 스코프 축소 vs 미완성 방치 구분 불가)",
                "question_value": "상",
                "risk": "하",
                "priority": "최우선",
            })

        diffusion = find_architecture_diffusion_point(fan_in, hub, repo_root)
        if diffusion:
            findings.append({
                "id": f"architecture-diffusion:{diffusion['file']}",
                "file": diffusion["file"],
                "pattern_key": diffusion["pattern_key"],
                "finding": f"{diffusion['file']} — 허브 다음으로 fan_in={diffusion['fan_in']}, 여러 컴포넌트가 공유",
                "design_intent": "높음(다만 프레임워크 관용 패턴일 수 있음 — idiom_filter가 확정 여부 판정)",
                "question_value": "상",
                "risk": "하",
                "priority": "질문 대상",
            })

    for f, hits in tier_b["flagged_files"].items():
        if "auth_info_leak_via_thrown_error" in hits:
            findings.append({
                "id": f"tier-b-risk:{f}",
                "file": f,
                "finding": f"{f} — 인증정보(uid/email 등)가 JSON.stringify되어 throw된 Error에 담김",
                "design_intent": "중(에러 컨텍스트를 남기려는 의도는 있어 보임)",
                "question_value": "중",
                "risk": "상",
                "priority": "Important(🔴)",
            })
        if "hardcoded_secret_pattern" in hits:
            findings.append({
                "id": f"tier-b-risk:{f}:secret",
                "file": f,
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
                "file": None,
                "finding": f"'{pattern}' 반복 등장 파일: {repeated}",
                "design_intent": "하(리팩토링 누락 가능성)",
                "question_value": "상",
                "risk": "하(유지보수성)",
                "priority": "질문 대상",
            })

    findings = apply_idiom_filter(findings)
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
