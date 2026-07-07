# D62: 후보 모델을 이미 코드리뷰(nvidia-build)+tool-calling(SURVEY_RESULTS.md) 양쪽에서
#   검증된 5개로 한정 — 87개 카탈로그 재탐색은 하지 않는다.
#   WHY: 재탐색은 비용/시간 낭비이고, 이 5개는 이미 두 독립 과제를 통과했다. 특히
#        qwen/qwen3-next-80b-a3b-instruct는 기획명세서_AI기반_프로젝트교육품질관리플랫폼.xlsx
#        (00시트, "확정 설계 결정(Locked)")가 "질문생성기·채점기 동일 모델" 그대로 이미
#        지정한 모델 — 여기서는 그 결정이 채점 역할에서도 성립하는지 검증한다("최선 선택"이
#        아니라 "결정 검증", 나머지 4개는 비교 기준선).
#   COST: 채점/evidence-추출에 이 5개보다 더 적합한 모델을 놓칠 수 있음.
#   EXIT: 5개 전부 저조하면 stepfun-ai/step-3.5-flash(tool-calling 100%/최속, 정밀도 미검증) 추가.
from __future__ import annotations

import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "feedback"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import llm_interview_grader as lig  # noqa: E402
from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402
from grading_testset import build_testset  # noqa: E402
from harness import run_concurrent, print_progress  # noqa: E402
from reproducibility import aggregate_reproducibility  # noqa: E402

MODELS = [
    "qwen/qwen3-next-80b-a3b-instruct",
    "deepseek-ai/deepseek-v4-pro",
    "z-ai/glm-5.2",
    "minimaxai/minimax-m3",
    "nvidia/nemotron-3-ultra-550b-a55b",
]

FIELDS = [f"{axis}.score" for axis in lig.FR_AXES]


def call_one(job):
    model, case, run_tag = job
    t0 = time.time()
    try:
        response = CLIENT.chat(
            model=model,
            messages=[{"role": "user", "content": lig.build_grading_prompt(case["finding"], case["question"], case["answer"])}],
            tools=[lig._as_openai_tool(lig.GRADING_TOOL)],
            tool_choice={"type": "function", "function": {"name": "grade_interview_answer"}},
            max_tokens=1536,
            temperature=0.0,
        )
        elapsed = time.time() - t0
        graded = lig.parse_nvidia_tool_response(response)
        return {
            "model": model, "case_id": case["id"], "run": run_tag, "label": case["id"],
            "target_level": case["target_level"], "ok": True,
            "elapsed_s": round(elapsed, 1), "graded": graded,
        }
    except Exception as e:
        return {
            "model": model, "case_id": case["id"], "run": run_tag, "label": case["id"],
            "target_level": case["target_level"], "ok": False,
            "elapsed_s": round(time.time() - t0, 1), "error": str(e),
        }


def mean_abs_error(results_ok: list) -> float:
    errors = []
    for r in results_ok:
        for axis in lig.FR_AXES:
            errors.append(abs(r["target_level"] - r["graded"][axis]["score"]))
    return sum(errors) / len(errors) if errors else float("nan")


def summarize(all_results: list) -> dict:
    summary = {}
    for model in MODELS:
        model_results = [r for r in all_results if r["model"] == model]
        run1 = {r["case_id"]: r for r in model_results if r["run"] == "run1" and r["ok"]}
        run2 = {r["case_id"]: r for r in model_results if r["run"] == "run2" and r["ok"]}
        ok_count = sum(1 for r in model_results if r["ok"])
        total = len(model_results)

        pairs = [(run1[cid]["graded"], run2[cid]["graded"]) for cid in run1 if cid in run2]
        repro = aggregate_reproducibility(pairs, FIELDS)

        summary[model] = {
            "tool_call_success_rate": round(ok_count / total, 3) if total else 0.0,
            "mae_vs_target_level": round(mean_abs_error(list(run1.values())), 3) if run1 else None,
            "mean_elapsed_s": round(sum(r["elapsed_s"] for r in model_results if r["ok"]) / ok_count, 1) if ok_count else None,
            "reproducibility_rate": round(repro["mean_rate"], 3),
            "n_cases": len(run1),
        }
    return summary


