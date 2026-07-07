# D84: Track A(질문생성)+Track B(채점)를 언어별(Python/Java/JS/C·C++)로 동시 확장
#   WHY: D80이 Track A만 언어별로 재현했고(REPEATS=1, 재현성 미측정), Track B(채점)는
#        JS/TS(Study-Match-) 전용 강/약 답변 쌍(D71/D72)만 있어 언어별 비교가 아예 불가능했다.
#        사용자 요청: "언어별 Track A,B 진행한 표를 모델별로(3축: 정밀도/재현성/속도)".
#        Track A는 기존 D80 finding 8개(언어당 2개)를 REPEATS=3으로 재실행해 재현성을 채우고,
#        Track B는 언어당 finding 1개씩 골라 강/약 답변 쌍을 D71/D72와 같은 방식(실제 코드
#        확인 후 근거 있는 강한 답변 vs 근거 없는 얕은 약한 답변)으로 새로 작성했다.
#   COST: Track B 강/약 답변은 이번에 처음 작성하는 것이라(D71이 이미 인정한 한계와 동일)
#        "사람 채점 골드셋"이 아니라 "명백한 강/약 구분 능력"만 측정 가능. 언어당 finding
#        1개뿐이라 그 finding의 특성(예: JS는 테스트파일 오탐, Java는 placeholder secret)에
#        따라 강한 답변이 요구하는 통찰의 종류가 언어마다 다르다 — "언어 자체의 난이도"가
#        아니라 "그 언어에서 뽑은 특정 finding의 난이도"를 재는 것에 가깝다.
#   EXIT: 언어당 finding을 여러 개로 늘려 평균을 내면 "특정 finding 난이도" 편향이 줄어든다.
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "feedback"))
import generate_questions as gq  # noqa: E402
from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402

REPO = os.path.dirname(__file__)

MODELS = [
    "qwen/qwen3-next-80b-a3b-instruct",
    "stepfun-ai/step-3.5-flash",
    "deepseek-ai/deepseek-v4-pro",
    "meta/llama-4-maverick-17b-128e-instruct",
    "openai/gpt-oss-120b",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "mistralai/mistral-nemotron",
]
REPEATS = 3

# ---- Track A: D80과 동일한 8개 finding, 이번엔 REPEATS=3 ----
TRACK_A_SAMPLES = [
    ("python", "examples/python/whoogle-search/judgment_output.json", "architecture-diffusion:endpoint.py"),
    ("python", "examples/python/whoogle-search/judgment_output.json", "tier-b-risk:cse_client.py:secret"),
    ("java", "examples/java/base-ai-assistant/judgment_output.json", "architecture-diffusion:ChatRagProperties.java"),
    ("java", "examples/java/base-ai-assistant/judgment_output.json", "tier-b-risk:ImageSearchTool.java:secret"),
    ("javascript", "examples/javascript/SHIELD/judgment_output.json", "architecture-diffusion:utils.ts"),
    ("javascript", "examples/javascript/chargebee-node/judgment_output.json", "tier-b-risk:requestWrapper.test.ts"),
    ("c_cpp", "examples/c_cpp/loki/judgment_output.json", "architecture-diffusion:UnitTest.h"),
    ("c_cpp", "examples/c_cpp/loki/judgment_output.json", "cognition-isolation:allocatorstringstorage.h"),
]

# ---- Track B: 언어당 finding 1개, 강/약 답변 쌍 (실제 코드 확인 후 신규 작성) ----
RUBRIC_TEXT = """\
[Code Understanding] 실제 코드·파일·함수를 정확히 인용하며 설명
  1점: 코드 참조 없이 일반론 / 3점: 일부 정확 인용·개괄 설명 / 5점: 정확한 파일·함수 인용+동작 정밀 서술
[Decision Reasoning] 왜 이렇게 설계했는지 논리적으로 설명
  1점: 이유 없음/암기 / 3점: 이유 제시하나 인과 약함 / 5점: 설계 의도·인과를 논리적으로 설명
[Alternative Comparison] 다른 설계와 비교해 트레이드오프 설명
  1점: 대안 인지 없음 / 3점: 대안 언급하나 비교 얕음 / 5점: 대안 비교+트레이드오프 명확
[Counter Example Response] 극단 반례에 회피 없이 논리적으로 대응
  1점: 회피/붕괴 / 3점: 부분 대응 / 5점: 반례 견디고 논리적 방어
[Self Reflection] 반례 후 실제로 생각을 바꾸고 개선안 제시
  1점: 무반응/고집 / 3점: 일부 수용 / 5점: 지적 수용+구체 개선안 제시
"""
AXES = ["code_understanding", "decision_reasoning", "alternative_comparison",
        "counter_example_response", "self_reflection"]
