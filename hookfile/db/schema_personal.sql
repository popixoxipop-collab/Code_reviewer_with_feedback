-- D126 -- 개인 저장소(personal.db) 스키마.
--
-- 이 파일이 저장하는 데이터는 학생 개인의 것이다(HOOKFILE_SCHEMA.md의 student_id 정의:
-- "익명화된 교육생 식별자"). 이미 존재하는 hookfile_v{N}.json / findings.json /
-- interview_scores.json / audit_v{N}_vs_r{N+1}.json 을 그대로 정규화해서 담을 뿐,
-- 새 데이터를 만들어내지 않는다. company_assets.db(schema_company.sql)와는 물리적으로
-- 다른 파일 -- 절대 같은 DB에 두지 않는다(개인 소유/회사 소유 경계를 파일 경계로 강제).

CREATE TABLE IF NOT EXISTS students (
    student_id   TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL
);

-- D129: variant -- baseline(대조군, _find_curriculum_ref placeholder)과 curriculum-fixed
-- (실제 매칭, hookfile/curriculum_match.py)를 매 회차 한 쌍으로 상시 병행 생성한다.
-- 두 트랙은 curriculum_refs 필드만 다르고 나머지는 동일(rules.instruction 등) -- 그래도
-- 완전히 분리된 hook_file_versions 행으로 관리한다: render_targets.py/audit_checklist.py/
-- export_student.py가 "하나의 Hook File 경로"를 받는 기존 인터페이스를 그대로 재사용할
-- 수 있고(변형 인지 로직 추가 불필요), 두 트랙의 merge_with_previous() 이력도 서로
-- 완전히 독립적으로 유지돼야 하기 때문(baseline이 fixed 위에 잘못 병합되면 안 됨).
CREATE TABLE IF NOT EXISTS hook_file_versions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id          TEXT NOT NULL REFERENCES students(student_id),
    version             INTEGER NOT NULL,
    variant             TEXT NOT NULL DEFAULT 'baseline' CHECK(variant IN ('baseline','curriculum-fixed')),
    generated_at        TEXT NOT NULL,
    source_round        INTEGER NOT NULL,
    canary_uuid         TEXT NOT NULL UNIQUE,
    coverage            REAL,
    provenance_commit   TEXT,
    UNIQUE(student_id, version, variant)
);
CREATE INDEX IF NOT EXISTS idx_hfv_student ON hook_file_versions(student_id);

-- 규칙은 "회차별 스냅샷"이다 -- 같은 rule_id가 v2/v3/v4에 걸쳐 반복돼도 매 버전마다
-- 별도 행이다(merge_with_previous()가 근거를 계속 누적시키는 걸 그대로 반영). audit이
-- "v3 시점 baseline_score vs r4 실측"을 비교하려면 이 스냅샷 이력이 반드시 필요하다 --
-- 최신 상태로 덮어쓰면 정착률(retention) 계산 자체가 불가능해진다.
CREATE TABLE IF NOT EXISTS rules (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    hook_file_version_id    INTEGER NOT NULL REFERENCES hook_file_versions(id),
    student_id              TEXT NOT NULL,  -- denormalized: student-scoped 조회를 join 없이
    rule_id                 TEXT NOT NULL,  -- 예: "코드_이해-01" (student+version 내에서만 유일)
    channel                 TEXT NOT NULL CHECK(channel IN ('code','interview')),
    axis                    TEXT NOT NULL,  -- 취약축 (FR-04-01 5축)
    tech_area               TEXT,
    trigger_text            TEXT,           -- "trigger"는 SQL 예약어라 컬럼명 회피
    checkable_condition     TEXT,
    instruction             TEXT,           -- 지침_본문
    provenance_hash         TEXT,
    finding_refs_json       TEXT,           -- JSON array, 통째로 읽는 provenance라 비정규화
    transcript_refs_json    TEXT,           -- JSON array
    curriculum_refs_json    TEXT,           -- JSON object
    status                  TEXT NOT NULL CHECK(status IN ('kept','deferred')) DEFAULT 'kept',
    UNIQUE(hook_file_version_id, rule_id)
);
CREATE INDEX IF NOT EXISTS idx_rules_student ON rules(student_id);
CREATE INDEX IF NOT EXISTS idx_rules_version ON rules(hook_file_version_id);

CREATE TABLE IF NOT EXISTS findings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    round_num       INTEGER NOT NULL,
    finding_id      TEXT NOT NULL,  -- 예: "architecture-diffusion:Product.java"
    file             TEXT,
    pattern_key      TEXT,
    finding_text     TEXT,
    priority         TEXT,
    design_intent    TEXT,
    question_value   TEXT,
    risk             TEXT,
    subrubric_json   TEXT,          -- JSON object (sub/weights/total 중첩 구조)
    lang             TEXT,
    UNIQUE(student_id, round_num, finding_id)
);
CREATE INDEX IF NOT EXISTS idx_findings_student ON findings(student_id, round_num);

CREATE TABLE IF NOT EXISTS interview_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    round_num       INTEGER NOT NULL,
    finding_id      TEXT NOT NULL,
    ok              INTEGER NOT NULL,  -- boolean 0/1
    axis            TEXT,
    fr_axis         TEXT,
    score           INTEGER,
    criterion       TEXT,
    evidence        TEXT,
    level           TEXT,
    verdict         TEXT,
    turns           INTEGER,
    error           TEXT               -- ok=0일 때만 값 존재
);
CREATE INDEX IF NOT EXISTS idx_interview_student ON interview_scores(student_id, round_num);

CREATE TABLE IF NOT EXISTS audits (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id            TEXT NOT NULL,
    hook_file_version      INTEGER NOT NULL,  -- 기준(baseline)이 된 버전 번호
    next_round             INTEGER NOT NULL,  -- 비교 대상 회차
    n_rules                INTEGER,
    n_judged               INTEGER,
    n_passed                INTEGER,
    pass_rate               REAL,
    computed_at              TEXT,
    UNIQUE(student_id, hook_file_version, next_round)
);
CREATE INDEX IF NOT EXISTS idx_audits_student ON audits(student_id);

CREATE TABLE IF NOT EXISTS audit_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id        INTEGER NOT NULL REFERENCES audits(id),
    rule_id         TEXT NOT NULL,
    channel         TEXT NOT NULL CHECK(channel IN ('code','interview')),
    passed          INTEGER NOT NULL,  -- boolean 0/1
    baseline_score  INTEGER,           -- interview 채널만
    next_score      INTEGER,           -- interview 채널만
    recurred_json   TEXT               -- code 채널만 (보통 빈 배열)
);
CREATE INDEX IF NOT EXISTS idx_audit_results_audit ON audit_results(audit_id);
