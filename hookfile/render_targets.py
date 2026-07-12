"""D121 -- Hook File 그릇(container) 렌더러.

확정(D125): 1차 그릇=정적 규칙 파일(교육생 개발 환경 의존 없음). 2차/옵션=실제 Claude
Code Hooks JSON(교육생이 Claude Code 사용자인 경우, 스키마의 trigger/checkable_condition이
event->matcher->handler에 이미 대응해 설계됐으므로 변환 비용이 낮음).

Usage:
  python3 hookfile/render_targets.py --hook-file v1.json --target static --out RULES.md
  python3 hookfile/render_targets.py --hook-file v1.json --target hooks-json --out .claude/settings.local.json
"""
import argparse
import json
from pathlib import Path

AXIS_ORDER = ("코드_이해", "설계_논리", "대안_비교", "반례_대응", "자기_수정")


def render_static(hook_file):
    """1차 그릇 -- CLAUDE.md/AGENTS.md 계열 정적 규칙 파일."""
    lines = [
        f"# Hook File — {hook_file['student_id']} (v{hook_file['version']})",
        "",
        f"> 생성: {hook_file['generated_at']} · 근거 회차: R{hook_file['source_round']} · "
        f"근거 커버리지: {hook_file['coverage']:.0%} · canary: `{hook_file['canary_uuid']}`",
        "",
        "이 파일은 본인의 과거 코드 리뷰/인터뷰에서 실제로 드러난 취약점에서 나온 "
        "개인화 처방입니다. 각 규칙은 근거(finding/transcript/교안 페이지)와 함께 제시됩니다.",
        "",
    ]
    by_axis = {}
    for r in hook_file["rules"]:
        by_axis.setdefault(r["취약축"], []).append(r)

    for axis in AXIS_ORDER:
        rules = by_axis.get(axis)
        if not rules:
            continue
        lines.append(f"## {axis}")
        lines.append("")
        for r in rules:
            lines.append(f"### `{r['rule_id']}` ({'코드' if r['channel'] == 'code' else '인터뷰'} 채널)")
            lines.append("")
            lines.append(f"**적용 조건**: {r['trigger']}")
            lines.append("")
            lines.append(f"**지침**: {r['지침_본문']}")
            lines.append("")
            lines.append(f"**확인 조건**: {r['checkable_condition']}")
            lines.append("")
            ev_lines = []
            for fr in r.get("finding_refs", []):
                ev_lines.append(f"- 코드 finding: `{fr['finding_id']}` ({fr.get('priority', '')})")
            for tr in r.get("transcript_refs", []):
                ev_lines.append(f"- 인터뷰 R{tr['round']} turn#{tr['turn_index']}: {tr['fr_axis']}={tr['score']}점")
            cr = r.get("curriculum_refs")
            if cr:
                ev_lines.append(f"- 교안: Unit {cr.get('unit')} {cr.get('unit_title', '')} (p.{cr.get('source_pages')})")
            if ev_lines:
                lines.append("**근거**:")
                lines.extend(ev_lines)
                lines.append("")
        lines.append("")

    if hook_file.get("deferred_rules"):
        lines.append("## 이번 버전에 안 들어간 항목 (규칙 예산 초과, 다음 버전 후보)")
        lines.append("")
        for d in hook_file["deferred_rules"]:
            lines.append(f"- `{d['rule_id']}` ({d['취약축']}) — {d['trigger']}")
        lines.append("")

    return "\n".join(lines)


def render_hooks_json(hook_file, runtime_check_script_path):
    """2차/옵션 그릇 -- 실제 Claude Code PreToolUse Hooks JSON. trigger 판정은 런타임에
    runtime_check_script_path(별도 companion 스크립트, 이 리포에는 미포함 -- 렌더 시점에
    hook_file의 rules를 그대로 옆에 두고 그 스크립트가 trigger/checkable_condition을
    파싱해 hookSpecificOutput.additionalContext로 지침_본문을 주입하는 방식)가 담당한다.
    """
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                f"python3 {runtime_check_script_path} "
                                f"--hook-file {hook_file['student_id']}_v{hook_file['version']}.json"
                            ),
                        }
                    ],
                }
            ]
        }
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hook-file", required=True)
    ap.add_argument("--target", choices=["static", "hooks-json"], default="static")
    ap.add_argument("--out", required=True)
    ap.add_argument("--runtime-check-script", default="hookfile_runtime_check.py")
    args = ap.parse_args()

    hook_file = json.loads(Path(args.hook_file).read_text(encoding="utf-8"))
    if args.target == "static":
        Path(args.out).write_text(render_static(hook_file), encoding="utf-8")
    else:
        rendered = render_hooks_json(hook_file, args.runtime_check_script)
        Path(args.out).write_text(json.dumps(rendered, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