GRADING_TOOL = {
    "name": "score_five_axes",
    "description": "학생 답변을 5축 루브릭(각 1~5점)으로 채점하고 축별 근거를 인용한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            **{f"{a}_score": {"type": "integer", "description": "1~5점"} for a in AXES},
            **{f"{a}_evidence": {"type": "string", "description": "답변에서 이 점수를 준 근거 구절 인용"} for a in AXES},
        },
        "required": [f"{a}_score" for a in AXES] + [f"{a}_evidence" for a in AXES],
    },
}

TRACK_B_PAIRS = [
    {
        "lang": "python", "pair_id": "py-endpoint-enum",
        "finding": "architecture-diffusion:endpoint.py (whoogle-search) — Endpoint(Enum)이 fan_in=9로 여러 라우트 핸들러가 공유하는 확산 지점",
        "question": "이 파일이 여러 컴포넌트가 공유하는 확산 지점인데, 왜 문자열 상수 대신 Enum으로 엔드포인트를 정의했는지 설명해보세요.",
        "variant": "strong",
        "answer": (
            "Endpoint(Enum)으로 만들면 라우트 이름이 코드베이스 전체에 매직 스트링으로 흩어지는 걸 "
            "막을 수 있습니다. __str__을 오버라이드해서 f-string이나 URL 조합에 그대로 꽂아 쓸 수 있게 "
            "했고, in_path() 헬퍼로 접두어 매칭까지 한곳에 모아뒀습니다. 대안으로 그냥 문자열 상수 "
            "모듈(ENDPOINTS.SEARCH = 'search')도 검토했을 텐데, Enum 쪽이 오타 시 즉시 AttributeError로 "
            "잡히는 반면 문자열 상수는 오타가 나도 그냥 새 문자열로 취급돼 런타임까지 못 잡습니다. "
            "트레이드오프는 새 엔드포인트를 추가할 때마다 이 한 파일을 반드시 거쳐야 해서 병목이 될 "
            "수 있다는 점인데, 엔드포인트 목록이 적고 자주 안 늘어나는 프로젝트 규모라 감수할 만한 "
            "비용이라고 봅니다."
        ),
    },
    {
        "lang": "python", "pair_id": "py-endpoint-enum",
        "finding": "architecture-diffusion:endpoint.py (whoogle-search) — Endpoint(Enum)이 fan_in=9로 여러 라우트 핸들러가 공유하는 확산 지점",
        "question": "이 파일이 여러 컴포넌트가 공유하는 확산 지점인데, 왜 문자열 상수 대신 Enum으로 엔드포인트를 정의했는지 설명해보세요.",
        "variant": "weak",
        "answer": "엔드포인트 목록을 한군데 모아두려고 Enum을 썼습니다. 딱히 다른 이유는 없습니다.",
    },
    {
        "lang": "java", "pair_id": "java-imagesearch-secret",
        "finding": "tier-b-risk:ImageSearchTool.java:secret (base-ai-assistant) — API_KEY = \"pexels API Key\" 시크릿 패턴 매치",
        "question": "여기 API_KEY 하드코딩 패턴이 탐지됐는데, 실제로 위험한 시크릿 유출인지, 왜 이렇게 작성했는지 설명해보세요.",
        "variant": "strong",
        "answer": (
            "코드를 보면 API_KEY = \"pexels API Key\"인데, 이건 실제 Pexels API 키가 아니라 "
            "'여기에 실제 키를 넣으라'는 의미의 placeholder 문자열입니다. 그래서 지금 시점엔 실제 "
            "시크릿 유출은 아닙니다. 다만 이렇게 코드에 상수로 박아두는 구조 자체가 문제인데, 실제 "
            "배포 전에 누군가 이 자리에 진짜 키를 그대로 커밋하면 그때는 진짜 유출이 됩니다. "
            "환경변수나 별도 설정 파일(application.yml + @Value)로 주입하는 방식이 대안이고, "
            "지금처럼 상수로 두면 애플리케이션 시작 시 이 값이 여전히 placeholder인지 검증하는 "
            "assert를 넣어서 '아직 설정 안 됐다'는 걸 조기에 알 수 있게 하는 게 최소한의 개선이라고 "
            "생각합니다."
        ),
    },
    {
        "lang": "java", "pair_id": "java-imagesearch-secret",
        "finding": "tier-b-risk:ImageSearchTool.java:secret (base-ai-assistant) — API_KEY = \"pexels API Key\" 시크릿 패턴 매치",
        "question": "여기 API_KEY 하드코딩 패턴이 탐지됐는데, 실제로 위험한 시크릿 유출인지, 왜 이렇게 작성했는지 설명해보세요.",
        "variant": "weak",
        "answer": "API 키가 코드에 그대로 있어서 위험합니다. 환경변수로 빼야 합니다.",
    },
    {
        "lang": "javascript", "pair_id": "js-requestwrapper-testfile",
        "finding": "tier-b-risk:requestWrapper.test.ts (chargebee-node) — 인증정보가 JSON.stringify되어 throw된 Error에 담김 트리거 매치",
        "question": "여기 인증정보가 JSON.stringify되어 throw된 Error에 담기는 위험 패턴이 탐지됐는데, 실제 위험인지 설명해보세요.",
        "variant": "strong",
        "answer": (
            "이 파일은 requestWrapper.test.ts로, 테스트 코드입니다. 실제로 열어보면 "
            "JSON.stringify({ customer: { id: 'cust_123' } })처럼 목(mock) Response를 만드는 테스트 "
            "픽스처들이고, throw new Error('start hook failed')는 별개의 다른 테스트 케이스에서 "
            "훅 실패를 시뮬레이션하는 코드입니다. 즉 '인증정보가 stringify돼서 throw된 에러에 담긴다'는 "
            "탐지 조건(uid/email류 키워드 + JSON.stringify + throw가 파일 안에 공존)이 실제로는 서로 "
            "인과관계 없는 두 개의 독립적인 테스트 블록에서 각각 매치된 겁니다. cust_123도 실제 고객 "
            "ID가 아니라 테스트용 더미값이고요. 그래서 이건 오탐이라고 판단합니다. 스캐너를 개선한다면 "
            "test 디렉터리를 스캔 대상에서 빼거나, 최소한 stringify와 throw가 같은 함수/블록 스코프 "
            "안에서 실제로 인과관계가 있는지(예: catch 블록 안에서 재던지기)까지 확인하도록 조건을 "
            "좁혀야 할 것 같습니다."
        ),
    },
    {
        "lang": "javascript", "pair_id": "js-requestwrapper-testfile",
        "finding": "tier-b-risk:requestWrapper.test.ts (chargebee-node) — 인증정보가 JSON.stringify되어 throw된 Error에 담김 트리거 매치",
        "question": "여기 인증정보가 JSON.stringify되어 throw된 Error에 담기는 위험 패턴이 탐지됐는데, 실제 위험인지 설명해보세요.",
        "variant": "weak",
        "answer": "인증정보를 JSON.stringify해서 에러에 담으면 위험하니 이 부분을 수정해야 합니다.",
    },
    {
        "lang": "c_cpp", "pair_id": "cpp-unittest-vendored",
        "finding": "architecture-diffusion:UnitTest.h (loki) — 여러 테스트 파일이 공유하는 fan_in=7 확산 지점",
        "question": "이 헤더가 여러 테스트 파일이 공유하는 확산 지점인데, 왜 이런 구조가 됐는지 설명해보세요.",
        "variant": "strong",
        "answer": (
            "파일 상단에 'Copyright Terje Sletteba and Pavel Vozenilek 2002'라는 저작권 표기가 "
            "있는 걸 보면, 이건 이 프로젝트가 자체적으로 설계한 파일이 아니라 외부에서 가져온 "
            "벤더링된 유닛테스트 프레임워크(Loki 라이브러리 자체의 테스트 인프라)입니다. 그래서 "
            "fan_in=7이 높게 나온 건 '이 프로젝트가 설계한 공유 상태/로직'이 아니라, 여러 테스트 "
            "소스 파일이 공통 테스트 유틸리티(SameType 같은 헬퍼)를 include해서 쓰는 자연스러운 "
            "결과입니다. 이 경우엔 '왜 이렇게 설계했는가'라는 질문 자체가 이 프로젝트 팀의 설계 "
            "판단이 아니라, 애초에 외부 테스트 프레임워크를 직접 짜지 않고 가져다 쓰기로 한 결정에 "
            "더 가깝습니다. 대안은 Boost.Test나 Catch2 같은 외부 의존성을 쓰는 것이었을 텐데, 2002년 "
            "당시 C++ 생태계에서 그런 표준화된 선택지가 지금만큼 성숙하지 않아 직접 벤더링하는 게 "
            "합리적이었을 수 있습니다."
        ),
    },
    {
        "lang": "c_cpp", "pair_id": "cpp-unittest-vendored",
        "finding": "architecture-diffusion:UnitTest.h (loki) — 여러 테스트 파일이 공유하는 fan_in=7 확산 지점",
        "question": "이 헤더가 여러 테스트 파일이 공유하는 확산 지점인데, 왜 이런 구조가 됐는지 설명해보세요.",
        "variant": "weak",
        "answer": "여러 테스트 파일이 다 이 헤더를 include해서 그런 것 같습니다.",
    },
]


