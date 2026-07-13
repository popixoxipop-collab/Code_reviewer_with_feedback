"""D126 -- personal.db / company_assets.db 연결+upsert 헬퍼.

기존 JSON 산출물(hookfile_v{N}.json / findings.json / interview_scores.json /
audit_v{N}_vs_r{N+1}.json)을 그대로 인자로 받아 정규화 적재한다. 이 모듈은 새 데이터를
만들지 않는다 -- 이미 git에 얼어붙은 JSON의 파생 조회/휴대용 레이어일 뿐이다.

두 DB는 물리적으로 다른 파일이다(personal.db / company_assets.db) -- 이 모듈에도
둘을 같은 커넥션으로 묶어 쓰는 함수는 없다. company_assets.db 쪽에 student_id를
넘기는 upsert 함수는 존재하지 않는다(스키마에 그 컬럼 자체가 없다, schema_company.sql
참고) -- 실수로 개인 데이터가 회사자산 DB에 흘러들어갈 코드 경로가 아예 없다.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent
PERSONAL_DB_PATH = DB_DIR / "personal.db"
COMPANY_DB_PATH = DB_DIR / "company_assets.db"
_SCHEMA_PERSONAL = DB_DIR / "schema_personal.sql"
_SCHEMA_COMPANY = DB_DIR / "schema_company.sql"


def _connect(db_path, schema_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    return conn


def connect_personal(db_path=PERSONAL_DB_PATH):
    return _connect(db_path, _SCHEMA_PERSONAL)


def connect_company(db_path=COMPANY_DB_PATH):
    return _connect(db_path, _SCHEMA_COMPANY)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _ensure_student(conn, student_id):
    conn.execute(
        "INSERT OR IGNORE INTO students (student_id, created_at) VALUES (?, ?)",
        (student_id, _now()),
    )


def upsert_hook_file_version(conn, hookfile_json):
    """hookfile_v{N}_{variant}.json 딕셔너리를 통째로 받아 hook_file_versions +
    rules(kept+deferred) 적재. 재실행해도 안전(같은 (버전,variant)면 UPDATE+rules
    전량 재삽입) -- RULE_BUDGET 버그처럼 같은 버전을 재생성해 덮어써야 하는 경우나
    D129의 baseline/curriculum-fixed 재실행을 그대로 지원한다.

    D129: variant는 JSON의 curriculum_mode 필드에서 가져온다(파일명 파싱 대신
    콘텐츠 기반 -- 더 견고). 필드가 없는 구버전 파일(D129 이전 생성분)은
    schema_personal.sql의 컬럼 기본값과 동일하게 "baseline"으로 취급."""
    student_id = hookfile_json["student_id"]
    version = hookfile_json["version"]
    variant = hookfile_json.get("curriculum_mode", "baseline")
    _ensure_student(conn, student_id)

    row = conn.execute(
        "SELECT id FROM hook_file_versions WHERE student_id=? AND version=? AND variant=?",
        (student_id, version, variant),
    ).fetchone()
    if row:
        hfv_id = row[0]
        conn.execute(
            "UPDATE hook_file_versions SET generated_at=?, source_round=?, canary_uuid=?, "
            "coverage=?, provenance_commit=? WHERE id=?",
            (hookfile_json["generated_at"], hookfile_json["source_round"],
             hookfile_json["canary_uuid"], hookfile_json.get("coverage"),
             hookfile_json.get("provenance_commit"), hfv_id),
        )
    else:
        cur = conn.execute(
            "INSERT INTO hook_file_versions (student_id, version, variant, generated_at, source_round, "
            "canary_uuid, coverage, provenance_commit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (student_id, version, variant, hookfile_json["generated_at"], hookfile_json["source_round"],
             hookfile_json["canary_uuid"], hookfile_json.get("coverage"),
             hookfile_json.get("provenance_commit")),
        )
        hfv_id = cur.lastrowid

    conn.execute("DELETE FROM rules WHERE hook_file_version_id=?", (hfv_id,))
    for status, rule_list in (("kept", hookfile_json.get("rules", [])),
                               ("deferred", hookfile_json.get("deferred_rules", []))):
        for r in rule_list:
            conn.execute(
                "INSERT INTO rules (hook_file_version_id, student_id, rule_id, channel, axis, "
                "tech_area, trigger_text, checkable_condition, instruction, provenance_hash, "
                "finding_refs_json, transcript_refs_json, curriculum_refs_json, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (hfv_id, student_id, r["rule_id"], r["channel"], r["취약축"], r.get("tech_area"),
                 r.get("trigger"), r.get("checkable_condition"), r.get("지침_본문"),
                 r.get("provenance_hash"),
                 json.dumps(r.get("finding_refs", []), ensure_ascii=False),
                 json.dumps(r.get("transcript_refs", []), ensure_ascii=False),
                 json.dumps(r.get("curriculum_refs", {}), ensure_ascii=False),
                 status),
            )
    conn.commit()
    return hfv_id


def upsert_findings(conn, student_id, round_num, findings_list):
    _ensure_student(conn, student_id)
    conn.execute("DELETE FROM findings WHERE student_id=? AND round_num=?", (student_id, round_num))
    for f in findings_list:
        conn.execute(
            "INSERT INTO findings (student_id, round_num, finding_id, file, pattern_key, "
            "finding_text, priority, design_intent, question_value, risk, subrubric_json, lang) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (student_id, round_num, f["id"], f.get("file"), f.get("pattern_key"),
             f.get("finding"), f.get("priority"), f.get("design_intent"),
             f.get("question_value"), f.get("risk"),
             json.dumps(f.get("subrubric", {}), ensure_ascii=False), f.get("lang")),
        )
    conn.commit()


def upsert_interview_scores(conn, student_id, round_num, scores_list):
    _ensure_student(conn, student_id)
    conn.execute("DELETE FROM interview_scores WHERE student_id=? AND round_num=?",
                 (student_id, round_num))
    for s in scores_list:
        conn.execute(
            "INSERT INTO interview_scores (student_id, round_num, finding_id, ok, axis, fr_axis, "
            "score, criterion, evidence, level, verdict, turns, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (student_id, round_num, s["finding_id"], 1 if s.get("ok") else 0, s.get("axis"),
             s.get("fr_axis"), s.get("score"), s.get("criterion"), s.get("evidence"),
             s.get("level"), s.get("verdict"), s.get("turns"), s.get("error")),
        )
    conn.commit()


def upsert_audit(conn, student_id, next_round, audit_json):
    """audit_v{N}_vs_r{N+1}.json엔 next_round 필드가 없다(파일명에만 있음) -- 호출자가
    라운드 디렉터리에서 알고 있는 값을 명시적으로 넘겨야 한다."""
    _ensure_student(conn, student_id)
    hfv = audit_json["hook_file_version"]
    conn.execute("DELETE FROM audits WHERE student_id=? AND hook_file_version=? AND next_round=?",
                 (student_id, hfv, next_round))
    cur = conn.execute(
        "INSERT INTO audits (student_id, hook_file_version, next_round, n_rules, n_judged, "
        "n_passed, pass_rate, computed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (student_id, hfv, next_round, audit_json.get("n_rules"), audit_json.get("n_judged"),
         audit_json.get("n_passed"), audit_json.get("pass_rate"), _now()),
    )
    audit_id = cur.lastrowid
    for r in audit_json.get("per_rule", []):
        conn.execute(
            "INSERT INTO audit_results (audit_id, rule_id, channel, passed, baseline_score, "
            "next_score, recurred_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (audit_id, r["rule_id"], r["channel"], 1 if r.get("passed") else 0,
             r.get("baseline_score"), r.get("next_score"),
             json.dumps(r["recurred"], ensure_ascii=False) if "recurred" in r else None),
        )
    conn.commit()
    return audit_id
