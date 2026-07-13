# source notebook: Step1. 상품리뷰분석 Agent 1.ipynb (cells 9, 14, 16, 23, 46, 48, 49)
#
# v2.0 변경 (Step1 리뷰 피드백 + Step2 미션 반영):
# - load_api_keys()를 config.py로 옮기고 여기서는 import만 한다. v1.0에서는 이 함수가
#   main.py에 직접 정의돼 있었고 app.py에도 비슷하지만 조금 다른 버전이 따로 있었다
#   (리뷰에서 "import를 쓰지 않은 이유"를 설명하라고 지적받은 부분) -- 지금은 이 파일도
#   app.py도 config.load_api_keys() 하나를 공유한다.
# - DB 입출력을 raw sqlite3 cursor.execute 대신 db.py의 insert_review()/fetch_history()로
#   교체했다. db.py를 import만 해도 테이블이 생성되던 v1.0의 부작용도 사라졌으므로
#   (db.py 상단 주석 참고) init_db()를 명시적으로 호출한다.
# - 미션③: setup_langsmith_tracing()으로 LangSmith trace 환경변수를 켜고, 각
#   app.invoke() 호출에 run_name을 달아 LangSmith UI에서 실행을 구분할 수 있게 했다.
# - display(df)는 Jupyter/Colab 전용 함수라 `python main.py`로 직접 돌리면
#   NameError가 나던 버그가 있었다 -- print(df)로 수정 (독립 스크립트로 실행 가능하게).
# - 노트북의 "기본 제공 라이브러리" import 중 실제로 쓰이지 않던 것들(numpy/matplotlib/
#   seaborn/openai/ast)은 정리했다. sqlite3는 db.py 안으로, os는 config.py 안으로 옮겨갔다.
import json

from config import load_api_keys
from db import init_db, insert_review, fetch_history
from monitoring import setup_langsmith_tracing, trace_run_config
from agent_graph import app

# API 키 로드 (OPENAI_API_KEY, LANGSMITH_API_KEY 등을 api_key.txt 한 파일에서 함께 로드)
load_api_keys()

# 미션③ [필수]: LangSmith trace 환경변수 설정. 이 호출 이후의 모든 llm.invoke /
# app.invoke는 (LANGSMITH_API_KEY가 유효하다면) 자동으로 LangSmith 프로젝트에 기록된다.
setup_langsmith_tracing()

# DB 준비 (테이블 없으면 생성 + v1.0 스키마였다면 verdict/reason_code/retry_count 보강)
init_db()

# 테스트용 데이터 (가짜 예측 결과) -- critic을 거치지 않은 수동 시드 데이터라
# verdict/reason_code/retry_count는 채우지 않는다 (NULL로 저장됨).
review_text = "보습력이 정말 좋아요. 향도 괜찮지만 가격은 조금 비싸요."
seed_items = [
    {"aspect": "보습", "label": 1},
    {"aspect": "향",   "label": 1},
    {"aspect": "가격", "label": 0},
]
insert_review(review_text, seed_items)
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

result = app.invoke(
    initial_state,
    config=trace_run_config(run_name="main-test-run-1"),
)
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
result2 = app.invoke(
    initial_state2,
    config=trace_run_config(run_name="main-test-run-2"),
)

# analyzer_result에서 aspect, label 추출 + critic 최종 판정 저장 (미션④ 재시도 이력)
items         = result2.get("analyzer_result", {}).get("items", [])
critic_result = result2.get("critic_result") or {}
aspects       = [item["aspect"] for item in items]
labels        = [item["label"] for item in items]

row_id = insert_review(
    review2, items,
    verdict=critic_result.get("verdict"),
    reason_code=critic_result.get("reason_code"),
    retry_count=result2.get("retry_count", 0),
)

print("저장 완료!")
print(f"리뷰: {review2}")
print(f"결과: aspect={aspects}, label={labels}")
print(
    f"verdict={critic_result.get('verdict')}, reason_code={critic_result.get('reason_code')}, "
    f"retry_count={result2.get('retry_count', 0)}, row_id={row_id}"
)

# 입력된 데이터 조회
# 원본 노트북은 Colab의 display(df)를 썼지만, 이 파일은 이제 일반 스크립트로도
# 실행 가능해야 하므로(display는 Jupyter/IPython 환경에서만 정의됨) print(df)로 수정.
df = fetch_history()
print(df)