def build_grading_prompt(item):
    return (
        "당신은 코드 이해도 인터뷰 답변을 채점하는 평가자입니다. 아래 5축 루브릭에 따라 "
        "학생 답변을 각 축 1~5점으로 채점하고, 각 점수의 근거가 되는 답변 속 문구를 그대로 "
        "인용하세요. 관대하게 채점하지 말고 루브릭 앵커(1/3/5점 기준)에 최대한 엄격히 맞추세요.\n\n"
        f"## 루브릭\n{RUBRIC_TEXT}\n"
        f"## Decision Point\n{item['finding']}\n\n"
        f"## 면접 질문\n{item['question']}\n\n"
        f"## 학생 답변\n{item['answer']}\n"
    )


def load_finding(path, fid, _cache={}):
    if path not in _cache:
        _cache[path] = json.load(open(os.path.join(REPO, path), encoding="utf-8"))
    for f in _cache[path]["findings"]:
        if f["id"] == fid:
            return f
    raise KeyError(fid)


pool = NvidiaKeyPool.from_env()
client = NvidiaRotatingClient(pool=pool)
print(f"key pool: {len(pool)} key(s)", flush=True)


def call_track_a(model, lang, finding, repeat_idx):
    prompt = gq.build_prompt(finding)
    tool = gq._as_openai_tool(gq.DEPTH_LADDER_TOOL)
    t0 = time.time()
    try:
        response = client.chat(
            model=model, messages=[{"role": "user", "content": prompt}], tools=[tool],
            tool_choice={"type": "function", "function": {"name": "depth_ladder_questions"}},
            max_tokens=1024, temperature=0.0,
        )
        elapsed = time.time() - t0
        gq.parse_nvidia_tool_response(response)
        return {"track": "A", "model": model, "lang": lang, "finding_id": finding["id"],
                "repeat": repeat_idx, "ok": True, "elapsed_s": round(elapsed, 2)}
    except Exception as e:
        return {"track": "A", "model": model, "lang": lang, "finding_id": finding["id"],
                "repeat": repeat_idx, "ok": False, "elapsed_s": round(time.time() - t0, 2), "error": str(e)}


