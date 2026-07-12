"""D126 -- personal.db에서 한 학생의 전체 데이터를 뽑아 기존 JSON 셰이프로 재구성.

이게 실제 "개인이 가져가는" 산출물이다 -- personal.db 파일 자체를 공유하는 게 아니라,
이 스크립트가 만드는 번들(디렉터리 구조가 experiments/hook_loop/students/<id>/round{N}/과
동일)을 학생에게 건넨다. render_targets.py/audit_checklist.py가 그대로 소비 가능하다
(라운드트립 검증 대상).

Usage:
  python3 hookfile/db/export_student.py --student-id gamma_s1 --out-dir /path/to/export
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402


def _row_to_rule(row):
    return {
        "rule_id": row["rule_id"], "channel": row["channel"], "취약축": row["axis"],
        "tech_area": row["tech_area"], "trigger": row["trigger_text"],
        "checkable_condition": row["checkable_condition"], "지침_본문": row["instruction"],
        "provenance_hash": row["provenance_hash"],
        "finding_refs": json.loads(row["finding_refs_json"] or "[]"),
        "transcript_refs": json.loads(row["transcript_refs_json"] or "[]"),
        "curriculum_refs": json.loads(row["curriculum_refs_json"] or "{}"),
    }


def export_student(student_id, out_dir, conn):
    out_dir = Path(out_dir)
    written = []

    hfv_rows = conn.execute(
        "SELECT * FROM hook_file_versions WHERE student_id=? ORDER BY version", (student_id,)
    ).fetchall()
    for hfv in hfv_rows:
        rule_rows = conn.execute(
            "SELECT * FROM rules WHERE hook_file_version_id=? ORDER BY id", (hfv["id"],)
        ).fetchall()
        kept = [_row_to_rule(r) for r in rule_rows if r["status"] == "kept"]
        deferred = [_row_to_rule(r) for r in rule_rows if r["status"] == "deferred"]
        hookfile_json = {
            "student_id": student_id, "version": hfv["version"],
            "generated_at": hfv["generated_at"], "source_round": hfv["source_round"],
            "canary_uuid": hfv["canary_uuid"], "coverage": hfv["coverage"],
            "provenance_commit": hfv["provenance_commit"],
            "deferred_rules": deferred, "rules": kept,
        }
        round_dir = out_dir / f"round{hfv['source_round']}"
        round_dir.mkdir(parents=True, exist_ok=True)
        path = round_dir / f"hookfile_v{hfv['version']}.json"
        path.write_text(json.dumps(hookfile_json, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(str(path))

    round_nums = {r["round_num"] for r in conn.execute(
        "SELECT DISTINCT round_num FROM findings WHERE student_id=? "
        "UNION SELECT DISTINCT round_num FROM interview_scores WHERE student_id=?",
        (student_id, student_id),
    ).fetchall()}
    for round_num in sorted(round_nums):
        round_dir = out_dir / f"round{round_num}"
        round_dir.mkdir(parents=True, exist_ok=True)

        finding_rows = conn.execute(
            "SELECT * FROM findings WHERE student_id=? AND round_num=? ORDER BY id",
            (student_id, round_num),
        ).fetchall()
        if finding_rows:
            findings = [{
                "id": r["finding_id"], "file": r["file"], "pattern_key": r["pattern_key"],
                "finding": r["finding_text"], "priority": r["priority"],
                "design_intent": r["design_intent"], "question_value": r["question_value"],
                "risk": r["risk"], "subrubric": json.loads(r["subrubric_json"] or "{}"),
                "lang": r["lang"],
            } for r in finding_rows]
            path = round_dir / "findings.json"
            path.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
            written.append(str(path))

        score_rows = conn.execute(
            "SELECT * FROM interview_scores WHERE student_id=? AND round_num=? ORDER BY id",
            (student_id, round_num),
        ).fetchall()
        if score_rows:
            scores = [{
                "finding_id": r["finding_id"], "ok": bool(r["ok"]), "axis": r["axis"],
                "fr_axis": r["fr_axis"], "score": r["score"], "criterion": r["criterion"],
                "evidence": r["evidence"], "level": r["level"], "verdict": r["verdict"],
                "turns": r["turns"], **({"error": r["error"]} if r["error"] else {}),
            } for r in score_rows]
            path = round_dir / "interview_scores.json"
            path.write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
            written.append(str(path))

    audit_rows = conn.execute(
        "SELECT * FROM audits WHERE student_id=? ORDER BY next_round", (student_id,)
    ).fetchall()
    for audit in audit_rows:
        result_rows = conn.execute(
            "SELECT * FROM audit_results WHERE audit_id=? ORDER BY id", (audit["id"],)
        ).fetchall()
        per_rule = [{
            "rule_id": r["rule_id"], "channel": r["channel"], "passed": bool(r["passed"]),
            **({"recurred": json.loads(r["recurred_json"])} if r["recurred_json"] is not None else {}),
            **({"baseline_score": r["baseline_score"]} if r["baseline_score"] is not None else {}),
            **({"next_score": r["next_score"]} if r["next_score"] is not None else {}),
        } for r in result_rows]
        audit_json = {
            "hook_file_version": audit["hook_file_version"], "student_id": student_id,
            "n_rules": audit["n_rules"], "n_judged": audit["n_judged"],
            "n_passed": audit["n_passed"], "pass_rate": audit["pass_rate"],
            "per_rule": per_rule,
        }
        round_dir = out_dir / f"round{audit['next_round']}"
        round_dir.mkdir(parents=True, exist_ok=True)
        path = round_dir / f"audit_v{audit['hook_file_version']}_vs_r{audit['next_round']}.json"
        path.write_text(json.dumps(audit_json, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(str(path))

    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args()
    conn = store.connect_personal(args.db_path) if args.db_path else store.connect_personal()
    conn.row_factory = sqlite3.Row
    written = export_student(args.student_id, args.out_dir, conn)
    conn.close()
    print(f"[export_student] {args.student_id}: {len(written)} files -> {args.out_dir}",
          file=sys.stderr, flush=True)
    for p in written:
        print(f"  {p}", file=sys.stderr)


if __name__ == "__main__":
    main()
