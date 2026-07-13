# source notebook: Ch10. [보조자료]Agent 시스템 구축을 위한 필요 기술들.ipynb

# --- cell 0 ---
# --- markdown ---
# # **Agent 시스템 구축을 위한 필요 기술들**

# --- cell 1 ---
# --- markdown ---
# ## **1. 환경준비**

# --- cell 2 ---
# --- markdown ---
# * 필요한 라이브러리 설치

# --- cell 3 ---
# [magic] !pip install -q streamlit

# --- cell 4 ---
# --- markdown ---
# * 라이브러리 로딩

# --- cell 5 ---
import json
import sqlite3
import pandas as pd

# --- cell 6 ---
# --- markdown ---
# ## **2. JSON**

# --- cell 7 ---
# --- markdown ---
# ### (1) json 기본 예제

# --- cell 8 ---
text = '{"name": "AIVLE", "year": 2026, "topics": ["json", "sqlite", "streamlit"]}'
data = json.loads(text)

print(data)
print(type(data))
print(data["name"])

# --- cell 9 ---
# --- markdown ---
# ### (2) json의 따옴표

# --- cell 10 ---
# json 내에서 키와 값은 큰 따옴표를 사용해야 합니다!
text = '{"aspect": "보습", "label": 1}'
data = json.loads(text)
print(data)

# --- cell 11 ---
# 아래 코드는 오류 발생 : json 내에서 작은 따옴표 사용
text = "{'aspect': '보습', 'label': 1}"
data = json.loads(text)
print(data)

# --- cell 12 ---
# --- markdown ---
# ### (3) JSON 읽기와 저장

# --- cell 13 ---
# --- markdown ---
# #### 1) 문자열 json으로 저장 및 읽기
# * json.dumps()는 기본적으로 ASCII 문자만 사용하도록 설정 : 한글을 Unicode escape 형태 (\uXXXX)로 변환
# * json 문자열을 json으로 로딩(파이썬 딕셔너리로)

# --- cell 14 ---
data = {"aspect": "보습", "label": 1}

json_text = json.dumps(data)
print(json_text)
print(type(json_text))

restored = json.loads(json_text)
print(restored)
print(type(restored))

# --- cell 15 ---
# --- markdown ---
# * 한글을 그대로 출력하려면 ensure_ascii=False 옵션 사용

# --- cell 16 ---
data = {"aspect": "보습", "label": 1}

json_text = json.dumps(data, ensure_ascii=False)
print(json_text)
print(type(json_text))

restored = json.loads(json_text)
print(restored)
print(type(restored))

# --- cell 17 ---
# --- markdown ---
# #### 2) json 파일로 저장 및 읽기

# --- cell 18 ---
data = {
    "review": "보습력은 좋고 향도 좋아요.",
    "items": [{"aspect": "보습", "label": 1},
              {"aspect": "향", "label": 1}]
}

