# D89: turn_engine.py(D87) 기준 7모델 벤치마크 -- 스펙 04시트 턴 상태기계가 실제 라이브 모델
#   호출로 구동될 때 risk-type(D88 confirmed 패턴)/cognition-isolation(D87 라이브검증 1건) 두
#   판정 경로 모두에서 정상 동작하는지 4개 언어에 걸쳐 최초로 실측한다.
#   WHY: D58~D85가 쌓은 모든 "질문생성 모델 벤치마크"는 `generate_questions.py`의 단발성
#        후보뱅크 생성기를 테스트한 것이었다(D86이 발견). `turn_engine.py`(D87)가 진짜 적응형
#        루프를 구현했고 D88이 risk-type 카테고리의 confirmed 패턴 콜드스타트를 해소했지만,
#        이 둘을 4개 언어 x 7개 모델 조합으로 실제 라이브 호출한 적은 없다(D87 스모크테스트는
#        qwen 1개 모델 x cognition-isolation C++ 1건뿐).
#   설계상 중요한 전제: `turn_engine.classify_answer()`는 answer_fn이 반환하는 텍스트에 대한
#        순수 정규식 판정이라 모델과 무관하게 결정론적이다 -- 즉 이 벤치마크가 모델별로 실제로
#        갈라지는 축은 (a) 매 레벨 `ask_question` 툴콜 스키마 준수(job 성공 여부), (b) 소요시간
#        이다. "판정 정확도"는 강한 답변=defended/약한 답변=exhausted_at_cap이 나오는지 보는
#        회귀체크 축이지 모델 비교 축이 아니다(로컬에서 `evaluate_reflection()`/
#        `classify_justification()`을 직접 호출해 API 비용 쓰기 전에 전부 사전검증 완료).
#   COST: `run_decision_point()`가 실패를 안에서 잡지 않으므로(레벨 중간에 tool_choice 미준수로
#        예외 발생 시 그 지점까지의 transcript는 버려짐) "몇 번째 레벨에서 실패했는지"는 에러
#        메시지로만 추정 가능하고, 정확한 레벨별 스키마 준수율은 이 데이터로 못 낸다 -- job
#        (finding x variant) 단위 성공/실패로 집계한다. 약한 답변은 4레벨을 전부 통과해야 성공
#        이므로 오히려 다회 연속 준수를 요구하는 더 엄격한 지표가 된다.
#   EXIT: 레벨별 정밀 스키마 준수율이 필요해지면 turn_engine.py의 run_decision_point() 안에
#        try/except를 넣어 부분 transcript를 반환하도록 바꿔야 한다(이번 범위에서는 핵심
#        오케스트레이션 무수정 원칙을 지켜 손대지 않음).
from __future__ import annotations

import json
import os
import sys
import time

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "feedback"))
sys.path.insert(0, os.path.join(REPO, "judgment"))
sys.path.insert(0, os.path.join(REPO, "pipeline"))
sys.path.insert(0, os.path.join(REPO, "benchmarks"))

from turn_engine import run_decision_point  # noqa: E402
from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402
from harness import run_concurrent, print_progress  # noqa: E402

SCRATCH_REPOS = os.environ.get(
    "TURN_ENGINE_SCRATCH_REPOS",
    "/private/tmp/claude-501/-Users-xox/4a38c284-432a-4492-a269-2e64c73551b4/scratchpad/repo_candidates",
)

MODELS = [
    "qwen/qwen3-next-80b-a3b-instruct",
    "stepfun-ai/step-3.5-flash",
    "deepseek-ai/deepseek-v4-pro",
    "meta/llama-4-maverick-17b-128e-instruct",
    "openai/gpt-oss-120b",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "mistralai/mistral-nemotron",
]

