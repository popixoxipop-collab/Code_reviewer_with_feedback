-- D126 -- 회사자산 저장소(company_assets.db) 스키마.
--
-- WHY 이 스키마엔 student_id(또는 어떤 형태로든 개인을 가리키는 컬럼)가 존재하면 안 된다:
--   개인 저장소(personal.db)와의 경계는 "코드 리뷰 때 조심하자"가 아니라 파일+스키마
--   구조로 강제되어야 한다(hookfile-isolation-guard.py가 측정기 불변식을 코드 레벨로
--   강제하는 것과 같은 원칙). 이 파일에 student_id 컬럼을 추가하는 PR은 그 자체로 이
--   경계를 깨는 것 -- 리뷰 시 최우선으로 거부할 것.
-- COST: 지금은 승격(개인 규칙 -> 회사자산) 로직이 없다. 학생이 gamma_s1 1명뿐이라
--   "여러 학생에서 반복되는 패턴"을 실제로 검증할 데이터가 없기 때문(2026-07-13 D126
--   결정 당시 확인). source_pattern_count만 정수로 남기고 구체적 출처(어느 학생인지)는
--   설계상 저장하지 않는다 -- 나중에 승격 로직을 넣을 때도 "몇 명에서 나왔는지"까지만
--   집계하고 "누구인지"는 이 DB에 절대 넣지 않는다.
-- EXIT: 학생 수가 늘어 일반화가 의미를 가지면, personal.db를 읽어 후보를 뽑고 이 표에
--   candidate로 적재하는 별도 승격 스크립트를 추가한다(이번 스코프 아님).

CREATE TABLE IF NOT EXISTS generalized_rules (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    axis                   TEXT NOT NULL,   -- 취약축 (FR-04-01 5축)
    tech_area              TEXT,
    trigger_pattern        TEXT NOT NULL,   -- 일반화된 trigger (특정 파일명/학생 참조 금지)
    instruction             TEXT NOT NULL,   -- 일반화된 지침_본문
    source_pattern_count    INTEGER NOT NULL DEFAULT 0,  -- 몇 명에게서 유사 패턴이 관측됐는지 "숫자만"
    status                  TEXT NOT NULL CHECK(status IN ('candidate','approved','archived')) DEFAULT 'candidate',
    created_at               TEXT NOT NULL,
    promoted_at              TEXT,           -- approved로 바뀐 시각, nullable
    notes                    TEXT
);
CREATE INDEX IF NOT EXISTS idx_generalized_rules_status ON generalized_rules(status);