# 저장
with open("result.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 읽기
with open("result.json", "r", encoding="utf-8") as f:
    loaded = json.load(f)

print(loaded)

# --- cell 19 ---
# --- markdown ---
# ### (4) 실습

# --- cell 20 ---
data1 = {
    "review": "보습력은 좋고 향도 좋아요.",
    "items": [{"aspect": "보습", "label": 1},
              {"aspect": "향", "label": 1}]
}

# json으로 변환(.dumps)하여 data2로 저장
data2 = json.dumps(data, ensure_ascii=False)
print(data2)

# --- cell 21 ---
# data1, data2 타입 확인
type(data1), type(data2)

# --- cell 22 ---
# json을 로딩하기(.loads)
data3 = json.loads(data2)

# 내용 출력, 타입 확인
print(data3)
print(type(data3))

# --- cell 23 ---
# --- markdown ---
# ## **3. SQLite**

# --- cell 24 ---
# --- markdown ---
# ### (1) DB, 테이블 만들기

# --- cell 25 ---
# DB 연결하기, 만약 없으면 생성하고 연결
conn = sqlite3.connect("testdb.db")

# --- cell 26 ---
# 커서 선언
cursor = conn.cursor()

# SQL문 실행
cursor.execute("""
CREATE TABLE movies (
    id INTEGER PRIMARY KEY,
    movie_name TEXT,
    genre TEXT,
    year INTEGER
)
""")

# SQL문 실행 완료
conn.commit()

# DB 연결 끊기
conn.close()

# --- cell 27 ---
# --- markdown ---
# ### (2) 데이터 입력하기(INSERT)

# --- cell 28 ---
# --- markdown ---
# * 데이터 1 건 입력하기

# --- cell 29 ---
conn = sqlite3.connect("testdb.db")
cursor = conn.cursor()

cursor.execute(
    "INSERT INTO movies (movie_name, genre, year) VALUES (?, ?, ?)",
    ("타이타닉", "드라마", 1997)
)

conn.commit()
conn.close()

# --- cell 30 ---
# --- markdown ---
# * 데이터 여러 건 입력하기

# --- cell 31 ---
conn = sqlite3.connect("testdb.db")
cursor = conn.cursor()

movies_data = [
    ("기생충", "드라마", 2019),
    ("극한직업", "코미디", 2019),
    ("명량", "액션", 2014),
    ("K-POP 데몬헌터스", "애니메이션", 2025),
    ("어벤져스: 엔드게임", "액션", 2019),
    ("라라랜드", "뮤지컬", 2016),
    ("인셉션", "SF", 2010),
    ("인터스텔라", "SF", 2014),
    ("알라딘", "판타지", 2019),
    ("범죄도시", "액션", 2017)
]

cursor.executemany(
    "INSERT INTO movies (movie_name, genre, year) VALUES (?, ?, ?)",
    movies_data
)

conn.commit()
conn.close()

# --- cell 32 ---
# --- markdown ---
# * 데이터프레임을 그대로 DB 테이블에 입력하기

# --- cell 33 ---
# 영화 데이터 생성
data = {"movie_name": [ "노팅힐", "반지의 제왕", "듄", "매트릭스", "위대한 쇼맨"],
        "genre": [ "로맨스", "판타지", "SF", "SF", "뮤지컬"],
        "year": [1999, 1999, 2019, 1999, 2017]
}

# DataFrame 생성
df = pd.DataFrame(data)
df

# --- cell 34 ---
# --- markdown ---
# * pandas 함수 사용

# --- cell 35 ---
conn = sqlite3.connect("testdb.db")

df.to_sql("movies", conn,
            if_exists="append",   # 기존 테이블에 추가
            index=False           # DataFrame index 저장 안함
)

conn.close()

# --- cell 36 ---
# --- markdown ---
# ### (3) 데이터 조회(SELECT)

# --- cell 37 ---
# --- markdown ---
# * 데이터를 튜플 형태로 조회하기

# --- cell 38 ---
conn = sqlite3.connect("testdb.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM movies")
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()

# --- cell 39 ---
# --- markdown ---
# * pandas 함수 사용

# --- cell 40 ---
conn = sqlite3.connect("testdb.db")
df = pd.read_sql("SELECT * FROM movies", conn)
conn.close()
df

# --- cell 41 ---
# --- markdown ---
# ### (4) 데이터 수정(UPDATE)

# --- cell 42 ---
conn = sqlite3.connect("testdb.db")
cursor = conn.cursor()

cursor.execute(
    "UPDATE movies SET genre = ? WHERE movie_name = ?",
    ("애니메이션", "알라딘")
)

conn.commit()
conn.close()

# --- cell 43 ---
conn = sqlite3.connect("testdb.db")
df = pd.read_sql("SELECT * FROM movies", conn)
conn.close()
df

# --- cell 44 ---
# --- markdown ---
# ### (5) 데이터 삭제(DELETE)

# --- cell 45 ---
conn = sqlite3.connect("testdb.db")
cursor = conn.cursor()

cursor.execute(
    "DELETE FROM movies WHERE year < ?",
    (2015,)
)

conn.commit()
conn.close()

# --- cell 46 ---
conn = sqlite3.connect("testdb.db")
df = pd.read_sql("SELECT * FROM movies", conn)
conn.close()
df

# --- cell 47 ---
# --- markdown ---
# ### (6) 실습
# * 데이터 경로 : `https://raw.githubusercontent.com/DA4BAM/dataset/refs/heads/master/Carseat_simple.csv`
# * 요구사항
#     * CSV 파일을 DataFrame으로 불러오기
#     * `testdb.db`에 테이블 `carseat`로 저장
#     * 저장된 데이터를 조회하기
#     * 데이터를 수정 : `ShelveLoc`가 'Bad'인 데이터의 `Urban` 값을 'No'로 수정
#     * 데이터 삭제 : `US`가 'No'인 데이터 삭제
# 특정 조건의 데이터를 삭제하기

# --- cell 48 ---
# CSV를 DataFrame으로 불러오기
url = "https://raw.githubusercontent.com/DA4BAM/dataset/refs/heads/master/Carseat_simple.csv"
df = pd.read_csv(url)

print(df.head())

# --- cell 49 ---
# SQLite DB에 테이블로 저장
conn = sqlite3.connect("testdb.db")

df.to_sql(
    "carseat",
    conn,
    if_exists="replace",   # 기존 테이블이 있으면 새로 생성
    index=False
)

conn.close()

# --- cell 50 ---
# 데이터 수정 : ShelveLoc가 "Bad"인 데이터의 Urban 값을 "No"로 수정
conn = sqlite3.connect("testdb.db")
cursor = conn.cursor()

cursor.execute("""
UPDATE carseat SET Urban = ? WHERE ShelveLoc = ?
""", ("No", "Bad"))

conn.commit()
conn.close()

# --- cell 51 ---
# 데이터 삭제 : US가 "No"인 데이터 삭제
conn = sqlite3.connect("testdb.db")
cursor = conn.cursor()

cursor.execute("""
DELETE FROM carseat WHERE US = ?
""", ("No",))

conn.commit()
conn.close()

# --- cell 52 ---
# 결과 조회하기
conn = sqlite3.connect("testdb.db")

result_df = pd.read_sql("SELECT * FROM carseat", conn)
print(result_df.head())
print("남은 데이터 건수:", len(result_df))

conn.close()

# --- cell 53 ---
# --- markdown ---
# ## **4. Streamlit 예제**
# * 아래 예제는 streamlit 공식 사이트를 참조합니다.
# * 각 예제는 다음과 같은 절차로 진행합니다.
#     * 스트림릿 코드 개발 및 저장(.py)
#     * 서버 실행
#     * 임시 공개 URL 생성 및 접속

# --- cell 54 ---
# --- markdown ---
# * Cloudflare Tunnel 설치

# --- cell 55 ---
# [magic] !wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
# [magic] !dpkg -i cloudflared-linux-amd64.deb

# --- cell 56 ---
# --- markdown ---
# ### (1) Hello Streamlit-er

# --- cell 57 ---
# --- markdown ---
# * 스트림릿 코드 개발 및 저장(.py)

# --- cell 58 ---
# [cell-magic] %%writefile app1.py

import streamlit as st

st.title("Hello Streamlit-er 👋")
st.markdown(
    """
    This is a playground for you to try Streamlit and have fun.

    **There's :rainbow[so much] you can build!**

    We prepared a few examples for you to get started. Just
    click on the buttons above and discover what you can do
    with Streamlit.
    """
)

if st.button("Send balloons!"):
    st.balloons()

# --- cell 59 ---
# --- markdown ---
# * Streamlit 서버 시작 : app1.py

# --- cell 60 ---
# [magic] !pkill -9 -f streamlit || true
# [magic] !rm -f streamlit.log

# [magic] !streamlit run app1.py \
  --server.port 8501 \
  --server.address 127.0.0.1 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  > streamlit.log 2>&1 &

# --- cell 61 ---
# --- markdown ---
# * 임시 공개 URL 생성 및 접속

# --- cell 62 ---
# [magic] !cloudflared tunnel --url http://127.0.0.1:8501

# --- cell 63 ---
# --- markdown ---
# * streamlit 서버 URL 연결을 끊기 위해서는 위 코드셀을 중단하세요.

# --- cell 64 ---
# --- markdown ---
# ### (2) Charts①

# --- cell 65 ---
# --- markdown ---
# * 스트림릿 코드 개발 및 저장(.py)

# --- cell 66 ---
# [cell-magic] %%writefile app2.py

import streamlit as st
import pandas as pd
import numpy as np

st.write("Streamlit supports a wide range of data visualizations, including [Plotly, Altair, and Bokeh charts](https://docs.streamlit.io/develop/api-reference/charts). 📊 And with over 20 input widgets, you can easily make your data interactive!")

all_users = ["Alice", "Bob", "Charly"]
with st.container(border=True):
    users = st.multiselect("Users", all_users, default=all_users)
    rolling_average = st.toggle("Rolling average")

np.random.seed(42)
data = pd.DataFrame(np.random.randn(20, len(users)), columns=users)
if rolling_average:
    data = data.rolling(7).mean().dropna()

tab1, tab2 = st.tabs(["Chart", "Dataframe"])
tab1.line_chart(data, height=250)
tab2.dataframe(data, height=250, use_container_width=True)

# --- cell 67 ---
# --- markdown ---
# * Streamlit 서버 시작 : app2.py

# --- cell 68 ---
# [magic] !pkill -9 -f streamlit || true
# [magic] !rm -f streamlit.log

# [magic] !streamlit run app2.py \
  --server.port 8501 \
  --server.address 127.0.0.1 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  > streamlit.log 2>&1 &

# --- cell 69 ---
# --- markdown ---
# * 임시 공개 URL 생성 및 접속
#     * 아래 코드가 실행된 후 약 5초 후에 링크를 누르세요.

# --- cell 70 ---
# [magic] !cloudflared tunnel --url http://127.0.0.1:8501

# --- cell 71 ---
# --- markdown ---
# ### (3) Charts②

# --- cell 72 ---
# [cell-magic] %%writefile app3.py

# app3.py --------------------------------------------
import pandas as pd
import streamlit as st
import seaborn as sns
import matplotlib.pyplot as plt

st.title("Titanic Dashboard")


# 데이터 캐싱 -----------------------------
@st.cache_data  # 다음 함수 실행시 데이터를 캐싱
def load_data(url):
    return pd.read_csv(url)

url = "https://raw.githubusercontent.com/DA4BAM/dataset/refs/heads/master/titanic_simple.csv"
df = load_data(url)

# UI : 칼럼을 나누고, 라디오버튼1,2, 슬라이더 구성 -------------
st.subheader("필터")
col1, col2, col3 = st.columns(3)

with col1:
    sex = st.radio("성별", ["All", "male", "female"])

with col2:
    embarked = st.radio("탑승지", ["All", "Cherbourg", "Queenstown", "Southampton"])

with col3:
    age_min,age_max = df["Age"].min(), df["Age"].max()
    age_range = st.slider("나이 범위", age_min, age_max, (age_min, age_max))

# 필터링 --------------------
f = df.copy()

if sex != "All":
    f = f.loc[f["Sex"] == sex]

if embarked != "All":
    f = f.loc[f["Embarked"] == embarked]

f = f.loc[f["Age"].between(age_range[0], age_range[1])]

st.write("필터 후 데이터 수 :", len(f))
st.divider()

# 그래프 및 데이터조회 ----------
left, right = st.columns(2)

# 생존 여부 막대그래프
with left:
    st.subheader("생존 여부")
    surv = f["Survived"].replace({0: "Died", 1: "Survived"})
    st.bar_chart(surv.value_counts())

# 운임 KDE plot (Seaborn)
with right:
    st.subheader("운임(Fare) KDE plot")
    fig, ax = plt.subplots()
    sns.kdeplot(data = f, x = 'Fare', ax=ax, hue = 'Survived', common_norm = False)
    ax.set_xlabel("Fare")
    ax.set_ylabel("Count")
    st.pyplot(fig)

st.divider()

# 데이터 보기
with st.expander("데이터 보기"):
    st.dataframe(f)

# --- cell 73 ---
# --- markdown ---
# * Streamlit 서버 시작 : app3.py

# --- cell 74 ---
# [magic] !pkill -9 -f streamlit || true
# [magic] !rm -f streamlit.log

# [magic] !streamlit run app3.py \
  --server.port 8501 \
  --server.address 127.0.0.1 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  > streamlit.log 2>&1 &

# --- cell 75 ---
# --- markdown ---
# * 임시 공개 URL 생성 및 접속
#     * 아래 코드가 실행된 후 약 5초 후에 링크를 누르세요.

# --- cell 76 ---
# [magic] !cloudflared tunnel --url http://127.0.0.1:8501

# --- cell 78 ---
# --- markdown ---
# ### (4) 실습
# * 다음 요구사항을 적용해서 구성해 봅시다.
#     * 다음 경로의 데이터를 `pd.read_csv`로 읽어서 `testdb.db`에 `mobile`이라는 테이블로 저장합니다.
#         * 데이터 경로 : `https://raw.githubusercontent.com/DA4BAM/dataset/refs/heads/master/mobile_2000.csv`
#     * 데이터 캐싱
#         * DB로 부터 데이터를 읽어서 데이터프레임으로 저장하는 함수를 만들고
#         * 캐싱을 위한 데코레이터를 붙입니다.
#     * UI : 3개 칼럼으로 구성
#         * 대학 졸업 여부(`COLLEGE`) : 라디오버튼
#         * 만족도(`REPORTED_SATISFACTION`) : 다중선택
#         * 집값(`HOUSE`) : 슬라이더
#     * 필터된 결과 : 2개 칼럼으로 구성
#         * `st.write`가 아닌 `st.metric`을 사용
#         * 필터된 데이터 건수
#         * 필터된 데이터 이탈율(`CHURN` 칼럼의 'LEAVE' 비율)
#     * 그래프 : 2개 칼럼으로 구성
#         * 이탈여부 막대 그래프
#         * 초과 사용시간(`OVERAGE`) kde plot
#     * 데이터 조회

# --- cell 79 ---
# --- markdown ---
# * 데이터 설명
# |	구분	|	변수 명	|	내용	|	type	|	비고	|
# |----|----|----|----|----|
# |	**Target**	|	**CHURN**	|	이탈여부	|	범주	| LEAVE,STAY	|
# |	feature	|	COLLEGE	|	대학졸업여부	|	범주	| 0, 1 |
# |	feature	|	INCOME	|	소득수준(달러)	|	숫자	|		|
# |	feature	|	OVERAGE	|	월평균 초과사용시간(분)	|	숫자	| |
# |	feature	|	LEFTOVER	|	월평균 잔여시간(%)	|	숫자	| 	|
# |	feature	|	HOUSE	|	집가격(달러)	|	숫자	|	|
# |	feature	|	HANDSET_PRICE	|	휴대폰가격(달러)	|	숫자	|		|
# |	feature	|	AVERAGE_CALL_DURATION	|	평균통화시간(분)	|	숫자	|		|
# |	feature	|	REPORTED_SATISFACTION	|	만족도설문	|	범주	| 1(매우불만) ~ 5(매우만족) |

# --- cell 80 ---
# CSV를 DataFrame으로 불러와서 SQLite DB에 테이블로 저장
url = "https://raw.githubusercontent.com/DA4BAM/dataset/refs/heads/master/mobile_2000.csv"
conn = sqlite3.connect("testdb.db")
pd.read_csv(url).to_sql("mobile", conn, if_exists="replace", index=False)
conn.close()

# --- cell 81 ---
# [cell-magic] %%writefile app4.py

# 라이브러리 로딩 --------------------------------------------
import pandas as pd
import streamlit as st
import seaborn as sns
import matplotlib.pyplot as plt
import sqlite3

st.title("Mobile Customer Dashboard")

# 데이터 캐싱 -----------------------------
@st.cache_data
def load_data(db_name, table_name):
    conn = sqlite3.connect(db_name)
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    conn.close()

    return df
df = load_data("testdb.db", "mobile")

# UI : 칼럼을 나누고, 라디오버튼, 다중선택, 슬라이더 구성 -------------
st.subheader("필터")
col1, col2, col3 = st.columns(3)

with col1:
    college = st.radio("대학 졸업 여부(COLLEGE)", ["All", "0", "1"])

with col2:
    sat_options = [1,2,3,4,5]
    satisfaction = st.multiselect("만족도(REPORTED_SATISFACTION)", sat_options, default = sat_options)

with col3:
    house_min, house_max = df["HOUSE"].min(), df["HOUSE"].max()
    house_range = st.slider("집값(HOUSE)", house_min, house_max, (house_min, house_max))

# 필터링 --------------------
f = df.copy()

if college != "All":
    f = f.loc[f["COLLEGE"] == int(college)]

if len(satisfaction) > 0:
    f = f.loc[f["REPORTED_SATISFACTION"].isin(satisfaction)]

f = f.loc[f["HOUSE"].between(house_range[0], house_range[1])]

st.divider()

# 필터된 결과 : 2개 칼럼(metric) ----------
m1, m2 = st.columns(2)

with m1:
    st.metric("필터된 데이터 건수", len(f))

with m2:
    churn_rate = (f["CHURN"] == "LEAVE").mean() * 100
    st.metric("필터된 데이터 이탈율(%)", f"{churn_rate:.1f}")

st.divider()

# 그래프 및 데이터조회 ----------
left, right = st.columns(2)

# 이탈여부 막대 그래프
with left:
    st.subheader("이탈 여부")
    st.bar_chart(f["CHURN"].value_counts())

# 초과 사용시간(OVERAGE) KDE plot
with right:
    st.subheader("초과 사용시간(OVERAGE) KDE plot")
    fig, ax = plt.subplots()
    sns.kdeplot(data=f, x="OVERAGE", ax=ax, hue="CHURN", common_norm = False)
    ax.set_xlabel("OVERAGE")
    ax.set_ylabel("Density")
    st.pyplot(fig)

st.divider()

# 데이터 보기
with st.expander("데이터 보기"):
    st.dataframe(f)

# --- cell 82 ---
# --- markdown ---
# * Streamlit 서버 시작 : app4.py

# --- cell 83 ---
# [magic] !pkill -9 -f streamlit || true
# [magic] !rm -f streamlit.log

# [magic] !streamlit run app4.py \
  --server.port 8501 \
  --server.address 127.0.0.1 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  > streamlit.log 2>&1 &

# --- cell 84 ---
# --- markdown ---
# * 임시 공개 URL 생성 및 접속
#     * 아래 코드가 실행된 후 약 5초 후에 링크를 누르세요.

# --- cell 85 ---
# [magic] !cloudflared tunnel --url http://127.0.0.1:8501