# 약한 답변: D87 스모크테스트가 라이브로 검증한 그대로("잘 모르겠습니다, 그냥 그렇게 했습니다"를
# 매 레벨 반복) -- cognition-isolation 4건에 재사용. risk-type 4건은 D85(TRACK_B_PAIRS)의 원문
# 약한 답변을 그대로 재사용(오프라인 재검증 결과 전부 0-hit=surface 확인됨, 수정 불필요).
GENERIC_WEAK = "잘 모르겠습니다, 그냥 그렇게 했습니다."

# 강한 답변은 전부 로컬에서 evaluate_reflection()/classify_justification()을 직접 호출해
# 2개 이상 confirmed 서브신호 매치(=defended) 확정 후 여기 반영한 것 -- API 호출 전 오프라인
# 검증 완료(스크래치의 validate_answers.py/validate_isolation.py 참고).
FINDINGS = [
    # ---- risk-type 4언어 (D85 TRACK_B_PAIRS 원본 + 트리거 문구 1개 자연스럽게 보정) ----
    {
        "lang": "python", "category": "architecture-diffusion", "repo_name": "whoogle-search",
        "finding": {
            "id": "architecture-diffusion:endpoint.py",
            "file": "endpoint.py",
            "finding": "Endpoint(Enum)이 fan_in=9로 여러 라우트 핸들러가 공유하는 확산 지점",
        },
        "strong_answer": (
            "Endpoint(Enum)으로 만들면 라우트 이름이 코드베이스 전체에 매직 스트링으로 흩어지는 걸 "
            "막을 수 있습니다. __str__을 오버라이드해서 f-string이나 URL 조합에 그대로 꽂아 쓸 수 있게 "
            "했고, in_path() 헬퍼로 접두어 매칭까지 한곳에 모아뒀습니다. 대안으로 그냥 문자열 상수 "
            "모듈(ENDPOINTS.SEARCH = 'search')도 검토했을 텐데, Enum 쪽이 오타 시 즉시 AttributeError로 "
            "잡히는 반면 문자열 상수는 오타가 나도 그냥 새 문자열로 취급돼 런타임까지 못 잡습니다. "
            "그래서 이 프로젝트는 문자열을 직접 타이핑하는 대신 Enum 등록을 거치는 쪽을 택한 것으로 "
            "보입니다. 트레이드오프는 새 엔드포인트를 추가할 때마다 이 한 파일을 반드시 거쳐야 해서 "
            "병목이 될 수 있다는 점인데, 엔드포인트 목록이 적고 자주 안 늘어나는 프로젝트 규모라 감수할 "
            "만한 비용이고, 새로 추가할 때도 이 파일에서 등록 여부부터 확인해야 한다고 봅니다."
        ),
        "weak_answer": "엔드포인트 목록을 한군데 모아두려고 Enum을 썼습니다. 딱히 다른 이유는 없습니다.",
    },
    {
        "lang": "java", "category": "tier-b-risk", "repo_name": "base-ai-assistant",
        "finding": {
            "id": "tier-b-risk:ImageSearchTool.java:secret",
            "file": "ImageSearchTool.java",
            "finding": "API_KEY = \"pexels API Key\" 시크릿 패턴 매치",
        },
        "strong_answer": (
            "코드를 보면 API_KEY = \"pexels API Key\"인데, 이건 실제 Pexels API 키가 아니라 "
            "'여기에 실제 키를 넣으라'는 의미의 placeholder 문자열입니다. 그래서 지금 시점엔 실제 "
            "시크릿 유출은 아닙니다. 다만 이렇게 코드에 상수로 박아두는 구조 자체가 문제인데, 실제 "
            "배포 전에 누군가 이 자리에 진짜 키를 그대로 커밋하면 그때는 진짜 유출이 됩니다. "
            "환경변수나 별도 설정 파일(application.yml + @Value)로 주입하는 방식이 대안이고, "
            "지금처럼 상수로 두면 애플리케이션 시작 시 이 값이 여전히 placeholder인지 검증하는 "
            "assert를 추가해야 '아직 설정 안 됐다'는 걸 조기에 확인해야 안전하다고 생각합니다."
        ),
        "weak_answer": "API 키가 코드에 그대로 있어서 위험합니다. 환경변수로 빼야 합니다.",
    },
    {
        "lang": "javascript", "category": "tier-b-risk", "repo_name": "chargebee-node",
        "finding": {
            "id": "tier-b-risk:requestWrapper.test.ts",
            "file": "requestWrapper.test.ts",
            "finding": "인증정보가 JSON.stringify되어 throw된 Error에 담김 트리거 매치",
        },
        "strong_answer": (
            "이 파일은 requestWrapper.test.ts로, 테스트 코드입니다. 실제로 열어보면 "
            "JSON.stringify({ customer: { id: 'cust_123' } })처럼 목(mock) Response를 만드는 테스트 "
            "픽스처들이고, throw new Error('start hook failed')는 별개의 다른 테스트 케이스에서 "
            "훅 실패를 시뮬레이션하는 코드입니다. 즉 '인증정보가 stringify돼서 throw된 에러에 담긴다'는 "
            "탐지 조건(uid/email류 키워드 + JSON.stringify + throw가 파일 안에 공존)이 실제로는 서로 "
            "인과관계 없는 두 개의 독립적인 테스트 블록에서 각각 매치된 겁니다. cust_123도 실제 고객 "
            "ID가 아니라 테스트용 더미값이고요. 그래서 이건 오탐이라고 판단합니다. 지금 보니 이 오탐은 "
            "스캐너가 test 디렉터리를 스캔 대상에서 빼지 않은 게 근본 원인이라, 그 규칙부터 개선해야 "
            "할 것 같습니다."
        ),
        "weak_answer": "인증정보를 JSON.stringify해서 에러에 담으면 위험하니 이 부분을 수정해야 합니다.",
    },
    {
        "lang": "c_cpp", "category": "architecture-diffusion", "repo_name": "loki",
        "finding": {
            "id": "architecture-diffusion:UnitTest.h",
            "file": "UnitTest.h",
            "finding": "여러 테스트 파일이 공유하는 fan_in=7 확산 지점",
        },
        "strong_answer": (
            "파일 상단에 'Copyright Terje Sletteba and Pavel Vozenilek 2002'라는 저작권 표기가 "
            "있는 걸 보면, 이건 이 프로젝트가 자체적으로 설계한 파일이 아니라 외부에서 가져온 "
            "벤더링된 유닛테스트 프레임워크(Loki 라이브러리 자체의 테스트 인프라)입니다. 그래서 "
            "fan_in=7이 높게 나온 건 '이 프로젝트가 설계한 공유 상태/로직'이 아니라, 여러 테스트 "
            "소스 파일이 공통 테스트 유틸리티(SameType 같은 헬퍼)를 include해서 쓰는 자연스러운 "
            "결과입니다. 지금 보니 이런 벤더링된 코드는 관용 패턴 목록에 등록해서 앞으로는 이렇게 "
            "다시 확인해야 하는 대상에서 빼는 게 좋겠습니다."
        ),
        "weak_answer": "여러 테스트 파일이 다 이 헤더를 include해서 그런 것 같습니다.",
    },
    # ---- cognition-isolation 4언어 (신규 저작, 실제 클론 코드 확인 후 작성) ----
    {
        "lang": "python", "category": "cognition-isolation", "repo_name": "Elevator",
        "finding": {
            "id": "cognition-isolation:patterns.py",
            "file": "patterns.py",
            "finding": "허브 모듈(constants.py)로 가는 edge 없음. fan_in=6만 보면 정상으로 보임",
        },
        "strong_answer": (
            "이 파일(patterns.py)은 enum 팩토리 함수, Singleton 메타클래스, destructurate 헬퍼처럼 "
            "프로젝트 도메인과 무관한 범용 파이썬 패턴만 모아둔 유틸리티 모듈입니다. Elevator(ZeroMQ "
            "기반 key-value 스토어)의 실제 도메인 로직—DB 백엔드 선택, 커맨드 라우팅 같은 것—은 "
            "constants.py 쪽에 있을 텐데, 이 유틸 함수들은 그런 도메인 상수가 전혀 필요 없습니다. "
            "오히려 이런 범용 헬퍼를 여기로 분리해서 다른 모듈들이 각자 위임해서 가져다 쓰는 구조이기 "
            "때문에, constants.py 같은 허브로 들어오는 edge가 없는 게 자연스럽습니다. fan_in=6은 이 "
            "파일을 이용하는 다른 파일이 6개 있다는 뜻이지, 이 파일이 뭔가와 연결이 끊겼다는 신호가 "
            "아니라고 봅니다."
        ),
        "weak_answer": GENERIC_WEAK,
    },
    {
        "lang": "java", "category": "cognition-isolation", "repo_name": "LibraryManageSystem",
        "finding": {
            "id": "cognition-isolation:Book.java",
            "file": "Book.java",
            "finding": "허브 모듈(Model.java)로 가는 edge 없음. fan_in=5만 보면 정상으로 보임",
        },
        "strong_answer": (
            "Book.java는 book 도메인의 순수 데이터 홀더(POJO)입니다 — 필드 6개와 생성자만 있고 실제 "
            "DB 접근 로직이 전혀 없습니다. Model.java 같은 DB 연결 허브는 실제 쿼리를 실행하는 "
            "BookDao/BookDaoImpl 같은 클래스에서나 필요하지, 이 값 객체 자체는 DB 커넥션이 딱히 "
            "필요 없는 계층입니다. 데이터와 영속성 로직을 분리(관심사 분리)해서 DB 접근은 별도 DAO "
            "클래스에 위임하는 구조로 보이고, 그래서 fan_in=5(이 클래스를 쓰는 파일 5개)와 무관하게 "
            "Model.java로 가는 edge가 없는 게 오히려 정상적인 계층 분리입니다."
        ),
        "weak_answer": GENERIC_WEAK,
    },
    {
        "lang": "javascript", "category": "cognition-isolation", "repo_name": "FarmAssist",
        "finding": {
            "id": "cognition-isolation:Input.jsx",
            "file": "Input.jsx",
            "finding": "허브 모듈(AppIcon.jsx)로 가는 edge 없음. fan_in=3만 보면 정상으로 보임",
        },
        "strong_answer": (
            "Input.jsx는 순수 프레젠테이션 UI 프리미티브입니다 — checkbox/radio/text 세 variant를 "
            "렌더링하는 forwardRef 컴포넌트일 뿐, 아이콘을 표시하는 로직이 코드 어디에도 없습니다. "
            "AppIcon.jsx는 아이콘을 렌더링하는 별도 컴포넌트인데, 이 Input 컴포넌트는 label 텍스트와 "
            "에러 메시지만 보여주면 되고 아이콘은 딱히 필요 없는 컴포넌트라 import할 이유가 없습니다. "
            "아이콘이 필요한 조합(예: 아이콘 붙은 인풋)은 이 컴포넌트를 감싸는 상위 컴포넌트에 "
            "위임하는 구조로 설계된 것 같고, 그래서 fan_in=3과 별개로 AppIcon.jsx로 가는 edge가 없는 "
            "게 자연스럽습니다."
        ),
        "weak_answer": GENERIC_WEAK,
    },
    {
        "lang": "c_cpp", "category": "cognition-isolation", "repo_name": "EasyQtSql",
        "finding": {
            "id": "cognition-isolation:EasyQtSql_DeleteQuery.h",
            "file": "EasyQtSql_DeleteQuery.h",
            "finding": "허브 모듈(EasyQtSql.h)로 가는 edge 없음. fan_in=2만 보면 정상으로 보임",
        },
        "strong_answer": (
            "EasyQtSql_DeleteQuery.h는 DELETE 쿼리 실행만 담당하는 리프(leaf) 구현 헤더입니다. "
            "필요한 건 QtSql과 EasyQtSql_NonQueryResult.h(반환 타입)뿐이고, EasyQtSql.h는 반대로 이 "
            "헤더를 포함하는 상위 aggregator 헤더로 보입니다 — 즉 이 파일 입장에서는 EasyQtSql.h를 "
            "다시 include할 필요 없습니다. 여러 Query 클래스(DeleteQuery/InsertQuery 등)를 "
            "EasyQtSql.h 하나가 모아서 위임하는 구조라, 개별 리프 헤더가 그 aggregator로 역참조하는 "
            "edge가 없는 게 헤더 설계상 자연스럽습니다. fan_in=2는 이 헤더를 include하는 다른 파일이 "
            "2개 있다는 뜻이지, 고립됐다는 신호는 아니라고 봅니다."
        ),
        "weak_answer": GENERIC_WEAK,
    },
]

