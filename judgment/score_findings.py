import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from idiom_filter import apply_idiom_filter  # noqa: E402
from tier_b_suppression_filter import apply_tier_b_suppression  # noqa: E402

# D13: 반복 패턴 탐지 대상 확장자를 인지 블록(cognition/two_tier_scan.py)의 SRC_EXTS와 동일하게 유지
#   WHY: 인지 블록만 다국어로 확장하고 판단 블록이 JS/TS만 스캔하면 다시 불일치가 생김
#   COST: 두 파일에 같은 확장자 목록이 중복됨(cross-package import로 묶으면 경로가 더 취약해짐)
#   EXIT: 확장자 목록이 3번째로 필요해지면 그때 공용 constants 모듈로 추출
ALL_SRC_EXTS = (
    ".ts", ".tsx", ".js", ".jsx", ".py", ".java",
    ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".swift",
)
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv"}

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


# D16: hub 동점 시 fan-out(자신이 얼마나 많이 import하는지)이 낮은 쪽으로 tie-break
#   WHY: D12(fan-in 이중계산 수정) 부작용으로 App.tsx(main.tsx→App.tsx 엣지가 새로 정확히
#        잡히면서 fan_in 7)와 firebase.ts(fan_in 7)가 동점이 됨 — 회귀 테스트에서 실측 발견.
#        fan_in만으론 "많은 파일이 의존하는 서비스 허브"(firebase.ts, fan_out=0)와
#        "여러 컴포넌트를 조립하는 컨테이너"(App.tsx, fan_out=8)를 구분 못함. 진짜 허브는
#        의존은 적게 받으면서 적게 하는(sink에 가까운) 쪽이라는 게 실측 근거
#   COST: fan_out도 계산해야 해서 find_hub가 edges까지 받아야 함(시그니처 변경)
#   EXIT: 이 휴리스틱도 틀리면 명시적 화이트리스트("firebase.ts", "db.ts" 같은 서비스 파일명
#        패턴)로 대체 검토
def find_hub(fan_in, edges):
    """entry point(main.tsx 등)를 제외한 fan-in 최고 파일 = 인지 블록이 뽑은 '허브'.

    fan_in이 동점이면 fan_out이 낮은(자기는 남을 덜 의존하는, sink에 가까운) 쪽을 우선한다.
    """
    candidates = {k: v for k, v in fan_in.items() if not any(k.startswith(h) for h in ENTRY_POINT_HINTS)}
    if not candidates:
        return None
    fan_out = {k: 0 for k in candidates}
    for src, dst in edges:
        if src in fan_out:
            fan_out[src] += 1
    max_fan_in = max(candidates.values())
    top = [k for k, v in candidates.items() if v == max_fan_in]
    return min(top, key=lambda k: fan_out[k])


# D19: 고립 판정 범위를 "전체 파일"이 아니라 "앱 루트가 직접 라우팅하는 형제 파일"로 제한
#   WHY: jxxnixx/LMS 실측 — 기존 로직은 fan_in>=1인 전체 51개 파일 중 허브(GenreContext.jsx)에
#        안 걸린 30개를 전부 "최우선" 고립으로 오탐지함. Study-Match-에서 통했던 이유는 App.tsx가
#        직접 라우팅하는 형제 컴포넌트가 전부 firebase.ts를 쓰는 게 우연이 아니라 구조였기 때문 —
#        규모가 커지고 관심사가 여러 개(Genre/Auth/Books 등)로 나뉘면 "전체가 허브를 써야 한다"는
#        가정 자체가 깨짐. 대신 "entry→root가 직접 import하는 형제들"끼리만 비교해야 함
#   COST: 형제 그룹 바깥의 진짜 고립 파일(예: 깊은 유틸리티 파일의 이상 패턴)은 이 규칙으로 못 잡음
#        — 그건 애초에 이 규칙의 책임 범위가 아니라는 뜻으로 재정의한 것(범위 축소가 의도)
#   EXIT: "형제 그룹"을 root 직계가 아니라 2단계까지 확장하고 싶으면 find_routed_peers의
#        BFS 깊이만 늘리면 됨
def find_routed_peers(edges):
    """entry point가 import하는 루트 컴포넌트(들)가 직접 import하는 파일 집합 = 비교 대상 형제 그룹."""
    entry_srcs = {src for src, dst in edges if any(src.startswith(h) for h in ENTRY_POINT_HINTS)}
    roots = {dst for src, dst in edges if src in entry_srcs}
    peers = {dst for src, dst in edges if src in roots}
    return peers


