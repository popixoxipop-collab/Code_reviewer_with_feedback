# D77: Track A(질문생성) 벤치마크를 언어별로 재현 -- D74~D76에서 확보한 다국어 corpus 사용
#   WHY: benchmark_track_a.py(D70)/SURVEY_RESULTS.md(D58)는 전부 Study-Match-/LMS(JS/TS)만
#        썼다. "JS/TS에서 이긴 모델이 Python/Java/C-C++에서도 이기는가"는 한 번도 검증된 적
#        없음(2026-07-07 사용자 질문으로 확인된 갭). D74~D76으로 만든 4개 언어 corpus(99건,
#        lang 필드 정확)가 있으니 그걸로 채운다.
#   COST: REPEATS=1(속도/1차 스윕용) -- benchmark_track_a.py의 REPEATS=3(재현성 측정)보다
#        약함. 언어당 finding 2개(tier-b-risk 1개 + architecture-diffusion 1개, c_cpp만
#        tier-b-risk가 아예 없어서 대신 cognition-isolation 사용, D75/D76이 이미 문서화한
#        한계)뿐이라 언어 내 분산은 못 봄 -- "언어별 대략적 방향성"만 잡는 정찰 성격.
#   EXIT: 흥미로운 언어별 격차가 보이면 해당 언어만 REPEATS=3으로 늘려 재현성까지 확인.
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
]
REPEATS = 1

# (lang, judgment_output.json 경로, finding id) -- D74~D76 corpus에서 언어당 2개씩 수동 선정
SAMPLES = [
    ("python", "examples/python/whoogle-search/judgment_output.json", "architecture-diffusion:endpoint.py"),
    ("python", "examples/python/whoogle-search/judgment_output.json", "tier-b-risk:cse_client.py:secret"),
    ("java", "examples/java/base-ai-assistant/judgment_output.json", "architecture-diffusion:ChatRagProperties.java"),
    ("java", "examples/java/base-ai-assistant/judgment_output.json", "tier-b-risk:ImageSearchTool.java:secret"),
    ("javascript", "examples/javascript/SHIELD/judgment_output.json", "architecture-diffusion:utils.ts"),
    ("javascript", "examples/javascript/chargebee-node/judgment_output.json", "tier-b-risk:requestWrapper.test.ts"),
    ("c_cpp", "examples/c_cpp/loki/judgment_output.json", "architecture-diffusion:UnitTest.h"),
    ("c_cpp", "examples/c_cpp/loki/judgment_output.json", "cognition-isolation:allocatorstringstorage.h"),
]


def load_finding(path, finding_id):
    data = json.load(open(os.path.join(REPO, path), encoding="utf-8"))
    for f in data["findings"]:
        if f["id"] == finding_id:
            return f
    raise KeyError(f"{finding_id} not found in {path}")


findings = [(lang, load_finding(path, fid)) for lang, path, fid in SAMPLES]

pool = NvidiaKeyPool.from_env()
client = NvidiaRotatingClient(pool=pool)
print(f"key pool: {len(pool)} key(s), theoretical max {pool.theoretical_max_rpm} RPM/model", flush=True)
print(f"Track A multilang: {len(MODELS)} models x {len(findings)} findings x {REPEATS} repeats = "
      f"{len(MODELS) * len(findings) * REPEATS} calls", flush=True)


def call_one(model, lang, finding, repeat_idx):
    prompt = gq.build_prompt(finding)
    tool = gq._as_openai_tool(gq.DEPTH_LADDER_TOOL)
    t0 = time.time()
    try:
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": "depth_ladder_questions"}},
            max_tokens=1024,
            temperature=0.0,
        )
        elapsed = time.time() - t0
        questions = gq.parse_nvidia_tool_response(response)
        return {
            "model": model, "lang": lang, "finding_id": finding["id"], "repeat": repeat_idx,
            "ok": True, "elapsed_s": round(elapsed, 2), "questions": questions,
        }
    except Exception as e:
        return {
            "model": model, "lang": lang, "finding_id": finding["id"], "repeat": repeat_idx,
            "ok": False, "elapsed_s": round(time.time() - t0, 2), "error": str(e),
        }


jobs = [(m, lang, f, r) for m in MODELS for lang, f in findings for r in range(REPEATS)]
results = []
with ThreadPoolExecutor(max_workers=12) as executor:
    futures = {executor.submit(call_one, m, lang, f, r): (m, lang, f["id"], r) for m, lang, f, r in jobs}
    done = 0
    for fut in as_completed(futures):
        results.append(fut.result())
        done += 1
        print(f"[{done}/{len(jobs)}] done", flush=True)

with open(os.path.join(REPO, "track_a_multilang_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# 언어 x 모델 매트릭스: 정밀도(스키마 완전준수율) + 평균 속도
agg = defaultdict(lambda: {"ok": 0, "total": 0, "elapsed": []})
for r in results:
    key = (r["lang"], r["model"])
    agg[key]["total"] += 1
    agg[key]["elapsed"].append(r["elapsed_s"])
    if r["ok"]:
        agg[key]["ok"] += 1

print("\n=== 언어 x 모델 정밀도(스키마 준수율) / 평균속도 ===")
langs = sorted(set(lang for lang, _ in agg))
for lang in langs:
    print(f"\n[{lang}]")
    for model in MODELS:
        e = agg[(lang, model)]
        precision = e["ok"] / e["total"] if e["total"] else 0
        avg_s = sum(e["elapsed"]) / len(e["elapsed"]) if e["elapsed"] else 0
        print(f"  {model:<45s} precision={precision:.0%}  avg={avg_s:.1f}s  (n={e['total']})")
