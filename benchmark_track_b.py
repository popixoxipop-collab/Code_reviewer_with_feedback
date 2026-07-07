# D70 참고(benchmark_track_a.py) — 이 파일은 Track B(채점/LLM-as-judge) 벤치마크.
#
# D71: 채점 벤치마크는 실제 학생 답변이 아니라 "의도적으로 품질을 통제한 강/약 답변 쌍"으로
#   변별력(정밀도)을 측정한다.
#   WHY: 이 저장소엔 원래 채점용 LLM 자체가 없었다(judgment/*.py는 100% 규칙기반, D59/D60
#        핸드오프 참고) — 즉 채점 프롬프트를 이번에 처음 만드는 것이라 비교할 실측 사람 채점
#        골드셋이 없다. LLM-as-judge를 검증하는 표준 방법(known-answer test)대로, 정답을
#        아는 강/약 쌍을 넣어 "이 judge가 더 나은 답변에 실제로 더 높은 점수를 주는가"를 재는
#        것이 사람 골드셋 없이도 가능한 가장 정직한 1차 검증이다.
#   COST: 이 정밀도는 "사람 채점과의 상관도"가 아니라 "명백한 강/약을 구분하는 최소 능력"만
#         잰다 — 훨씬 미묘한 실제 학생 답변(중간 수준)에서도 변별하는지는 검증 못함.
#   EXIT: 실제 학생 답변 10~20건 + 사람 채점이 쌓이면 TEST_ANSWERS를 그걸로 교체하고
#         정밀도 지표를 "사람 점수와의 상관계수"로 바꿀 것.
#
# D72: Pair1(Bookshelf.jsx)의 STRONG 답변은 TEAM_POC_SUMMARY.md에 기록된 실제 Codex 독립
#   생성 답변을 그대로 재사용(사람이 쓴 것도 아니고 이 벤치마크용으로 새로 지어낸 것도 아님).
#   Pair2(App.tsx)는 그런 실제 기록이 없어 강/약 둘 다 이 벤치마크를 위해 새로 작성한 합성
#   답변이다 — 아래 각 답변에 출처를 명시한다.
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "feedback"))
from generate_questions import _as_openai_tool  # noqa: E402
from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402

REPO = os.path.dirname(__file__)

# D73: deepseek-ai/deepseek-v4-pro를 숏리스트에서 제외하고 mistralai/mistral-nemotron으로 교체
#   WHY: Track A 실행 중 deepseek-v4-pro가 12/12 호출 전부 즉시(0.5s) HTTP 429 — 3초 간격을
#        둔 재시도(3회)에서도 동일하게 즉시 실패. 이건 볼륨발 rate limit이 아니라 이 API 키로는
#        이 모델 자체에 접근 권한이 없다는 신호(다른 5개 모델은 같은 키로 정상 작동).
#   COST: deepseek-v4-pro는 이전 code-review 벤치마크(nvidia-build)에서 재현성 최고점(0.9)을
#         받은 모델이라 이번 채점 벤치마크에서 가장 궁금했던 후보 중 하나인데 비교 불가.
#   EXIT: 이 키에 deepseek-v4-pro 접근 권한이 생기면(다른 티어 키로 교체 등) Track A/B 둘 다
#         재실행해 다시 포함.
MODELS = [
    "qwen/qwen3-next-80b-a3b-instruct",
    "stepfun-ai/step-3.5-flash",
    "mistralai/mistral-nemotron",
    "meta/llama-4-maverick-17b-128e-instruct",
    "openai/gpt-oss-120b",
    "mistralai/mistral-large-3-675b-instruct-2512",
]

REPEATS = 3

# 기획명세서 05_AI방법론 시트의 5축 루브릭(1/3/5점 앵커) 원문 그대로
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

AXES = [
    "code_understanding", "decision_reasoning", "alternative_comparison",
    "counter_example_response", "self_reflection",
]

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