def find_isolated_from_hub(edges, fan_in, hub):
    """루트가 직접 라우팅하는 형제 파일 중, 허브로 가는 edge가 없는 파일(D19로 범위 제한).

    실측(Study-Match-): fan-in 지표만 보면 이런 파일을 놓친다 — 이 파일도 fan_in=1로
    '정상'처럼 보이기 때문. 반드시 edge의 목적지(dst)까지 봐야 드러난다.
    """
    peers = find_routed_peers(edges)
    routed = {f for f in peers if fan_in.get(f, 0) >= 1 and f != hub}
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
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fnames:
            if fn == top_file:
                text = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
                if re.search(r"createContext\s*(<[^>]*>)?\s*\(", text):
                    pattern_key = "react-context-global-state"
                # D21: React Query "리소스별 커스텀 훅" 컨벤션도 관용 패턴 후보로 인식
                #   WHY: jxxnixx/LMS 실측 — useBooksQueries.ts가 fan_in=6으로 diffusion 후보에
                #        올랐는데 내용은 @tanstack/react-query 공식 문서가 권장하는 표준 패턴
                #        (리소스당 useQuery 래퍼 훅)이라 createContext 패턴 하나만 보던 기존
                #        탐지로는 놓쳤음. 이것도 "설계 판단"보다 "라이브러리 컨벤션"에 가까움
                #   COST: 다른 라이브러리의 유사 컨벤션(Redux Toolkit의 slice 등)은 여전히 미탐지
                #   EXIT: 새 컨벤션이 발견될 때마다 이 블록에 정규식 분기 추가(패턴 사전이 커지면
                #        PATTERN_DETECTORS 딕셔너리로 리팩터링 검토)
                elif re.search(r"\buse(Suspense)?(Query|Mutation)\s*\(", text):
                    pattern_key = "react-query-custom-hook"
                break
    return {"file": top_file, "fan_in": candidates[top_file], "pattern_key": pattern_key}


def find_repeated_pattern_files(repo_root, pattern, min_hits):
    hits = {}
    for root, dirs, fnames in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fnames:
            if not fn.endswith(ALL_SRC_EXTS):
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

    hub = find_hub(fan_in, edges)
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

    # D14: Tier B raw 히트에서 confirmed 오탐((trigger,matched_text) 단위)을 먼저 걷어낸 뒤 채점
    tier_b_flagged = apply_tier_b_suppression(tier_b["flagged_files"])
    for f, hits in tier_b_flagged.items():
        triggers = {h["trigger"] for h in hits}
        if "auth_info_leak_via_thrown_error" in triggers:
            findings.append({
                "id": f"tier-b-risk:{f}",
                "file": f,
                "finding": f"{f} — 인증정보(uid/email 등)가 JSON.stringify되어 throw된 Error에 담김",
                "design_intent": "중(에러 컨텍스트를 남기려는 의도는 있어 보임)",
                "question_value": "중",
                "risk": "상",
                "priority": "Important(🔴)",
            })
        if "hardcoded_secret_pattern" in triggers:
            matched = next(h["matched_text"] for h in hits if h["trigger"] == "hardcoded_secret_pattern")
            findings.append({
                "id": f"tier-b-risk:{f}:secret",
                "file": f,
                "finding": f"{f} — 시크릿 패턴 매치(오탐 가능성 있음, 육안 확인 필요) matched_text={matched!r}",
                "design_intent": "확인 필요",
                "question_value": "하",
                "risk": "확인 전까지 중",
                "priority": "검토 대상(자동 신뢰 금지)",
            })
        # D20: eval_or_dangerous_html 트리거를 finding으로 승격하는 규칙이 누락돼 있었음
        #   WHY: jxxnixx/LMS 실측 — 인지 블록은 Bookshelf.jsx의 dangerouslySetInnerHTML을 정확히
        #        잡았는데 판단 블록에 이 트리거를 finding화하는 규칙 자체가 없어서 조용히 버려짐
        #        (auth_info_leak/hardcoded_secret 두 트리거만 처리하고 있었음)
        #   COST: 없음 — 순수 누락 버그였음
        #   EXIT: 새 Tier B 트리거를 추가할 때마다 이 블록에도 대응 규칙을 반드시 추가해야 함
        #        (트리거 추가와 finding화 규칙 추가가 분리돼 있어 또 누락될 수 있음 — 근본 해법은
        #        트리거 이름→finding 템플릿을 딕셔너리로 묶어 한 곳에서 관리하는 리팩터링)
        if "eval_or_dangerous_html" in triggers:
            matched = next(h["matched_text"] for h in hits if h["trigger"] == "eval_or_dangerous_html")
            findings.append({
                "id": f"tier-b-risk:{f}:dangerous-html",
                "file": f,
                "finding": f"{f} — 위험한 동적 실행/HTML 삽입 패턴 matched_text={matched!r} (XSS 등 위험 가능, 입력 출처 확인 필요)",
                "design_intent": "확인 필요",
                "question_value": "중",
                "risk": "상",
                "priority": "Important(🔴)",
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

    findings = apply_idiom_filter(findings, repo_root=repo_root)
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
