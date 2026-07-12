"""D121 -- Hook File 생성기.

측정 산출물(P01 unit_map / P02 findings / P03 transcript+scores)에서 증거 필드를
결정론적으로 조립하고, LLM(Locked qwen)은 지침_본문 문장화에만 사용한다(학생/회차당
1콜 -- 모든 후보 규칙의 지침문을 한 번의 배치 콜로 생성, 근거 필드는 프롬프트에 그대로
주입해 "근거 없이 지침을 만들 수 없는" 구조를 강제).

측정기 불변식(D123 temporal firewall, layer 3): 이 회차의 측정 raw가 이미 git에 커밋돼
있어야만(해시 고정) 실행된다 -- "측정 완결 -> 처방" 순서를 코드로 강제.

Usage:
  python3 hookfile/generate_hook_file.py \\
    --student-id S001 --round 1 \\
    --findings path/to/judgment_findings.json \\
    --transcript path/to/turn_engine_transcript.json \\
    --unit-map path/to/unit_map.json \\
    --out hookfile_v1.json \\
    [--prev-version hookfile_v0.json]  # R2+ 증분 병합용
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "feedback"))
sys.path.insert(0, str(REPO))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402
from timeout_config import DEFAULT_TIMEOUT_S, DEFAULT_MAX_TOKENS  # noqa: E402
import canary  # noqa: E402

MODEL = "qwen/qwen3-next-80b-a3b-instruct"  # 팀 Locked -- 이 계획 전체가 상속하는 원칙
RULE_BUDGET = 10  # D125 확정: P02+P03 두 채널 합산 상한
TOP_AXES = 3
RULES_PER_AXIS = 4  # 3*4=12 후보 생성 후 예산으로 절사(상위 axis일수록 우선)

# D121: P02 finding "kind"(id 접두어) -> FR-04-01 5축 매핑. 이 매핑은 이 코드베이스에
#   원래 존재하지 않았다 -- P02는 자체 3축(design_intent/question_value/risk)을, P03는
#   FR-04-01 5축을 각각 독립적으로 써 왔고, Hook File이 두 채널을 하나의 축 공간으로
#   통합하려면 이 다리가 필요했다(발견된 설계 갭, 여기서 최초 정의).
#   WHY: 각 finding kind가 실제로 무엇을 진단하는지에 따라 가장 가까운 FR 축을 골랐다 --
#        cognition-isolation(허브 미연결)=자기 코드 구조를 아는가=코드_이해,
#        architecture-diffusion(공유 지점)=추출/재사용 대안을 고려했는가=대안_비교,
#        tier-b-risk(보안 트리거)="이 입력이 악의적이면?"=반례_대응,
#        repeated-pattern(중복)=대안_비교(추출 대안).
#   COST: 이 매핑은 휴리스틱이지 실측 검증(사람 라벨 대조)을 거치지 않았다 -- P02
#        정밀도 라벨링(D119 3.1)처럼 사람 표본 대조가 필요한 후속 검증 대상.
#   EXIT: 매핑이 틀렸다는 신호(예: 특정 kind의 규칙이 항상 무시됨, audit_checklist.py의
#        통과율로 감지 가능)가 나오면 이 딕셔너리만 교체하면 됨 -- 나머지 코드는 불변.
FINDING_KIND_TO_FR_AXIS = {
    "cognition-isolation": "코드_이해",
    "architecture-diffusion": "대안_비교",
    "tier-b-risk": "반례_대응",
    "repeated-pattern": "대안_비교",
}
FR_AXES = ("코드_이해", "설계_논리", "대안_비교", "반례_대응", "자기_수정")


def log(msg):
    print(f"[generate_hook_file] {msg}", file=sys.stderr, flush=True)


def _file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def _git_commit_contains(path):
    """D123 layer 3 temporal firewall: 이 파일이 현재 HEAD 커밋에 포함돼 있는지 확인.
    미확인 시(uncommitted) 생성을 거부 -- '측정 완결 -> 처방' 순서를 코드로 강제."""
    try:
        rel = str(Path(path).resolve().relative_to(REPO))
    except ValueError:
        return False, "path outside repo -- cannot verify commit status"
    r = subprocess.run(
        ["git", "-C", str(REPO), "status", "--porcelain", "--", rel],
        capture_output=True, text=True, timeout=15,  # timeout-guard: allow (local git status)
    )
    if r.stdout.strip():
        return False, f"{rel} has uncommitted changes: {r.stdout.strip()}"
    r2 = subprocess.run(
        ["git", "-C", str(REPO), "log", "-1", "--format=%H", "--", rel],
        capture_output=True, text=True, timeout=15,  # timeout-guard: allow (local git log)
    )
    commit = r2.stdout.strip()
    if not commit:
        return False, f"{rel} is not tracked in git history"
    return True, commit


def temporal_firewall_check(*paths):
    for p in paths:
        ok, detail = _git_commit_contains(p)
        if not ok:
            raise RuntimeError(
                f"D123 temporal firewall: 측정 raw({p})가 아직 커밋되지 않음 -- {detail}. "
                f"'측정 완결 -> 처방' 순서 위반. 먼저 커밋할 것."
            )
    return True


def _weakest_fr_axes(transcript_scores, n=TOP_AXES):
    """P03 score_card 리스트에서 점수가 낮은 축부터 정렬(ENG-01 취약축 진단)."""
    by_axis = {}
    for sc in transcript_scores:
        axis = sc["fr_axis"]
        by_axis.setdefault(axis, []).append(sc["score"])
    ranked = sorted(by_axis.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
    return [axis for axis, _ in ranked[:n]]


def build_candidate_rules(findings, transcript_scores, unit_map, round_num, seq_by_axis=None):
    """증거 필드를 결정론적으로 조립 -- LLM 관여 없음.

    D122(gamma R2 실측 발견): seq_by_axis를 매번 0부터 새로 세면, R2에서 새로 만드는
    rule_id가 R1에서 이미 쓴 rule_id와 우연히 같아질 수 있다(예: 서로 다른 파일을
    가리키는 두 규칙이 둘 다 "대안_비교-01") -- merge_with_previous()는 (취약축,trigger)
    키로만 중복 판정해서 이 경우 진짜 다른 두 규칙이 같은 rule_id로 공존하게 됨.
    caller(generate_hook_file)가 prev_version의 기존 rule_id에서 축별 최대 seq를
    미리 계산해 넘겨주면 이어서 번호를 매긴다.
    """
    weak_axes = _weakest_fr_axes(transcript_scores) if transcript_scores else list(FR_AXES[:TOP_AXES])
    log(f"weakest FR axes this round: {weak_axes}")

    candidates = []
    seq_by_axis = dict(seq_by_axis) if seq_by_axis else {}

    # 코드 채널(P02): finding kind -> FR axis 매핑으로 후보 생성, priority가 높은 순
    priority_rank = {"최우선": 0, "Important(🔴)": 1, "질문 대상": 2, "검토 대상(자동 신뢰 금지)": 3}
    sorted_findings = sorted(findings, key=lambda f: priority_rank.get(f.get("priority"), 9))
    for f in sorted_findings:
        kind = f["id"].split(":")[0]
        axis = FINDING_KIND_TO_FR_AXIS.get(kind)
        if axis not in weak_axes:
            continue
        seq = seq_by_axis.get(axis, 0) + 1
        seq_by_axis[axis] = seq
        curriculum_ref = _find_curriculum_ref(f, unit_map)
        candidates.append({
            "rule_id": f"{axis}-{seq:02d}", "channel": "code", "취약축": axis,
            "tech_area": f.get("lang") or "unknown",
            "finding_refs": [{
                "source": "judgment_4axis_benchmark.py or live scan", "finding_id": f["id"],
                "priority": f.get("priority"), "subrubric_axis": _dominant_subrubric_axis(f),
            }],
            "transcript_refs": [],
            "curriculum_refs": curriculum_ref,
            "trigger": f"파일 패턴: *{f.get('file') or ''}* 또는 유사 구조(허브 미연결/공유 확산/보안 트리거)",
            "checkable_condition": (
                f"다음 회차 P02 스캔 결과에 동일 kind('{kind}')+동일 file('{f.get('file')}') "
                f"finding이 재발하지 않아야 함"
            ),
            "provenance_hash": None,  # generate_hook_file() 호출부에서 findings_path 해시로 채움
            "_evidence_text": f.get("finding", ""),
        })

    # 인터뷰 채널(P03): 취약 축별로 가장 낮은 점수의 turn을 근거로 후보 생성
    scores_by_axis = {}
    for i, sc in enumerate(transcript_scores):
        scores_by_axis.setdefault(sc["fr_axis"], []).append((i, sc))
    for axis in weak_axes:
        entries = sorted(scores_by_axis.get(axis, []), key=lambda x: x[1]["score"])[:RULES_PER_AXIS]
        for turn_index, sc in entries:
            seq = seq_by_axis.get(axis, 0) + 1
            seq_by_axis[axis] = seq
            candidates.append({
                "rule_id": f"{axis}-{seq:02d}", "channel": "interview", "취약축": axis,
                "tech_area": None,
                "finding_refs": [],
                "transcript_refs": [{
                    "round": round_num, "turn_index": turn_index, "level": sc.get("level"),
                    "fr_axis": axis, "score": sc["score"],
                }],
                "curriculum_refs": None,
                "trigger": f"이 회차 인터뷰에서 '{axis}' 관련 질문이 나올 때",
                "checkable_condition": f"다음 회차 인터뷰의 '{axis}' 점수가 이번 회차({sc['score']}점)보다 낮아지지 않아야 함",
                "provenance_hash": None,
                "_evidence_text": f"{sc.get('criterion', '')} | evidence: {sc.get('evidence', '')}",
            })

    return candidates, weak_axes


def _dominant_subrubric_axis(finding):
    sub = finding.get("subrubric") or {}
    if not sub:
        return None
    return min(sub.items(), key=lambda kv: {"하": 0, "중": 1, "상": 2}.get(finding.get(kv[0], "중"), 1))[0] if sub else None


def _find_curriculum_ref(finding, unit_map):
    """finding의 언어/맥락과 대략 맞는 unit을 찾아 CUR-02 매핑 근거로 사용.
    P01 provenance-precision 검증을 통과한 concept만 인용해야 한다는 §4.1 선행 게이트를
    실제로 강제하려면 curriculum_provenance_audit.json의 tier1_pass/tier2 grounded 결과와
    교차해야 한다 -- 이 1차 구현은 unit_map 유무만 확인하고, 정합성 교차검증은 EXIT로 남김."""
    if not unit_map:
        return None
    first_unit = next(iter(unit_map.values()), None)
    if not first_unit:
        return None
    return {
        "unit": first_unit.get("unit_id"), "unit_title": first_unit.get("unit_title"),
        "source_pages": first_unit.get("source_pages", []),
    }


def apply_rule_budget(candidates, budget=RULE_BUDGET):
    """상위 3축 우선, 축 내에서는 code/interview 번갈아 -- 인위적 반반 아니라 발견 순서
    그대로(축 심각도로 이미 정렬됨). 예산 초과분은 deferred_rules로 보존."""
    kept, deferred = candidates[:budget], candidates[budget:]
    return kept, deferred


def phrase_instructions(client, candidates, prev_rules=None):
    """LLM 1콜(배치) -- 근거 필드만 프롬프트에 넣고 지침_본문만 요청. 근거 없이 지침 생성 불가."""
    if not candidates:
        return {}
    items = [
        {"rule_id": c["rule_id"], "취약축": c["취약축"], "trigger": c["trigger"], "evidence": c["_evidence_text"]}
        for c in candidates
    ]
    prompt = (
        "아래는 한 교육생의 실제 코드 리뷰 finding 또는 인터뷰 채점 근거다. 각 항목마다, "
        "이 근거에 기반해 다음 과제를 수행할 때 지켜야 할 **실행 가능한 지시문**을 1~2문장으로 써라 "
        "(예: '기능 구현 전에 endpoint/request/response schema/error case를 표로 먼저 정리'). "
        "근거에 없는 내용을 지어내지 마라 -- 근거가 빈약하면 지시문도 보수적으로 좁게 써라.\n\n"
        f"근거 목록:\n{json.dumps(items, ensure_ascii=False, indent=2)}\n\n"
        "JSON만 반환: {\"instructions\": [{\"rule_id\": \"...\", \"지침_본문\": \"...\"}]}"
    )
    resp = client.chat(
        model=MODEL, messages=[{"role": "user", "content": prompt}],
        max_tokens=DEFAULT_MAX_TOKENS, temperature=0.0,
        response_format={"type": "json_object"},
    )
    content = resp["choices"][0]["message"].get("content") or "{}"
    parsed = json.loads(content)
    return {item["rule_id"]: item["지침_본문"] for item in parsed.get("instructions", [])}


def merge_with_previous(new_rules, prev_version_path):
    """R2+: v1 규칙 + 이번 회차 신규 처방 = v2(증분 병합, append 우선, 중복은 근거 병합)."""
    if not prev_version_path or not Path(prev_version_path).exists():
        return new_rules
    prev = json.loads(Path(prev_version_path).read_text(encoding="utf-8"))
    prev_rules = prev.get("rules", [])
    prev_by_axis_trigger = {(r["취약축"], r["trigger"]): r for r in prev_rules}
    merged = list(prev_rules)
    for r in new_rules:
        key = (r["취약축"], r["trigger"])
        if key in prev_by_axis_trigger:
            existing = prev_by_axis_trigger[key]
            existing["finding_refs"] = existing.get("finding_refs", []) + r.get("finding_refs", [])
            existing["transcript_refs"] = existing.get("transcript_refs", []) + r.get("transcript_refs", [])
        else:
            merged.append(r)
    return merged


def generate_hook_file(student_id, round_num, findings_path, transcript_path, unit_map_path,
                        out_path, prev_version_path=None, skip_firewall=False):
    if not skip_firewall:
        temporal_firewall_check(findings_path, transcript_path, unit_map_path)
    else:
        log("WARNING: temporal firewall skipped (skip_firewall=True) -- dev/demo mode only")

    findings = json.loads(Path(findings_path).read_text(encoding="utf-8")) if findings_path else []
    transcript_scores = json.loads(Path(transcript_path).read_text(encoding="utf-8")) if transcript_path else []
    unit_map = json.loads(Path(unit_map_path).read_text(encoding="utf-8")) if unit_map_path else {}

    starting_seq_by_axis = {}
    if prev_version_path and Path(prev_version_path).exists():
        prev_rules = json.loads(Path(prev_version_path).read_text(encoding="utf-8")).get("rules", [])
        for r in prev_rules:
            axis, _, seq_str = r["rule_id"].rpartition("-")
            try:
                seq = int(seq_str)
            except ValueError:
                continue
            starting_seq_by_axis[axis] = max(starting_seq_by_axis.get(axis, 0), seq)

    candidates, weak_axes = build_candidate_rules(findings, transcript_scores, unit_map, round_num, seq_by_axis=starting_seq_by_axis)
    for c in candidates:
        src_path = findings_path if c["channel"] == "code" else transcript_path
        c["provenance_hash"] = _file_hash(src_path) if src_path else None
    kept, deferred = apply_rule_budget(candidates)
    log(f"{len(candidates)} candidates -> {len(kept)} kept, {len(deferred)} deferred (budget={RULE_BUDGET})")

    pool = NvidiaKeyPool.from_env()
    client = NvidiaRotatingClient(pool=pool, timeout_s=DEFAULT_TIMEOUT_S)
    instructions = phrase_instructions(client, kept)
    for c in kept:
        c["지침_본문"] = instructions.get(c["rule_id"], "")
        del c["_evidence_text"]
    for c in deferred:
        c.pop("_evidence_text", None)

    merged_rules = merge_with_previous(kept, prev_version_path)
    version = 1
    if prev_version_path and Path(prev_version_path).exists():
        version = json.loads(Path(prev_version_path).read_text(encoding="utf-8"))["version"] + 1

    all_axes_diagnosed = set(weak_axes)
    covered_axes = {r["취약축"] for r in merged_rules}
    coverage = len(covered_axes & all_axes_diagnosed) / len(all_axes_diagnosed) if all_axes_diagnosed else 0.0

    token = canary.issue_canary(student_id, version)
    hook_file = {
        "student_id": student_id, "version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_round": round_num, "canary_uuid": token, "coverage": round(coverage, 3),
        "provenance_commit": _git_commit_contains(findings_path)[1] if findings_path and not skip_firewall else None,
        "deferred_rules": deferred, "rules": merged_rules,
    }
    Path(out_path).write_text(json.dumps(hook_file, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"wrote {out_path} (version={version}, {len(merged_rules)} rules, coverage={coverage:.3f})")
    return hook_file


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--findings", default=None)
    ap.add_argument("--transcript", default=None)
    ap.add_argument("--unit-map", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prev-version", default=None)
    ap.add_argument("--skip-firewall", action="store_true", help="dev/demo only -- bypasses D123 layer 3")
    args = ap.parse_args()
    generate_hook_file(
        args.student_id, args.round, args.findings, args.transcript, args.unit_map,
        args.out, prev_version_path=args.prev_version, skip_firewall=args.skip_firewall,
    )


if __name__ == "__main__":
    main()
