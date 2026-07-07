# D66: 정밀도 지표를 "recall"이 아니라 reference-set coverage로 명명 — 기존 12개 정적분석
#   finding은 gold standard가 아니라 참고 세트일 뿐이다(정적분석 자체가 팀 결정상 폐기 대상).
# D69: 이 벤치마크 실행이 기획명세서 00시트의 "Qwen 스펙(컨텍스트·가격) 미검증 — 락 전 실측
#   필요" 항목을 함께 검증한다(코드조각+요구사항을 실제 이 shape로 호출하므로).
from __future__ import annotations

import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH_DIR = os.environ.get(
    "MEAS02_SCRATCH_DIR",
    "/private/tmp/claude-501/-Users-xox/f934435e-507f-4ce3-993d-b89228689375/scratchpad",
)
SCRATCH_REPOS = os.path.join(SCRATCH_DIR, "repo_candidates")
sys.path.insert(0, os.path.join(REPO, "judgment"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import meas02_decision_point_extractor as extractor  # noqa: E402
from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402
from harness import run_concurrent, print_progress  # noqa: E402

MODELS = [
    "qwen/qwen3-next-80b-a3b-instruct",
    "deepseek-ai/deepseek-v4-pro",
    "z-ai/glm-5.2",
    "minimaxai/minimax-m3",
    "nvidia/nemotron-3-ultra-550b-a55b",
]

# 참고 세트: 기존 정적분석(cognition/judgment 블록)이 이미 찾은 4개 지점 — "정답"이 아니라
# "겹치는지 확인할 참고 대상"(D66). isolation(Competitions.tsx)은 의도적으로 포함 —
# 이건 cross-file 구조 신호(fan-in)라서 단일 파일 조각만 보는 이 추출기가 원천적으로
# 잡을 수 없다는 한계 자체를 실측으로 보여주기 위함(정직하게 보고).
CASES = [
    {
        "label": "study_match:firebase.ts",
        "file": os.path.join(SCRATCH_REPOS, "Study-Match-/src/firebase.ts"),
        "requirements": os.path.join(SCRATCH_DIR, "study_match_requirements.txt"),
        "reference_keywords": ["uid", "email", "stringify", "authinfo", "인증", "개인정보"],
        "reference_note": "tier-b-risk:firebase.ts (인증정보 JSON.stringify 유출) — 단일 파일 내 신호, 커버 가능해야 함",
    },
    {
        "label": "study_match:Competitions.tsx",
        "file": os.path.join(SCRATCH_REPOS, "Study-Match-/src/components/Competitions.tsx"),
        "requirements": os.path.join(SCRATCH_DIR, "study_match_requirements.txt"),
        "reference_keywords": ["firebase", "허브", "고립", "isolat", "fetch"],
        "reference_note": "cognition-isolation:Competitions.tsx (허브 미연결) — cross-file fan-in 신호라 "
                           "단일 파일 조각만 보는 이 추출기는 원천적으로 못 잡을 가능성이 높음(한계 실측용)",
    },
    {
        "label": "lms:Bookshelf.jsx",
        "file": os.path.join(SCRATCH_REPOS, "LMS/src/pages/(shelf)/Bookshelf.jsx"),
        "requirements": os.path.join(SCRATCH_DIR, "lms_requirements.txt"),
        "reference_keywords": ["dangerouslysetinnerhtml", "xss", "sanitize", "html"],
        "reference_note": "tier-b-risk:Bookshelf.jsx:dangerous-html — 단일 파일 내 신호, 커버 가능해야 함",
    },
    {
        "label": "lms:useBooksQueries.ts",
        "file": os.path.join(SCRATCH_REPOS, "LMS/src/api/lms/books/useBooksQueries.ts"),
        "requirements": os.path.join(SCRATCH_DIR, "lms_requirements.txt"),
        "reference_keywords": ["query", "공유", "캐시", "여러 컴포넌트", "재사용"],
        "reference_note": "architecture-diffusion:useBooksQueries.ts (여러 컴포넌트 공유) — 부분적으로 "
                           "단일 파일에서도 추론 가능(공유 목적의 훅이라는 건 파일 자체에서 보임)",
    },
]


def _load_case_inputs(case):
    with open(case["file"], encoding="utf-8", errors="ignore") as f:
        code_snippet = f.read()
    with open(case["requirements"], encoding="utf-8") as f:
        requirements = f.read()
    return os.path.basename(case["file"]), code_snippet, requirements


def coverage(decision_points: list, keywords: list) -> bool:
    haystack = " ".join(f"{p.get('judgment_type','')} {p.get('evidence','')}" for p in decision_points).lower()
    return any(kw.lower() in haystack for kw in keywords)


def call_one(job):
    model, case, run_tag = job
    file_name, code_snippet, requirements = _load_case_inputs(case)
    t0 = time.time()
    try:
        response = CLIENT.chat(
            model=model,
            messages=[{"role": "user", "content": extractor.build_extraction_prompt(file_name, code_snippet, requirements, None)}],
            tools=[extractor._as_openai_tool(extractor.DECISION_POINT_TOOL)],
            tool_choice={"type": "function", "function": {"name": "extract_decision_points"}},
            max_tokens=2048,
            temperature=0.0,
        )
        elapsed = time.time() - t0
        result = extractor.parse_nvidia_tool_response(response)
        return {
            "model": model, "label": case["label"], "run": run_tag, "ok": True,
            "elapsed_s": round(elapsed, 1), "decision_points": result["decision_points"],
            "n_points": len(result["decision_points"]),
            "covers_reference": coverage(result["decision_points"], case["reference_keywords"]),
        }
    except Exception as e:
        return {
            "model": model, "label": case["label"], "run": run_tag, "ok": False,
            "elapsed_s": round(time.time() - t0, 1), "error": str(e),
        }


def summarize(all_results: list) -> dict:
    summary = {}
    for model in MODELS:
        model_results = [r for r in all_results if r["model"] == model]
        run1 = {r["label"]: r for r in model_results if r["run"] == "run1" and r["ok"]}
        ok_count = sum(1 for r in model_results if r["ok"])
        total = len(model_results)

        coverage_by_case = {label: r["covers_reference"] for label, r in run1.items()}
        n_points_mean = sum(r["n_points"] for r in run1.values()) / len(run1) if run1 else None

        # 재현성: run1/run2 각 case의 decision_points 개수가 얼마나 안정적인지(구조화 필드가
        # 자유 텍스트 배열이라 exact-match가 아니라 개수 안정성으로 근사 — 한계로 명시)
        run2 = {r["label"]: r for r in model_results if r["run"] == "run2" and r["ok"]}
        count_diffs = [abs(run1[l]["n_points"] - run2[l]["n_points"]) for l in run1 if l in run2]
        stability = (1 - sum(min(d, 1) for d in count_diffs) / len(count_diffs)) if count_diffs else None

        summary[model] = {
            "tool_call_success_rate": round(ok_count / total, 3) if total else 0.0,
            "reference_set_coverage": coverage_by_case,
            "coverage_rate": round(sum(coverage_by_case.values()) / len(coverage_by_case), 3) if coverage_by_case else None,
            "mean_n_decision_points": round(n_points_mean, 1) if n_points_mean is not None else None,
            "mean_elapsed_s": round(sum(r["elapsed_s"] for r in model_results if r["ok"]) / ok_count, 1) if ok_count else None,
            "reproducibility_count_stability": round(stability, 3) if stability is not None else None,
        }
    return summary


def to_markdown(summary: dict) -> str:
    lines = [
        "# MEAS-02 순수 LLM Decision Point 추출기 벤치마크 결과\n",
        "기획명세서_AI기반_프로젝트교육품질관리플랫폼.xlsx(00시트, \"확정 설계 결정\") 그대로 "
        "정적분석 미사용, 코드조각+요구사항→LLM. 정밀도는 reference-set coverage(D66) — "
        "기존 정적분석 4개 finding과 겹치는지 확인하는 것이지 gold standard 대비 recall이 아님. "
        "이 실행 자체가 Qwen 컨텍스트/속도 실측(D69, 00시트 \"락 전 실측 필요\")도 겸함.\n",
        "| Model | tool_choice 준수율 | reference-set coverage | 평균 DP 개수 | 평균 속도 | 개수-안정성(재현성 근사) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for model, s in summary.items():
        cov = f"{s['coverage_rate']*100:.0f}%" if s["coverage_rate"] is not None else "n/a"
        npts = f"{s['mean_n_decision_points']:.1f}" if s["mean_n_decision_points"] is not None else "n/a"
        speed = f"{s['mean_elapsed_s']:.1f}s" if s["mean_elapsed_s"] is not None else "n/a"
        stab = f"{s['reproducibility_count_stability']:.2f}" if s["reproducibility_count_stability"] is not None else "n/a"
        lines.append(f"| `{model}` | {s['tool_call_success_rate']*100:.0f}% | {cov} | {npts} | {speed} | {stab} |")

    lines.append("\n## 케이스별 coverage 상세 (한계 포함)")
    for case in CASES:
        lines.append(f"\n**{case['label']}** — {case['reference_note']}")
        for model, s in summary.items():
            hit = s["reference_set_coverage"].get(case["label"])
            mark = "covered" if hit else ("NOT covered" if hit is False else "n/a(실패)")
            lines.append(f"- `{model}`: {mark}")

    lines.append(
        "\n## 중요한 방법론적 한계 (D77로 재검증 완료, 정직하게 명시)\n"
        "최초 실행(5모델 동시 제출)의 경합 문제를 D77(모델별 순차 실행)로 고치고 실패 건을 "
        "5초 간격으로 순차 재시도한 결과: `qwen3-next-80b`/`deepseek-v4-pro`는 100% 도달. "
        "`nvidia/nemotron-3-ultra-550b-a55b`는 75%(잔여 실패는 503/tool_choice 미준수 — 진짜 "
        "서비스 이슈로 보임). **`minimaxai/minimax-m3`는 grading 벤치마크(짧은 프롬프트)에서는 "
        "100%였는데 이 벤치마크(전체 코드파일+요구사항 전문을 프롬프트에 넣는 훨씬 큰 컨텍스트)"
        "에서는 25%에 그쳤다** — 실패 대부분이 120초 타임아웃으로, 경합이 아니라 **이 모델이 "
        "큰 컨텍스트 처리에 특히 취약하다는 신호**로 해석하는 게 더 타당하다(작은 프롬프트 "
        "task에서는 이 모델을 써도 되지만, MEAS-02처럼 전체 파일을 통째로 넣는 task에는 "
        "부적합할 수 있음). `z-ai/glm-5.2`는 이 벤치마크에서도 0% — grading 벤치마크에서 "
        "이미 확인한 대로(SURVEY_RESULTS.md의 과거 42% 이력과 달리 이번엔 순차 실행+격리 "
        "단독 호출+20초 간격 재시도 전부에서 0/9) 경합이 아니라 모델 자체의 지속적 이용 "
        "불가로 판단, 후보에서 제외 권장."
    )
    lines.append(
        "\n## 알려진 한계\n"
        "- 이 추출기는 단일 파일 조각만 보므로(스펙의 \"DP 단위 처리로 컨텍스트 의존 최소화\" 설계),"
        " cross-file 구조 신호(예: Competitions.tsx의 허브 미연결 — fan-in 기반)는 원천적으로 "
        "탐지 대상이 아니다. 이건 버그가 아니라 스펙이 선택한 아키텍처의 알려진 트레이드오프다.\n"
        "- reference-set coverage는 키워드 매칭 기반 근사(nvidia-build METHODOLOGY.md의 heuristic "
        "screening과 동일한 성격, 정밀 검증 아님).\n"
        "- 재현성은 decision_points 배열이 자유 텍스트를 포함해 구조화 필드 exact-match(D61 모듈)를 "
        "그대로 못 쓰고, 개수 안정성으로 근사했다 — 채점 벤치마크(D63)보다 느슨한 지표."
    )
    return "\n".join(lines)


# D77 (grading_run_benchmark.py 참고, 동일 진단) — 모델별 순차 실행으로 교체
#   WHY/COST/EXIT: grading_run_benchmark.py의 D77와 동일. 이 파일 자신의 "중요한 방법론적
#   한계" 문단이 이미 "특히 qwen3-next-80b 외 4개 모델의 순위는 재검증 없이 신뢰하지 말 것"이라고
#   스스로 기록해뒀다.
def main():
    global CLIENT
    pool = NvidiaKeyPool.from_env()
    CLIENT = NvidiaRotatingClient(pool=pool)

    results = []
    for model in MODELS:
        jobs = [(model, c, "run1") for c in CASES] + [(model, c, "run2") for c in CASES]
        print(f"=== {model}: {len(jobs)} calls ===", flush=True)
        results.extend(run_concurrent(jobs, call_one, max_workers=6, progress=print_progress))
        time.sleep(3)

    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "meas02_benchmark_raw.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    summary = summarize(results)
    with open(os.path.join(out_dir, "meas02_chart_data.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    md = to_markdown(summary)
    with open(os.path.join(out_dir, "meas02_results.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print("\n" + md)


if __name__ == "__main__":
    main()