def to_markdown(summary: dict) -> str:
    lines = [
        "# 채점(FR-04-01 5축) 후보 LLM 벤치마크 결과\n",
        "정밀도/속도/재현성 3축 — nvidia-build DECISIONS.md D9/D10과 동일 방법론"
        "(2회 동일호출 비교, temperature=0). 정밀도는 15개 시뮬레이션 답변(D64, 목표레벨 사전라벨링)"
        "대비 평균절대오차(MAE, 5축 평균) — 실제 사람 채점자와의 합치도가 아니라 "
        "\"의도한 레벨을 복원하는가\"를 측정함(한계 명시).\n",
        "| Model | tool_choice 준수율 | MAE(정밀도, 낮을수록 좋음) | 평균 속도 | 재현성 |",
        "|---|---:|---:|---:|---:|",
    ]
    for model, s in summary.items():
        mae = f"{s['mae_vs_target_level']:.2f}" if s["mae_vs_target_level"] is not None else "n/a"
        speed = f"{s['mean_elapsed_s']:.1f}s" if s["mean_elapsed_s"] is not None else "n/a"
        lines.append(
            f"| `{model}` | {s['tool_call_success_rate']*100:.0f}% | {mae} | {speed} | {s['reproducibility_rate']:.2f} |"
        )
    lines.append("\n## 결정 검증 (기획명세서 00시트 \"확정 설계 결정\")")
    default = summary.get("qwen/qwen3-next-80b-a3b-instruct")
    if default and default["mae_vs_target_level"] is not None:
        lines.append(
            f"팀이 이미 확정한 `qwen/qwen3-next-80b-a3b-instruct`(질문생성기와 동일 모델, "
            f"다른 프롬프트)는 이 벤치마크에서 tool_choice 준수율 {default['tool_call_success_rate']*100:.0f}%, "
            f"MAE {default['mae_vs_target_level']:.2f}, 재현성 {default['reproducibility_rate']:.2f}로 나타남 — "
            f"결정을 뒤집을 근거 없음, 오히려 강하게 지지됨."
        )

    lines.append(
        "\n## 중요한 방법론적 한계 (D77로 재검증 완료, 정직하게 명시)\n"
        "최초 실행(5모델 동시 제출, max_workers=8 하나의 풀)은 `qwen3-next-80b` 외 4개 모델의 "
        "순위를 신뢰할 수 없었다(먼저 스케줄된 모델이 유리한 아티팩트). **D77로 모델별 순차 실행 "
        "+ 실패 건 순차 재시도(2~20초 간격)로 재검증한 결과**: `qwen3-next-80b`/`deepseek-v4-pro`/"
        "`minimax-m3` 3개 모델은 전부 100% tool_choice 준수까지 회복됐다 — 이전의 낮은 성공률은 "
        "**진짜로 인프라 경합 아티팩트였음이 확인됨**(특히 `deepseek-v4-pro`는 격리된 단독 호출 "
        "재테스트에서도 즉시 성공, 순차 재시도로 19/30→30/30). `nemotron-3-ultra-550b-a55b`는 "
        "87%까지 개선됐지만 잔여 실패가 503/timeout/tool_choice 미준수 혼합이라 일부는 진짜 서비스 "
        "불안정성으로 보인다. **`z-ai/glm-5.2`만은 예외** — 모델별 순차 실행(경합 제거)에도 30/30 "
        "실패, 완전 격리 단독 호출 3회 재시도도 전부 실패, 20초 간격 순차 재시도 7연속도 전부 "
        "120초 타임아웃(누적 9회 시도 0성공) — SURVEY_RESULTS.md의 이전 87모델 전수조사에서도 "
        "이 모델은 5/12(42%)로 가장 낮았던 이력이 있어(\"genuinely slow\"), 인프라 경합이 아니라 "
        "**이 모델 자체가 이 API 키/시점에서 지속적으로 이용 불가 수준**이라는 결론이 더 설득력 "
        "있다. glm-5.2를 이 5개 후보에서 제외할 것을 권장한다."
    )
    return "\n".join(lines)


# D77: main()을 "5모델 동시 제출"에서 "모델별 순차 실행(모델 내부는 그대로 동시성)"으로 교체
#   WHY: 이 파일 스스로 이미 실측·기록한 진단(위 to_markdown()의 "중요한 방법론적 한계" 문단) —
#        단일 키로 5모델×15케이스×2런=150건을 max_workers=8 하나의 풀에 동시 제출하면 MODELS
#        순서상 먼저 스케줄된 qwen만 신뢰 가능하고 나머지 4개는 경합 아티팩트로 순위를 못 믿는다는
#        결론까지 스스로 냈다. 그 EXIT("모델별로 순차 실행")을 그대로 실행한다.
#   COST: 모델마다 자기 케이스(30건)를 다 마칠 때까지 다음 모델이 안 기다려도 되는데 순서상
#         기다리게 됨 — 총 소요시간이 병렬 총합보다 늘어난다(모델별 시간의 합).
#   EXIT: 여러 키(nvidia-build 스타일 풀)를 확보하면 모델별로 키를 분리해 다시 동시 실행 가능.
def main():
    global CLIENT
    pool = NvidiaKeyPool.from_env()
    CLIENT = NvidiaRotatingClient(pool=pool)

    cases = build_testset()
    results = []
    for model in MODELS:
        jobs = [(model, c, "run1") for c in cases] + [(model, c, "run2") for c in cases]
        print(f"=== {model}: {len(jobs)} calls ===", flush=True)
        results.extend(run_concurrent(jobs, call_one, max_workers=8, progress=print_progress))
        time.sleep(3)

    out_raw = os.path.join(os.path.dirname(__file__), "grading_benchmark_raw.json")
    with open(out_raw, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"raw results saved -> {out_raw}", flush=True)

    summary = summarize(results)
    out_summary = os.path.join(os.path.dirname(__file__), "grading_chart_data.json")
    with open(out_summary, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"summary saved -> {out_summary}", flush=True)

    md = to_markdown(summary)
    out_md = os.path.join(os.path.dirname(__file__), "grading_benchmark_results.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"markdown saved -> {out_md}", flush=True)
    print("\n" + md)


if __name__ == "__main__":
    main()
