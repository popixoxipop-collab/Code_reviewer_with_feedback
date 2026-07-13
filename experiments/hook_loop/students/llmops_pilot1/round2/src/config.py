# v2.0 신규 파일
#
# Step1 리뷰 피드백: load_api_keys()가 main.py / app.py 두 곳에 서로 살짝 다른 버전으로
# 복붙되어 있었다 (파일마다 독립 실행 가능하게 만들려던 것인데, "import를 쓰지 않은
# 이유"를 설명하라는 지적을 받음). state.py/nodes.py/agent_graph.py는 이미 import로
# 공유하고 있었으므로 같은 원칙을 여기에도 적용해 데이터 경로 + API 키 로딩을
# 이 파일 하나로 합치고 나머지 파일은 전부 여기서 import 해서 쓴다.
#
# 반대로 이 파일 자체는 "독립 실행"이 필요 없다 -- config.py는 항상 다른 모듈에
# 의존성으로 import되는 용도이지 단독으로 실행할 이유가 없기 때문에 __main__ 블록도 없다.
import os

# Colab 환경(원본 노트북)의 기본 경로를 그대로 유지한다 -- 기존 동작을 바꾸지 않기 위함.
# 로컬/CI 등 Colab이 아닌 환경에서 돌릴 때만 PROJ_DATA_DIR 환경변수로 덮어쓰면 된다.
DATA_DIR = os.environ.get("PROJ_DATA_DIR", "/content/drive/MyDrive/proj2_agent/")
DB_PATH = os.path.join(DATA_DIR, "reviews.db")
API_KEY_FILE = os.path.join(DATA_DIR, "api_key.txt")


def load_api_keys(filepath: str = None) -> None:
    """`KEY=VALUE` 줄 형식의 파일(api_key.txt)을 읽어 os.environ에 주입한다.

    OPENAI_API_KEY뿐 아니라 미션③에서 쓰는 LANGSMITH_API_KEY도 같은 파일에
    한 줄 추가하는 것만으로 함께 로드된다. 예:
        OPENAI_API_KEY=sk-...
        LANGSMITH_API_KEY=lsv2_...

    파일이 없으면 조용히 넘어간다 -- 이미 환경변수로 키가 주입되는 배포 환경
    (서버 secrets, CI 등)에서는 api_key.txt 자체가 없는 게 정상 상태이므로
    에러로 취급하지 않는다 (원본 app.py의 예외 처리 방식을 그대로 계승).
    """
    if filepath is None:
        filepath = API_KEY_FILE
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