# ---- 테스트 답변: 강/약 쌍 2세트 ----
TEST_ANSWERS = [
    {
        "pair_id": "bookshelf-xss",
        "finding": "tier-b-risk:Bookshelf.jsx:dangerous-html (dangerouslySetInnerHTML로 네이버 도서 API 응답을 그대로 렌더링)",
        "question": "이 코드에 잠재적 위험 패턴이 있는데, 이 부분이 어떤 위험을 가질 수 있는지, 그리고 왜 이렇게 구현했는지 설명해보세요.",
        "variant": "strong",
        "source": "REAL — Codex(codex:codex-rescue) 독립 생성, TEAM_POC_SUMMARY.md 91-109행 원문 그대로",
        "answer": (
            "이 부분은 dangerouslySetInnerHTML을 써서 XSS 위험이 있는 게 맞는 것 같습니다. "
            "item.title이랑 item.author가 네이버 도서 API에서 오는 값인데, 응답에 <b> 태그 "
            "같은 게 섞여 있어서 그냥 렌더링하면 태그가 텍스트로 보이는 문제가 있었고, 그걸 "
            "해결하려고 급하게 dangerouslySetInnerHTML로 처리했던 것 같습니다. 외부 API 응답이라도 "
            "신뢰할 수 있는 소스라고 안일하게 생각했던 것 같고, 스크립트 삽입 가능성 같은 건 그 "
            "당시엔 크게 고려하지 못했습니다. 지금 보니 정규식으로 필요한 태그만 걸러내거나 "
            "DOMPurify 같은 걸로 sanitize하고 렌더링했어야 할 것 같습니다."
        ),
    },
    {
        "pair_id": "bookshelf-xss",
        "finding": "tier-b-risk:Bookshelf.jsx:dangerous-html (dangerouslySetInnerHTML로 네이버 도서 API 응답을 그대로 렌더링)",
        "question": "이 코드에 잠재적 위험 패턴이 있는데, 이 부분이 어떤 위험을 가질 수 있는지, 그리고 왜 이렇게 구현했는지 설명해보세요.",
        "variant": "weak",
        "source": "SYNTHETIC — 이 벤치마크용으로 의도적으로 얕게 작성(실제 학생 답변 아님)",
        "answer": "그냥 API에서 오는 데이터를 화면에 보여주려고 dangerouslySetInnerHTML을 썼습니다. 별다른 이유는 없고 그냥 편해서 이렇게 했습니다.",
    },
    {
        "pair_id": "app-diffusion",
        "finding": "architecture-diffusion:App.tsx (여러 컴포넌트가 공유하는 상태/컨텍스트 확산 지점)",
        "question": "이 파일이 여러 컴포넌트에서 공유되는 확산 지점인데, 왜 이런 구조를 선택했는지 설명해보세요.",
        "variant": "strong",
        "source": "SYNTHETIC — 이 벤치마크용으로 작성(App.tsx에 대한 실제 기록 답변이 없어 강/약 둘 다 신규 작성)",
        "answer": (
            "여러 하위 컴포넌트가 로그인 상태와 현재 대회 목록을 동시에 필요로 해서 Context API로 "
            "App.tsx에 최상위 상태를 뒀습니다. Redux나 Zustand 같은 상태관리 라이브러리도 고려했는데, "
            "이 프로젝트는 전역 상태가 로그인 유저 정보랑 대회 목록 두 개뿐이라 별도 라이브러리를 "
            "추가하면 오히려 보일러플레이트가 늘어난다고 판단했습니다. 대신 prop drilling으로 "
            "내려주는 방식도 검토했는데, 5단계 넘게 내려가는 컴포넌트가 있어서 중간 컴포넌트들이 "
            "쓰지도 않는 props를 계속 전달만 해주는 게 유지보수에 더 나쁘다고 봤습니다. 트레이드오프는 "
            "있습니다 — Context 값이 바뀌면 구독하는 모든 컴포넌트가 리렌더링되는데, 지금 규모에선 "
            "성능 문제가 안 보였지만 컴포넌트가 훨씬 늘어나면 useMemo나 Context 분리로 최적화가 "
            "필요할 거라고 생각합니다."
        ),
    },
    {
        "pair_id": "app-diffusion",
        "finding": "architecture-diffusion:App.tsx (여러 컴포넌트가 공유하는 상태/컨텍스트 확산 지점)",
        "question": "이 파일이 여러 컴포넌트에서 공유되는 확산 지점인데, 왜 이런 구조를 선택했는지 설명해보세요.",
        "variant": "weak",
        "source": "SYNTHETIC — 이 벤치마크용으로 의도적으로 얕게 작성(실제 학생 답변 아님)",
        "answer": "여러 컴포넌트가 다 같이 써야 해서 그냥 위쪽(App.tsx)에 뒀습니다. 다른 방법은 딱히 생각 안 해봤습니다.",
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


pool = NvidiaKeyPool.from_env()
client = NvidiaRotatingClient(pool=pool)
print(f"key pool: {len(pool)} key(s)", flush=True)
print(f"Track B: {len(MODELS)} models x {len(TEST_ANSWERS)} answers x {REPEATS} repeats = "
      f"{len(MODELS) * len(TEST_ANSWERS) * REPEATS} calls", flush=True)


def grade_one(model, item, repeat_idx):
    prompt = build_grading_prompt(item)
    tool = _as_openai_tool(GRADING_TOOL)
    t0 = time.time()
    try:
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": "score_five_axes"}},
            max_tokens=1024,
            temperature=0.0,
        )
        elapsed = time.time() - t0
        choice = response["choices"][0]["message"]
        call = next(c for c in choice["tool_calls"] if c["function"]["name"] == "score_five_axes")
        result = json.loads(call["function"]["arguments"])
        scores = {a: int(result[f"{a}_score"]) for a in AXES}
        return {
            "model": model, "pair_id": item["pair_id"], "variant": item["variant"],
            "repeat": repeat_idx, "ok": True, "elapsed_s": round(elapsed, 2), "scores": scores,
        }
    except Exception as e:
        return {
            "model": model, "pair_id": item["pair_id"], "variant": item["variant"],
            "repeat": repeat_idx, "ok": False, "elapsed_s": round(time.time() - t0, 2), "error": str(e),
        }


jobs = [(m, item, r) for m in MODELS for item in TEST_ANSWERS for r in range(REPEATS)]
results = []
with ThreadPoolExecutor(max_workers=12) as executor:
    futures = {executor.submit(grade_one, m, item, r): (m, item["pair_id"], item["variant"], r) for m, item, r in jobs}
    done = 0
    for fut in as_completed(futures):
        r = fut.result()
        results.append(r)
        done += 1
        tag = "OK " if r["ok"] else "ERR"
        print(f"[{done}/{len(jobs)}] {tag} {r['model']:45s} {r['pair_id']:15s} {r['variant']:6s} rep{r['repeat']} {r['elapsed_s']:>6.1f}s", flush=True)

out_path = os.path.join(REPO, "track_b_results.json")
json.dump(results, open(out_path, "w"), ensure_ascii=False, indent=2)
print(f"saved -> {out_path}", flush=True)

# ---- 집계: 정밀도(변별력) / 재현성(분산) / 속도 ----
import statistics

by_model = defaultdict(list)
for r in results:
    if r["ok"]:
        by_model[r["model"]].append(r)

summary = {}
for model, rs in by_model.items():
    # 정밀도: strong 평균총점 > weak 평균총점 인 pair 비율(axis 평균으로 계산)
    by_pair_variant = defaultdict(list)
    for r in rs:
        total = sum(r["scores"].values())
        by_pair_variant[(r["pair_id"], r["variant"])].append(total)

    pair_ids = sorted(set(pid for pid, _ in by_pair_variant))
    correct = 0
    for pid in pair_ids:
        strong_scores = by_pair_variant.get((pid, "strong"), [])
        weak_scores = by_pair_variant.get((pid, "weak"), [])
        if strong_scores and weak_scores:
            if statistics.mean(strong_scores) > statistics.mean(weak_scores):
                correct += 1
    precision = correct / len(pair_ids) if pair_ids else 0.0

    # 재현성: 동일 (pair,variant) 반복 채점의 총점 표준편차 평균(낮을수록 좋음) -> 1/(1+std)로 변환
    stds = []
    for (pid, variant), totals in by_pair_variant.items():
        if len(totals) > 1:
            stds.append(statistics.pstdev(totals))
    avg_std = statistics.mean(stds) if stds else 0.0
    reproducibility = 1 / (1 + avg_std)

    avg_latency = statistics.mean(r["elapsed_s"] for r in rs)

    summary[model] = {
        "precision_discrimination_rate": round(precision, 3),
        "reproducibility_score": round(reproducibility, 3),
        "avg_score_std": round(avg_std, 3),
        "avg_latency_s": round(avg_latency, 2),
        "n_calls_ok": len(rs),
    }

out_summary = os.path.join(REPO, "track_b_summary.json")
json.dump(summary, open(out_summary, "w"), ensure_ascii=False, indent=2)
print(f"saved -> {out_summary}", flush=True)
print(json.dumps(summary, ensure_ascii=False, indent=2))
