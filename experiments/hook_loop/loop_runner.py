"""D122 -- Hook File 재귀 루프 회차 오케스트레이터 (측정/동결/처방 부분).

"학생이 과제를 코딩하는" 단계는 이 스크립트가 자동화하지 않는다 -- 그건 Claude Code
Agent 호출이 필요한 단계라 순수 파이썬 서브프로세스로 흉내낼 수 없다(별도 claude -p
세션은 되지만, 이 실험은 Agent tool로 신선한(메타정보 없는) 컨텍스트를 직접 통제하는
쪽을 선택 -- GAMMA_DESIGN.md 참고). 이 스크립트는 그 사이사이(측정/동결/처방)를 맡는다.

Usage (한 회차의 코드가 이미 <student_dir>/src/에 있다고 가정):
  python3 experiments/hook_loop/loop_runner.py measure-code \\
    --student-dir experiments/hook_loop/students/gamma_s1/round1 --out findings.json

  python3 experiments/hook_loop/loop_runner.py measure-interview \\
    --student-dir experiments/hook_loop/students/gamma_s1/round1 \\
    --findings findings.json --persona-prompt-file persona.txt --out scores.json \\
    [--hook-summary-file prev_hook_summary.txt]  # R2+에서만

  python3 experiments/hook_loop/loop_runner.py freeze --path experiments/hook_loop/students/gamma_s1/round1
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "feedback"))
sys.path.insert(0, str(REPO / "cognition"))
sys.path.insert(0, str(REPO / "judgment"))
sys.path.insert(0, str(REPO))

from turn_engine import run_decision_point, _transcript_text  # noqa: E402
from llm_interview_grader import grade_answer, _build_client  # noqa: E402
from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402
from timeout_config import DEFAULT_TIMEOUT_S  # noqa: E402
import interview_rubric  # noqa: E402

MODEL = "qwen/qwen3-next-80b-a3b-instruct"  # 팀 Locked
MAX_FINDINGS_PER_ROUND = 5  # 비용/시간 통제 -- 회차당 최대 이만큼만 인터뷰
ANSWER_MODEL = os.environ.get("GAMMA_ANSWER_MODEL", "haiku")
ANSWER_TIMEOUT_S = 60.0  # timeout-guard: allow (claude -p 서브프로세스, NVIDIA 콜 아님)
ANSWER_MAX_BUDGET_USD = "0.50"  # timeout-guard: allow (claude -p 예산 한도, NVIDIA 아님)
QUOTA_EXHAUSTED_MARKERS = ("weekly limit", "usage limit", "hit your")  # D107 계보


def log(msg):
    print(f"[loop_runner] {msg}", file=sys.stderr, flush=True)


def _run_scan_judge(src_dir):
    """cognition/two_tier_scan.py + judgment/score_findings.py 직접 호출(M1 harness와 동일 패턴)."""
    scan_res = subprocess.run(
        [sys.executable, str(REPO / "cognition" / "two_tier_scan.py"), str(src_dir)],
        capture_output=True, text=True, timeout=60,  # timeout-guard: allow (local deterministic scan)
    )
    scan = json.loads(scan_res.stdout)
    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(scan, f)
    try:
        judge_res = subprocess.run(
            [sys.executable, str(REPO / "judgment" / "score_findings.py"), tmp_path, str(src_dir)],
            capture_output=True, text=True, timeout=60,  # timeout-guard: allow (local deterministic judge)
        )
    finally:
        os.unlink(tmp_path)
    return scan, json.loads(judge_res.stdout)


def cmd_measure_code(student_dir, out_path):
    src_dir = Path(student_dir) / "src"
    scan, judgment = _run_scan_judge(src_dir)
    findings = judgment.get("findings", [])
    Path(out_path).write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"measure-code: {len(findings)} findings -> {out_path}")
    return findings


def _persona_answer(persona_prompt_template, context, question):
    prompt = persona_prompt_template.format(context=context, question=question)
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", ANSWER_MODEL, "--safe-mode",
         "--no-session-persistence", "--max-budget-usd", ANSWER_MAX_BUDGET_USD],
        capture_output=True, text=True, timeout=ANSWER_TIMEOUT_S,  # timeout-guard: allow (claude -p, not NVIDIA)
    )
    text = (result.stdout or "").strip()
    if not text:
        raise RuntimeError(f"empty answer-agent output (rc={result.returncode}): {(result.stderr or '')[:300]!r}")
    if any(m in text for m in QUOTA_EXHAUSTED_MARKERS):
        raise RuntimeError(f"claude -p returned a usage-limit message, not an answer: {text[:200]!r}")
    return text


def cmd_measure_interview(student_dir, findings, persona_prompt_template, out_path, max_findings=MAX_FINDINGS_PER_ROUND):
    src_dir = Path(student_dir) / "src"
    priority_rank = {"최우선": 0, "Important(🔴)": 1, "질문 대상": 2, "검토 대상(자동 신뢰 금지)": 3}
    sample = sorted(findings, key=lambda f: priority_rank.get(f.get("priority"), 9))[:max_findings]
    log(f"measure-interview: {len(sample)}/{len(findings)} findings sampled (priority order)")

    pool = NvidiaKeyPool.from_env()
    client = NvidiaRotatingClient(pool=pool, timeout_s=DEFAULT_TIMEOUT_S)
    grader_client = _build_client()

    results = []
    for i, finding in enumerate(sample, 1):
        context = finding.get("finding", "")

        def answer_fn(question, level, _ctx=context):
            return _persona_answer(persona_prompt_template, _ctx, question)

        t0 = time.time()
        try:
            interview = run_decision_point(finding, str(src_dir), answer_fn, client, MODEL)
        except Exception as e:
            log(f"[{i}/{len(sample)}] {finding['id']}: interview FAILED: {type(e).__name__}: {e}")
            results.append({"finding_id": finding["id"], "ok": False, "error": str(e)})
            continue

        question = interview["transcript"][0]["question"] if interview["transcript"] else ""
        answer_text = _transcript_text(interview["transcript"])
        try:
            grades = grade_answer(grader_client, finding, question, answer_text)
        except Exception as e:
            log(f"[{i}/{len(sample)}] {finding['id']}: grading FAILED: {type(e).__name__}: {e}")
            results.append({"finding_id": finding["id"], "ok": False, "error": f"grading: {e}", "verdict": interview["verdict"]})
            continue

        for axis in interview_rubric.AXES:
            fr_axis = interview_rubric.FR_AXIS_ALIAS[axis]
            score = grades.get(fr_axis, {}).get("score") if isinstance(grades.get(fr_axis), dict) else grades.get(fr_axis)
            if score is None:
                continue
            results.append({
                "finding_id": finding["id"], "ok": True, "axis": axis, "fr_axis": fr_axis,
                "score": score, "criterion": interview_rubric.describe(axis, score) if score in range(1, 6) else None,
                "evidence": answer_text[:300], "level": interview["transcript"][-1]["level"] if interview["transcript"] else None,
                "verdict": interview["verdict"], "turns": interview["turns"],
            })
        log(f"[{i}/{len(sample)}] {finding['id']}: verdict={interview['verdict']} turns={interview['turns']} ({time.time()-t0:.1f}s)")

    Path(out_path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"wrote {out_path}")
    return results


def cmd_freeze(path):
    """D123 layer 3 준비 -- 측정 raw를 커밋해 generate_hook_file.py의 temporal firewall이
    통과할 수 있는 상태로 만든다."""
    rel = str(Path(path).resolve().relative_to(REPO))
    subprocess.run(["git", "-C", str(REPO), "add", rel], check=True, timeout=30)  # timeout-guard: allow (local git add)
    r = subprocess.run(
        ["git", "-C", str(REPO), "commit", "-m", f"data(hook_loop): freeze {rel}"],
        capture_output=True, text=True, timeout=30,  # timeout-guard: allow (local git commit)
    )
    log(f"freeze: {r.stdout.strip() or r.stderr.strip()}")
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("measure-code")
    p1.add_argument("--student-dir", required=True)
    p1.add_argument("--out", required=True)

    p2 = sub.add_parser("measure-interview")
    p2.add_argument("--student-dir", required=True)
    p2.add_argument("--findings", required=True)
    p2.add_argument("--persona-prompt-file", required=True)
    p2.add_argument("--out", required=True)
    p2.add_argument("--max-findings", type=int, default=MAX_FINDINGS_PER_ROUND)

    p3 = sub.add_parser("freeze")
    p3.add_argument("--path", required=True)

    args = ap.parse_args()
    if args.cmd == "measure-code":
        cmd_measure_code(args.student_dir, args.out)
    elif args.cmd == "measure-interview":
        findings = json.loads(Path(args.findings).read_text(encoding="utf-8"))
        persona = Path(args.persona_prompt_file).read_text(encoding="utf-8")
        cmd_measure_interview(args.student_dir, findings, persona, args.out, max_findings=args.max_findings)
    elif args.cmd == "freeze":
        cmd_freeze(args.path)


if __name__ == "__main__":
    main()
