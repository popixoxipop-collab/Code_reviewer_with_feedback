# source notebook: Step1. 상품리뷰분석 Agent 1.ipynb (cells 9, 14, 16, 23, 46, 48, 49)
# [magic] from google.colab import drive
# [magic] drive.mount('/content/drive')

# 기본 제공 라이브러리
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import sqlite3
import json
import os
import openai
import ast
import re

# 더 필요한 라이브러리가 있다면 추가합시다. -----

from db import path
from agent_graph import app


def load_api_keys(filepath="api_key.txt"):
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()


# API 키 로드 및 환경변수 설정
load_api_keys(path + 'api_key.txt')

# DB 연결
conn = sqlite3.connect(path + "reviews.db")
cursor = conn.cursor()

# 테스트용 데이터 (가짜 예측 결과)
review_text  = "보습력이 정말 좋아요. 향도 괜찮지만 가격은 조금 비싸요."
agent_aspect = json.dumps(["보습", "향", "가격"], ensure_ascii=False)
agent_label  = json.dumps([1, 1, 0])

# INSERT 실행
cursor.execute(
    "INSERT INTO reviews (review, agent_aspect, agent_label) VALUES (?, ?, ?)",
    (review_text, agent_aspect, agent_label)
)

# commit
conn.commit()
conn.close()
print("테스트 데이터 입력 완료")

# 실행 테스트 : 리뷰 입력 + Agent 실행
review = '''
잘 사용하고 있어요. 보습력도 좋고 향도 좋아서 잘 사용합니다.
용량도 커서 부담없이 자주 바르고 있어요. 앞으로도 잘 사용할 것 같아요.
보습력 향 모두 만족하는 상품입니다.
'''

initial_state = {
    "review":          review.strip(),
    "analyzer_result": None,
    "critic_result":   None,
    "retry_count":     0,
    "max_retries":     2,
    "next_agent":      "analyzer"
}

result = app.invoke(initial_state)
print(json.dumps(result, ensure_ascii=False, indent=2))

# 실행 테스트2 : 리뷰 입력 + Agent 실행 + DB 저장
review2 = "촉촉하고 좋은데, 향이 좀 부족해요."

# Agent 실행
initial_state2 = {
    "review":          review2.strip(),
    "analyzer_result": None,
    "critic_result":   None,
    "retry_count":     0,
    "max_retries":     2,
    "next_agent":      "analyzer"
}
result2 = app.invoke(initial_state2)

# analyzer_result에서 aspect, label 추출
items    = result2.get("analyzer_result", {}).get("items", [])
aspects  = [item["aspect"] for item in items]
labels   = [item["label"]  for item in items]

agent_aspect = json.dumps(aspects, ensure_ascii=False)
agent_label  = json.dumps(labels)

# DB 연결
conn   = sqlite3.connect(path + "reviews.db")
cursor = conn.cursor()

# INSERT
cursor.execute(
    "INSERT INTO reviews (review, agent_aspect, agent_label) VALUES (?, ?, ?)",
    (review2, agent_aspect, agent_label)
)
conn.commit()
conn.close()

print(f"저장 완료!")
print(f"리뷰: {review2}")
print(f"결과: aspect={aspects}, label={labels}")

# 입력된 데이터 조회
conn = sqlite3.connect(path + "reviews.db")
df   = pd.read_sql_query("SELECT * FROM reviews", conn)
conn.close()
display(df)