def call_track_b(model, item, repeat_idx):
    prompt = build_grading_prompt(item)
    tool = gq._as_openai_tool(GRADING_TOOL)
    t0 = time.time()
    try:
        response = client.chat(
            model=model, messages=[{"role": "user", "content": prompt}], tools=[tool],
            tool_choice={"type": "function", "function": {"name": "score_five_axes"}},
            max_tokens=1024, temperature=0.0,
        )
        elapsed = time.time() - t0
        choice = response["choices"][0]["message"]
        call = next(c for c in choice["tool_calls"] if c["function"]["name"] == "score_five_axes")
        result = json.loads(call["function"]["arguments"])
        scores = {a: int(result[f"{a}_score"]) for a in AXES}
        return {"track": "B", "model": model, "lang": item["lang"], "pair_id": item["pair_id"],
                "variant": item["variant"], "repeat": repeat_idx, "ok": True,
                "elapsed_s": round(elapsed, 2), "scores": scores}
    except Exception as e:
        return {"track": "B", "model": model, "lang": item["lang"], "pair_id": item["pair_id"],
                "variant": item["variant"], "repeat": repeat_idx, "ok": False,
                "elapsed_s": round(time.time() - t0, 2), "error": str(e)}


a_findings = [(lang, load_finding(path, fid)) for lang, path, fid in TRACK_A_SAMPLES]

jobs = []
for m in MODELS:
    for lang, f in a_findings:
        for r in range(REPEATS):
            jobs.append(("A", m, lang, f, r))
    for item in TRACK_B_PAIRS:
        for r in range(REPEATS):
            jobs.append(("B", m, item, r))

print(f"total calls: {len(jobs)} (Track A {len(a_findings)}find x {len(MODELS)}model x {REPEATS}rep "
      f"+ Track B {len(TRACK_B_PAIRS)}item x {len(MODELS)}model x {REPEATS}rep)", flush=True)

results = []
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {}
    for job in jobs:
        track, m = job[0], job[1]
        if track == "A":
            _, m, lang, f, r = job
            fut = executor.submit(call_track_a, m, lang, f, r)
        else:
            _, m, item, r = job
            fut = executor.submit(call_track_b, m, item, r)
        futures[fut] = job

    done = 0
    for fut in as_completed(futures):
        results.append(fut.result())
        done += 1
        if done % 20 == 0 or done == len(jobs):
            print(f"[{done}/{len(jobs)}] done", flush=True)
            json.dump(results, open(os.path.join(REPO, "track_ab_multilang_results.json"), "w"),
                       ensure_ascii=False, indent=2)

json.dump(results, open(os.path.join(REPO, "track_ab_multilang_results.json"), "w"),
           ensure_ascii=False, indent=2)
print("DONE", flush=True)
