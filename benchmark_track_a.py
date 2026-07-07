# D70: Track A/B 벤치마크 — 질문생성(A) vs 채점(B) 두 축을 분리 측정
#   WHY: 기획명세서(00_개요·결정사항)가 "qwen3-next-80b-a3b-instruct 단일, 질문생성·채점을
#        동일 모델·상이 프롬프트로"라고 이미 모델을 lock했다. 그래서 이 벤치마크의 목적은
#        "어느 모델을 고를까"(SURVEY_RESULTS.md가 87개 모델로 이미 답함)가 아니라 "이미 고른
#        모델(+대안 후보)이 질문생성과 채점, 서로 다른 두 역할 각각에서 합격선을 넘는가"이다.
#        두 역할은 성공 기준이 다르다(질문생성=창의성/스키마 준수, 채점=일관성/변별력) — 하나의
#        벤치마크로 대체 불가.
#   COST: 87개 전수조사가 아니라 6개 모델 숏리스트(SURVEY_RESULTS.md 상위권 6개)로 축소 —
#         전수 재확인은 아님. Track B는 실제 학생 데이터가 아니라 합성 테스트 답변(품질을
#         의도적으로 통제한 강/약 쌍)으로 변별력을 측정 — 실제 학생 답변 분포에 대한 일반화는
#         아직 미검증.
#   EXIT: 숏리스트를 넓히려면 MODELS 리스트에 chat_candidates.json에서 더 추가. 실제 학생
#         답변이 쌓이면 benchmark_track_b.py의 TEST_ANSWERS를 실측 데이터로 교체.
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

REPEATS = 3  # 재현성 측정을 위한 반복 횟수 (동일 finding, 동일 온도 0.0)

data = json.load(open(os.path.join(REPO, "examples/study_match/judgment_output.json")))
findings = data["findings"]  # 4개, 4개 카테고리 전부 포함(cognition-isolation/architecture-diffusion/tier-b-risk/repeated-pattern)

pool = NvidiaKeyPool.from_env()
client = NvidiaRotatingClient(pool=pool)
print(f"key pool: {len(pool)} key(s), theoretical max {pool.theoretical_max_rpm} RPM/model", flush=True)
print(f"Track A: {len(MODELS)} models x {len(findings)} findings x {REPEATS} repeats = "
      f"{len(MODELS) * len(findings) * REPEATS} calls", flush=True)


def call_one(model, finding, repeat_idx):
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
            "model": model, "finding_id": finding["id"], "repeat": repeat_idx,
            "ok": True, "elapsed_s": round(elapsed, 2), "questions": questions,
        }
    except Exception as e:
        return {
            "model": model, "finding_id": finding["id"], "repeat": repeat_idx,
            "ok": False, "elapsed_s": round(time.time() - t0, 2), "error": str(e),
        }


jobs = [(m, f, r) for m in MODELS for f in findings for r in range(REPEATS)]
results = []
with ThreadPoolExecutor(max_workers=12) as executor:
    futures = {executor.submit(call_one, m, f, r): (m, f["id"], r) for m, f, r in jobs}
    done = 0
    for fut in as_completed(futures):
        r = fut.result()
        results.append(r)
        done += 1
        tag = "OK " if r["ok"] else "ERR"
        print(f"[{done}/{len(jobs)}] {tag} {r['model']:45s} {r['finding_id']:35s} rep{r['repeat']} {r['elapsed_s']:>6.1f}s", flush=True)

out_path = os.path.join(REPO, "track_a_results.json")
json.dump(results, open(out_path, "w"), ensure_ascii=False, indent=2)
print(f"saved -> {out_path}", flush=True)

# 요약 집계
by_model = defaultdict(lambda: {"calls": 0, "ok": 0, "elapsed": [], "by_finding": defaultdict(list)})
for r in results:
    m = by_model[r["model"]]
    m["calls"] += 1
    if r["ok"]:
        m["ok"] += 1
        m["elapsed"].append(r["elapsed_s"])
    m["by_finding"][r["finding_id"]].append(r["ok"])

summary = {}
for model, agg in by_model.items():
    precision = agg["ok"] / agg["calls"] if agg["calls"] else 0.0
    # 재현성: finding별 3회 전부 성공한 비율(부분 성공은 재현성 결함으로 간주)
    fully_reliable = sum(1 for oks in agg["by_finding"].values() if all(oks)) / len(agg["by_finding"])
    avg_latency = sum(agg["elapsed"]) / len(agg["elapsed"]) if agg["elapsed"] else None
    summary[model] = {
        "precision_compliance_rate": round(precision, 3),
        "reproducibility_full_reliability_rate": round(fully_reliable, 3),
        "avg_latency_s": round(avg_latency, 2) if avg_latency else None,
    }

out_summary = os.path.join(REPO, "track_a_summary.json")
json.dump(summary, open(out_summary, "w"), ensure_ascii=False, indent=2)
print(f"saved -> {out_summary}", flush=True)
print(json.dumps(summary, ensure_ascii=False, indent=2))
