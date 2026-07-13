# source notebook: Step1. 상품리뷰분석 Agent 1.ipynb (cell 21)
import sqlite3

path = '/content/drive/MyDrive/proj2_agent/'

# DB 연결
conn = sqlite3.connect(path + "reviews.db")
cursor = conn.cursor()

# 테이블 생성
cursor.execute('''
    CREATE TABLE IF NOT EXISTS reviews (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        review      TEXT,
        agent_aspect TEXT,
        agent_label  TEXT,
        updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# commit
conn.commit()
conn.close()
print("DB 테이블 생성 완료")
