"""D121 -- Hook 체크리스트 자동 감사기 (plan §5.3 지표 3).

checkable_condition은 사람이 읽는 설명 텍스트다 -- 자동 판정은 그 텍스트를 파싱하지
않고, 규칙의 구조화된 필드(finding_refs의 kind+file, transcript_refs의 fr_axis+score)를
다음 회차 산출물과 직접 대조한다.

판정:
  코드 채널  : 다음 회차 P02 스캔에 "동일 kind+동일 file" finding이 재발하면 FAIL, 없으면 PASS
  인터뷰 채널: 다음 회차 해당 fr_axis 점수가 근거 회차 점수 이상이면 PASS, 낮아지면 FAIL

Usage:
  python3 hookfile/audit_checklist.py --hook-file v1.json \\
    --next-findings round2_findings.json --next-transcript round2_scores.json \\
    --out audit_v1_vs_r2.json
"""
import argparse
import json
from pathlib import Path


def audit_code_rule(rule, next_findings):
    targets = {(fr["finding_id"].split(":")[0], _file_of(fr["finding_id"])) for fr in rule["finding_refs"]}
    next_kinds_files = {(f["id"].split(":")[0], f.get("file")) for f in next_findings}
    recurred = targets & next_kinds_files
    return {"rule_id": rule["rule_id"], "channel": "code", "passed": not recurred, "recurred": sorted(str(x) for x in recurred)}


def _file_of(finding_id):
    parts = finding_id.split(":")
    return parts[1] if len(parts) > 1 else None


def audit_interview_rule(rule, next_scores_by_axis):
    axis = rule["취약축"]
    baseline = max((tr["score"] for tr in rule["transcript_refs"]), default=None)
    next_scores = next_scores_by_axis.get(axis, [])
    if baseline is None or not next_scores:
        return {"rule_id": rule["rule_id"], "channel": "interview", "passed": None, "reason": "no baseline or next-round data"}
    next_best = max(next_scores)
    return {
        "rule_id": rule["rule_id"], "channel": "interview", "passed": next_best >= baseline,
        "baseline_score": baseline, "next_score": next_best,
    }


def audit(hook_file, next_findings, next_scores):
    next_scores_by_axis = {}
    for sc in next_scores:
        next_scores_by_axis.setdefault(sc["fr_axis"], []).append(sc["score"])

    results = []
    for rule in hook_file["rules"]:
        if rule["channel"] == "code":
            results.append(audit_code_rule(rule, next_findings))
        else:
            results.append(audit_interview_rule(rule, next_scores_by_axis))

    n_judged = sum(1 for r in results if r["passed"] is not None)
    n_passed = sum(1 for r in results if r["passed"] is True)
    pass_rate = n_passed / n_judged if n_judged else None
    return {
        "hook_file_version": hook_file["version"], "student_id": hook_file["student_id"],
        "n_rules": len(results), "n_judged": n_judged, "n_passed": n_passed,
        "pass_rate": round(pass_rate, 3) if pass_rate is not None else None,
        "per_rule": results,
        "note": (
            "diagnostic separation (plan 5.3 metric 3): 준수율 상승+품질 상승=hook 유효 / "
            "준수율 상승+품질 정체=처방 내용 문제(맞는 걸 처방했지만 효과 없음) / "
            "준수율 하락=전달 그릇 문제(내용이 이전 단계에서부터 실패) -- 이 함수는 준수율만 "
            "계산한다. 품질(FR-04-01 점수 자체의 추세)은 5.3 지표 2와 별도로 대조해야 함."
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hook-file", required=True)
    ap.add_argument("--next-findings", default=None)
    ap.add_argument("--next-transcript", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    hook_file = json.loads(Path(args.hook_file).read_text(encoding="utf-8"))
    next_findings = json.loads(Path(args.next_findings).read_text(encoding="utf-8")) if args.next_findings else []
    next_scores = json.loads(Path(args.next_transcript).read_text(encoding="utf-8")) if args.next_transcript else []

    result = audit(hook_file, next_findings, next_scores)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "per_rule"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
