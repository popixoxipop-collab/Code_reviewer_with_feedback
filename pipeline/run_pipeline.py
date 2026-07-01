import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COGNITION = os.path.join(ROOT, "cognition", "two_tier_scan.py")
JUDGMENT = os.path.join(ROOT, "judgment", "score_findings.py")
IDIOM_HOOK = os.path.join(ROOT, "judgment", "idiom_hook.py")
TIER_B_HOOK = os.path.join(ROOT, "judgment", "tier_b_hook.py")

# D22: 오케스트레이터는 "무엇이 관용패턴/오탐인지" 스스로 추론하지 않는다 — injections.json을
#   사람이 미리 채운다
#   WHY: 그 판단은 실제 코드 검토가 필요한 지점이다. 자동으로 다 주입하면 잡음(fabricated
#        feedback)이 상태 파일에 섞여 idiom_hook/tier_b_hook의 신뢰도 자체를 오염시킨다
#        (2026-07-01 jxxnixx/LMS 실측: dangerouslySetInnerHTML은 실제로 진짜 위험이라
#        "오탐"으로 주입하면 안 되는 사례였다 — 자동 주입이었다면 이 구분을 못 했을 것)
#   COST: 완전 무인 실행이 안 됨 — injections.json을 사람이 먼저 채워야 함
#   EXIT: 자동 추론이 필요해지면 LLM 판단 단계를 추가하되, 생성된 각 injection에 "note"(왜
#        그렇게 판단했는지)를 강제로 채우게 해 감사 가능성은 유지
#
# 사용법:
#   python3 pipeline/run_pipeline.py <target_src> <injections.json> [output.md]
#
# injections.json 형식 (배열, 순서대로 순차 주입):
#   [{"type": "idiom", "label": "...", "lang": "javascript", "pattern_key": "...",
#     "note": "왜 관용패턴이라 판단했는지", "rounds": 3},
#    {"type": "tier_b", "label": "...", "trigger": "...", "matched_text": "...",
#     "note": "왜 오탐이라 판단했는지", "rounds": 3}]


def run_json(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{result.stderr}")
    return json.loads(result.stdout)


def run_cognition(target_src):
    return run_json([sys.executable, COGNITION, target_src])


def run_judgment(scan_path, target_src):
    return run_json([sys.executable, JUDGMENT, scan_path, target_src])


def apply_injection(injection):
    rounds = injection.get("rounds", 3)
    if injection["type"] == "idiom":
        for i in range(rounds):
            subprocess.run(
                [sys.executable, IDIOM_HOOK, "feedback", injection["lang"], injection["pattern_key"],
                 "idiom_not_decision", f"{injection['note']} (round {i + 1})", injection["note"]],
                capture_output=True, text=True, check=True,
            )
        subprocess.run([sys.executable, IDIOM_HOOK, "update", injection["lang"]],
                        capture_output=True, text=True, check=True)
    elif injection["type"] == "tier_b":
        for i in range(rounds):
            subprocess.run(
                [sys.executable, TIER_B_HOOK, "feedback", injection["trigger"], injection["matched_text"],
                 f"{injection['note']} (round {i + 1})"],
                capture_output=True, text=True, check=True,
            )
        subprocess.run([sys.executable, TIER_B_HOOK, "update"], capture_output=True, text=True, check=True)
    else:
        raise ValueError(f"unknown injection type: {injection['type']}")


def snapshot(findings):
    return {f["id"]: f["question_value"] for f in findings}


def diff_rows(before_snap, after_result):
    after_snap = snapshot(after_result["findings"])
    rows = []
    for fid in sorted(set(before_snap) | set(after_snap)):
        b = before_snap.get(fid, "(없음)")
        a = after_snap.get(fid, "(제거됨)")
        rows.append((fid, b, a, "✅ 변경됨" if b != a else "—"))
    return rows


def render_markdown(repo_label, stage_rows):
    lines = [f"# 재귀 hook 폐루프 검증 — {repo_label}", ""]
    for stage_name, rows in stage_rows:
        lines.append(f"## {stage_name}")
        lines.append("")
        lines.append("| Finding | Before | After | 변화 |")
        lines.append("|---|---|---|---|")
        for fid, b, a, mark in rows:
            lines.append(f"| `{fid}` | {b} | {a} | {mark} |")
        lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 3:
        print("usage: run_pipeline.py <target_src> <injections.json> [output.md]", file=sys.stderr)
        sys.exit(1)
    target_src = sys.argv[1]
    injections_path = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None

    with open(injections_path, encoding="utf-8") as f:
        injections = json.load(f)

    scan = run_cognition(target_src)
    scan_path = "/tmp/_pipeline_scan.json"
    with open(scan_path, "w", encoding="utf-8") as f:
        json.dump(scan, f, ensure_ascii=False)

    baseline = run_judgment(scan_path, target_src)
    print(f"[baseline] {len(baseline['findings'])}건", file=sys.stderr)

    stage_rows = []
    prev_snap = snapshot(baseline["findings"])

    for idx, injection in enumerate(injections, start=1):
        apply_injection(injection)
        result = run_judgment(scan_path, target_src)
        label = injection.get("label", f"주입 {idx}: {injection['type']}")
        stage_rows.append((label, diff_rows(prev_snap, result)))
        prev_snap = snapshot(result["findings"])
        print(f"[{label}] 완료", file=sys.stderr)

    md = render_markdown(target_src, stage_rows)
    print(md)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)


if __name__ == "__main__":
    main()
