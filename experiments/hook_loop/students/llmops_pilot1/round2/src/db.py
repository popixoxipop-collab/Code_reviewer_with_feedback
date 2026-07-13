# source notebook: Step1. 상품리뷰분석 Agent 1.ipynb (cell 21)
#
# v2.0 변경:
# - v1.0에서는 이 파일을 import만 해도 즉시 DB connect/CREATE TABLE/commit/print가
#   실행됐다 (모듈을 불러오기만 했는데 부작용이 발생 -- "통제 가능한 운영 시스템"과는
#   반대되는 패턴). main.py가 `from db import path`를 할 때마다 매번 테이블 생성 SQL이
#   돌고 "DB 테이블 생성 완료"가 출력됐던 것도 이 부작용 때문이다.
#   -> 함수로 감싸고, 모듈을 그냥 import할 때는 아무 부작용이 없게 바꿨다.
#   `python db.py`로 직접 실행할 때만 기존처럼 테이블을 만들고 메시지를 출력한다
#   (파일 맨 아래 `if __name__ == "__main__"` 참고).
# - 데이터 경로(path)와 API 키 로딩은 config.py로 옮겼다 (Step1 피드백: load_api_keys
#   중복). 이 파일은 `path`라는 이름을 그대로 재노출해서 기존에 `from db import path`로
#   쓰던 코드(main.py)가 깨지지 않게 했다.
# - 미션④(reason_code 기반 재시도 정책) + 미션⑤(대시보드 실행 이력) 를 지원하려면
#   "이 리뷰가 최종적으로 Conformity였는지, 어떤 reason_code로 끝났는지, 재시도를 몇 번
#   했는지"가 DB에 남아야 한다. 그래서 reviews 테이블에 verdict/reason_code/retry_count
#   3개 컬럼을 추가했다. 이미 v1.0 스키마(4컬럼)로 만들어진 reviews.db가 있다면
#   init_db()가 ALTER TABLE로 안전하게 보강한다 (기존 행 삭제 없음).
import json
import os
import sqlite3
from typing import Optional

import pandas as pd

from config import DATA_DIR, DB_PATH

# 기존 코드(main.py 등)가 `from db import path`로 참조하던 이름을 그대로 유지하기 위한
# 재노출(re-export). 실제 정의는 config.py에 있다.
path = DATA_DIR


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """reviews 테이블이 없으면 생성하고, v1.0 스키마로 이미 존재한다면 v2.0에서
    추가된 컬럼(verdict/reason_code/retry_count)을 ALTER TABLE로 보강한다.

    DATA_DIR가 아직 없는 새 환경(예: 로컬에서 PROJ_DATA_DIR를 새 경로로 지정한 경우)을
    위해 디렉터리도 함께 만들어준다.
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            review       TEXT,
            agent_aspect TEXT,
            agent_label  TEXT,
            verdict      TEXT,
            reason_code  TEXT,
            retry_count  INTEGER,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 마이그레이션: 기존 v1.0 DB(4컬럼)에는 verdict/reason_code/retry_count가 없다.
    # PRAGMA table_info로 실제 컬럼을 확인하고 없는 것만 추가한다.
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(reviews)").fetchall()}
    for col, col_type in (("verdict", "TEXT"), ("reason_code", "TEXT"), ("retry_count", "INTEGER")):
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE reviews ADD COLUMN {col} {col_type}")

    conn.commit()
    conn.close()


def insert_review(
    review: str,
    items: list,
    *,
    verdict: Optional[str] = None,
    reason_code: Optional[str] = None,
    retry_count: Optional[int] = None,
) -> int:
    """analyzer_result의 items(list of {"aspect","label",...})를 DB에 저장한다.

    verdict/reason_code/retry_count는 v2.0에서 추가된 선택 인자다 -- critic을 거치지
    않은 수동 시드 데이터를 넣을 때는 생략하면 NULL로 저장된다 (main.py의 "가짜 예측
    결과" 삽입부가 이 케이스).

    Returns:
        새로 삽입된 row의 id.
    """
    aspects = json.dumps([item["aspect"] for item in items], ensure_ascii=False)
    labels = json.dumps([item["label"] for item in items])

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO reviews (review, agent_aspect, agent_label, verdict, reason_code, retry_count)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (review, aspects, labels, verdict, reason_code, retry_count),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def fetch_history(limit: Optional[int] = None) -> pd.DataFrame:
    """저장된 리뷰 분석 이력을 최신순(id DESC)으로 반환한다.

    미션⑤(대시보드 실행 이력 조회)에서 그대로 사용한다. limit을 주지 않으면 전체를
    반환한다. SQL은 파라미터화된 쿼리만 사용한다(보안 규칙 -- limit도 f-string으로
    직접 꽂지 않고 `?` 플레이스홀더로 바인딩).
    """
    conn = get_connection()
    try:
        if limit:
            df = pd.read_sql_query(
                "SELECT * FROM reviews ORDER BY id DESC LIMIT ?", conn, params=(int(limit),)
            )
        else:
            df = pd.read_sql_query("SELECT * FROM reviews ORDER BY id DESC", conn)
    finally:
        conn.close()
    return df


if __name__ == "__main__":
    # `python db.py`로 직접 실행했을 때만 v1.0과 동일하게 즉시 테이블을 만들고 알려준다.
    # (import 시에는 아무 일도 일어나지 않는다 -- 위 변경 요약 참고.)
    init_db()
    print("DB 테이블 생성 완료")
