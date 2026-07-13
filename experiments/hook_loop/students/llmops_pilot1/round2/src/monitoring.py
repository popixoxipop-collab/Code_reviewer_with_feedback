# v2.0 신규 파일 -- 미션③ [필수] 모니터링 시스템 구축(LangSmith 기반)
#
# 설계 요약:
#   LANGSMITH_TRACING / LANGSMITH_PROJECT / LANGSMITH_ENDPOINT 환경변수를 설정해두면,
#   그 뒤로 실행되는 모든 LangChain/LangGraph 호출(analyzer_node/critic_node의
#   llm.invoke, agent_graph.app.invoke 전체)이 별도의 코드 수정 없이 자동으로
#   LangSmith 프로젝트에 trace로 기록된다. 즉 이 파일이 하는 일은 "무엇을 trace할지"가
#   아니라 "trace를 켜고 어디로 보낼지"를 한 곳에서 설정하는 것 -- nodes.py/agent_graph.py
#   쪽 로직은 건드릴 필요가 없다.
#
#   이 프로젝트에는 실제 LANGSMITH_API_KEY가 없다 (과제 요구사항: 환경변수 설정 코드와
#   trace 로직 "구조"만 그럴듯하면 되고 실행 테스트는 필요 없음). 그래서 아래 함수들은
#   키가 없어도 절대 앱을 죽이지 않도록 전부 best-effort로 작성했다 -- 실제 키가 채워지는
#   순간 코드 변경 없이 그대로 동작하는 것이 목표.
import os

DEFAULT_PROJECT = "product-review-agent-v2"
DEFAULT_ENDPOINT = "https://api.smith.langchain.com"


def setup_langsmith_tracing(
    project: str = DEFAULT_PROJECT,
    endpoint: str = DEFAULT_ENDPOINT,
    enabled: bool = True,
) -> bool:
    """LangSmith trace 환경변수를 설정한다 (미션③ 필수 요구사항 그대로).

    main.py / app.py 양쪽 진입점에서 각각 한 번씩만 호출하면 된다 (환경변수는
    프로세스 전역이라 두 곳에 같은 설정 코드를 복붙할 이유가 없다 -- Step1 피드백과
    동일한 원칙).

    Args:
        project: LangSmith 프로젝트 이름. 실행을 구분해서 보고 싶으면 바꿔서 호출.
        endpoint: LangSmith API 엔드포인트.
        enabled: False로 주면 tracing을 명시적으로 끈다 (예: 로컬 디버깅 시 노이즈 제거).

    Returns:
        환경변수 설정이 "시도"되었는지 여부 (LANGSMITH_API_KEY 유효 여부와는 무관 --
        키 유무는 별도로 확인하고 경고만 출력한다).
    """
    if not enabled:
        os.environ["LANGSMITH_TRACING"] = "false"
        return False

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = project
    os.environ["LANGSMITH_ENDPOINT"] = endpoint

    # LANGSMITH_API_KEY는 config.load_api_keys()가 api_key.txt에서 먼저 읽어와야 한다.
    # 이 함수는 그 값을 새로 만들지 않고, 없을 때 조용히 넘어가는 대신 한 번 경고만 남긴다
    # -- tracing 실패가 LLM 응답 자체를 막아서는 안 되므로 (best-effort side-channel).
    if not os.environ.get("LANGSMITH_API_KEY"):
        print(
            f"[monitoring] LANGSMITH_API_KEY가 없습니다. trace 환경변수는 설정되었지만 "
            f"실제 LangSmith 대시보드로는 전송되지 않을 수 있습니다. "
            f"(프로젝트명: {project})"
        )
    return True


def trace_run_config(run_name: str, **metadata) -> dict:
    """agent_app.invoke(state, config=...) 에 넘길 RunnableConfig 조각을 만든다.

    LangGraph의 compile() 결과물은 LangChain Runnable이므로 invoke(input, config=...)의
    config에 run_name/tags/metadata를 실어 보내면, LangSmith UI에서 이번 실행을
    다른 실행과 구분해서 볼 수 있다 (예: "이 실행은 Streamlit에서 온 것", "재시도 몇 회").

    metadata에 넘긴 키워드 인자 중 값이 None인 것은 제외한다 (LangSmith 쪽에 굳이
    빈 값을 보내지 않기 위함).
    """
    return {
        "run_name": run_name,
        "tags": ["product-review-agent", "v2"],
        "metadata": {k: v for k, v in metadata.items() if v is not None},
    }


def get_recent_trace_urls(project: str = DEFAULT_PROJECT, limit: int = 5):
    """[선택/best-effort] 최근 LangSmith run들을 조회해본다 (미션③ "관측 결과 확인" 보조용).

    langsmith 패키지 유무, API 키 유무, SDK 버전에 따라 실패할 수 있는 모든 경로를
    폭넓게 방어한다 -- 이 함수가 실패해도 에이전트 실행 자체에는 영향이 없어야 한다.
    이 프로젝트에는 실제 키가 없으므로 정상적으로는 항상 빈 리스트를 반환하고,
    대신 대시보드에서 직접 확인할 수 있는 안내만 출력한다.
    """
    try:
        from langsmith import Client  # 선택적 의존성: langsmith 미설치 시 ImportError

        client = Client()
        runs = client.list_runs(project_name=project, limit=limit)
        return [getattr(r, "url", None) for r in runs if getattr(r, "url", None)]
    except Exception as e:  # noqa: BLE001 -- best-effort 관측 기능이라 광범위하게 방어
        print(f"[monitoring] LangSmith run 조회 생략 (키 미설정 또는 SDK 예외): {e}")
        print(f"[monitoring] 대시보드에서 프로젝트 '{project}'로 직접 확인: https://smith.langchain.com/")
        return []
