"""D126 -- 한 라운드 디렉터리의 이미 얼어붙은(git commit) JSON을 personal.db로 동기화.

측정/동결 파이프라인(loop_runner.py, generate_hook_file.py, audit_checklist.py)은
건드리지 않는다 -- 이 스크립트는 그 산출물을 읽기만 하는 별도 스텝이다. 각 라운드의
freeze가 전부 끝난 뒤 1회 실행.

Usage:
  python3 hookfile/db/sync_to_db.py --student-dir experiments/hook_loop/students/gamma_s1/round4
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402


def sync_round(student_dir, conn):
    student_dir = Path(student_dir)
    student_id = student_dir.parent.name
    m = re.search(r"round(\d+)", student_dir.name)
    if not m:
        raise ValueError(f"cannot parse round number from {student_dir}")
    round_num = int(m.group(1))

    n_synced = []

    findings_path = student_dir / "findings.json"
    if findings_path.exists():
        findings = json.loads(findings_path.read_text(encoding="utf-8"))
        store.upsert_findings(conn, student_id, round_num, findings)
        n_synced.append(f"findings={len(findings)}")

    scores_path = student_dir / "interview_scores.json"
    if scores_path.exists():
        scores = json.loads(scores_path.read_text(encoding="utf-8"))
        store.upsert_interview_scores(conn, student_id, round_num, scores)
        n_synced.append(f"interview_scores={len(scores)}")

    # D129: glob은 hookfile_v*.json 전체를 잡는다 -- baseline/curriculum-fixed 두 변형
    # 다 이 패턴에 맞고, variant는 파일명이 아니라 콘텐츠의 curriculum_mode로 구분된다
    # (store.upsert_hook_file_version 참고) -- 파일명 규칙이 또 바뀌어도 안전.
    for hf_path in sorted(student_dir.glob("hookfile_v*.json")):
        hookfile_json = json.loads(hf_path.read_text(encoding="utf-8"))
        store.upsert_hook_file_version(conn, hookfile_json)
        n_synced.append(f"hookfile_v{hookfile_json['version']}_{hookfile_json.get('curriculum_mode', 'baseline')}"
                         f"({len(hookfile_json.get('rules', []))} rules)")

    for audit_path in sorted(student_dir.glob("audit_v*_vs_r*.json")):
        audit_json = json.loads(audit_path.read_text(encoding="utf-8"))
        store.upsert_audit(conn, student_id, round_num, audit_json)
        n_synced.append(f"audit(v{audit_json['hook_file_version']}->r{round_num})")

    print(f"[sync_to_db] {student_id}/round{round_num}: {', '.join(n_synced) or 'nothing to sync'}",
          file=sys.stderr, flush=True)
    return n_synced


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-dir", required=True)
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args()
    conn = store.connect_personal(args.db_path) if args.db_path else store.connect_personal()
    sync_round(args.student_dir, conn)
    conn.close()


if __name__ == "__main__":
    main()