CLIENT = None


def call_one(job):
    model, entry, variant = job
    repo_root = os.path.join(SCRATCH_REPOS, entry["repo_name"])
    answer_text = entry["strong_answer"] if variant == "strong" else entry["weak_answer"]

    def answer_fn(question, level):
        return answer_text

    label = f"{entry['lang']}:{entry['finding']['id']}:{variant}"
    t0 = time.time()
    try:
        result = run_decision_point(entry["finding"], repo_root, answer_fn, CLIENT, model)
        expected = "defended" if variant == "strong" else "exhausted_at_cap"
        return {
            "model": model, "label": label, "ok": True,
            "lang": entry["lang"], "category": entry["category"], "variant": variant,
            "verdict": result["verdict"], "matches_expected": result["verdict"] == expected,
            "turns": result["turns"], "elapsed_s": result["elapsed_s"],
        }
    except Exception as e:
        return {
            "model": model, "label": label, "ok": False,
            "lang": entry["lang"], "category": entry["category"], "variant": variant,
            "error": str(e), "elapsed_s": round(time.time() - t0, 1),
        }


def summarize(all_results: list) -> dict:
    summary = {}
    for model in MODELS:
        rows = [r for r in all_results if r["model"] == model]
        ok_rows = [r for r in rows if r["ok"]]
        total = len(rows)
        ok_count = len(ok_rows)
        matched = sum(1 for r in ok_rows if r.get("matches_expected"))
        summary[model] = {
            "job_success_rate": round(ok_count / total, 3) if total else 0.0,
            "verdict_matches_expected_rate": round(matched / ok_count, 3) if ok_count else None,
            "mean_elapsed_s": round(sum(r["elapsed_s"] for r in ok_rows) / ok_count, 1) if ok_count else None,
            "mean_turns": round(sum(r["turns"] for r in ok_rows) / ok_count, 2) if ok_count else None,
            "n_ok": ok_count, "n_total": total,
        }
    return summary


def main():
    global CLIENT
    pool = NvidiaKeyPool.from_env()
    CLIENT = NvidiaRotatingClient(pool=pool)

    out_dir = os.path.dirname(os.path.abspath(__file__))
    raw_path = os.path.join(out_dir, "turn_engine_multilang_results.json")

    results = []
    for model in MODELS:
        jobs = [(model, entry, variant) for entry in FINDINGS for variant in ("strong", "weak")]
        print(f"=== {model}: {len(jobs)} calls ===", flush=True)
        results.extend(run_concurrent(jobs, call_one, max_workers=6, progress=print_progress))
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        time.sleep(3)

    summary = summarize(results)
    with open(os.path.join(out_dir, "turn_engine_multilang_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== 요약 ===")
    for model, s in summary.items():
        print(f"{model}: job_success={s['job_success_rate']*100:.0f}% "
              f"verdict_match={(s['verdict_matches_expected_rate'] or 0)*100:.0f}% "
              f"mean_elapsed={s['mean_elapsed_s']}s mean_turns={s['mean_turns']} "
              f"({s['n_ok']}/{s['n_total']})")


if __name__ == "__main__":
    main()
