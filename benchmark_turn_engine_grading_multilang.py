# D93: Track A(질문생성) + Track B(채점) + turn_engine.py 적응형 벤치마크를 하나로 통합
#   WHY: D89~D92는 turn_engine.py를 4개 언어 x 7모델로 실행했지만 job 성공률/속도(Track A에
#        해당하는 축)만 쟀다. Track B(FR-04-01 5축 LLM-as-judge 채점, `llm_interview_grader.py`)
#        는 turn_engine과 한 번도 결합된 적이 없고, 애초에 4개 언어로 재실행된 적도 없다(D80이
#        재실행한 건 Track A뿐). 사용자 요청: "지금 Track A x 4언어 / Track B x 원본만 /
#        turn_engine x 4언어(별개 지표)가 따로 노는(OR) 상태다 -- turn_engine의 적응형
#        멀티턴 흐름 안에서 Track A와 Track B를 둘 다, 4개 언어 전부에 대해 측정하라(AND)."
#   설계: run_decision_point()가 만드는 실제 multi-turn transcript를
#        turn_engine._transcript_text()(기존 헬퍼, 무수정)로 포맷해 그대로
#        llm_interview_grader.grade_answer()에 넘긴다 -- 기획명세서 확정 결정("질문생성기·
#        채점기 동일 모델")대로 turn_engine을 실행한 그 모델이 자기 transcript를 채점한다.
#   COST: 답변 스크립트를 2종(strong/weak, D89 재사용)에서 3종으로 확장 -- strong/weak는
#        각각 자기_수정 축을 의미있게 채점할 transcript를 못 만든다(strong=L1 즉시 방어라
#        reflection에 도달 안 함, weak=4턴 내내 안 변함). "improving"(L1~L3 제네릭 약한 답변
#        재사용 + reflection에서만 진짜 자기수정 답변)을 신규 추가해 실제로 reflection
#        단계까지 도달하는 transcript를 만든다. 8 findings x 3 scripts x 7 models = 168
#        turn_engine job(~504 실제 호출) + 성공 job당 채점 1회(~168) = 총 ~670콜, D89(280)의
#        2.4배 -- 하니스는 D89로 이미 검증됐고 답변 전부 오프라인 사전검증 완료라 전체 규모로
#        바로 진행(사용자 확인).
#   EXIT: REPEATS=1이라 재현성 미측정(D89와 동일 이유, 1차 정찰). 여러 키 확보 후 REPEATS 늘려
#        재실행 가능 -- FINDINGS/스크립트 구조는 무수정 재사용 가능.
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "feedback"))
sys.path.insert(0, os.path.join(REPO, "judgment"))
sys.path.insert(0, os.path.join(REPO, "pipeline"))
sys.path.insert(0, os.path.join(REPO, "benchmarks"))

from turn_engine import run_decision_point, _transcript_text  # noqa: E402
import llm_interview_grader as lig  # noqa: E402
from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402
from harness import run_concurrent, print_progress  # noqa: E402

# D89 스크립트를 파일로 로드해 FINDINGS(8건, strong/weak 텍스트 포함)를 재사용 -- 무수정,
# 이 파일에 improving_answer 필드만 덧붙인다.
_spec = importlib.util.spec_from_file_location("bte_d89", os.path.join(REPO, "benchmark_turn_engine_multilang.py"))
_bte_d89 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bte_d89)

SCRATCH_REPOS = _bte_d89.SCRATCH_REPOS
MODELS = _bte_d89.MODELS
GENERIC_WEAK = _bte_d89.GENERIC_WEAK

# improving_answer: L1~L3는 GENERIC_WEAK 재사용(오프라인 검증됨, surface 확정) + reflection
# 단계에서만 이 텍스트로 교체.
#   risk-type(tier-b-risk/architecture-diffusion): reflection은 evaluate_reflection()이
#     self_error_recognition(필수)+optional>=2를 요구 -- D51 confirmed 트리거 문구
#     (너무\s*신뢰했/안일하게\s*생각 + 그래서/지금\s*보니/추가해야|확인해야|개선해야)로 신규 저작,
#     로컬 evaluate_reflection() 직접 호출로 전부 오프라인 검증 완료(reflection_present=True).
#   cognition-isolation: classify_answer()가 level과 무관하게 항상 classify_justification()을
#     쓰므로(레벨 분기 없음), D89의 strong 텍스트(이미 role_separation/perf_optimization/
#     domain_irrelevance 중 2개 이상 매치 검증됨)를 reflection 단계 답변으로 그대로 재사용 --
#     새 텍스트 저작 불필요.
IMPROVING_ANSWERS = {
    "architecture-diffusion:endpoint.py": (
        "지금 보니 제가 이 부분을 너무 안일하게 생각했습니다. Enum에 없는 엔드포인트가 "
        "요청되면 그냥 조용히 넘어가는 줄 알았는데, 실제로는 예외 없이 처리가 안 되는 "
        "경우가 있을 수 있어서, 그래서 등록되지 않은 값이 들어왔을 때 명시적으로 검증하는 "
        "로직을 추가해야 한다고 생각합니다."
    ),
    "tier-b-risk:ImageSearchTool.java:secret": (
        "지금 보니 제가 이 placeholder를 너무 안일하게 생각했습니다. 실제 배포 파이프라인에 "
        "이 값이 검증 없이 그대로 나갈 수 있다는 걸 놓쳤어요. 그래서 애플리케이션 시작 시 "
        "이 값이 여전히 placeholder인지 검사하는 로직을 추가해야 한다고 생각합니다."
    ),
    "tier-b-risk:requestWrapper.test.ts": (
        "지금 보니 제가 이 코드를 너무 신뢰했습니다 — 테스트 픽스처인지 제대로 확인도 안 "
        "하고 그냥 위험하다고 판단했어요. 그래서 스캐너가 test 디렉터리부터 확인해야 하는 "
        "규칙으로 개선해야 한다고 생각합니다."
    ),
    "architecture-diffusion:UnitTest.h": (
        "지금 보니 제가 이 헤더를 너무 안일하게 생각했습니다 — 벤더링된 외부 코드인지 "
        "확인도 안 하고 그냥 이 프로젝트 설계라고 판단했어요. 그래서 관용 패턴 목록에 "
        "등록해서 앞으로는 이런 경우 다시 확인해야 한다고 생각합니다."
    ),
    # cognition-isolation 4건: D89 strong 텍스트를 그대로 재사용(레벨 무관 분류, 신규 저작 없음)
    "cognition-isolation:patterns.py": None,
    "cognition-isolation:Book.java": None,
    "cognition-isolation:Input.jsx": None,
    "cognition-isolation:EasyQtSql_DeleteQuery.h": None,
}

FINDINGS = []
for entry in _bte_d89.FINDINGS:
    fid = entry["finding"]["id"]
    improving = IMPROVING_ANSWERS[fid]
    if improving is None:
        improving = entry["strong_answer"]  # cognition-isolation: strong 재사용
    new_entry = dict(entry)
    new_entry["improving_answer"] = improving
    FINDINGS.append(new_entry)

CLIENT = None


def _make_answer_fn(answer_text_at_reflection, weak_text):
    def answer_fn(question, level):
        return answer_text_at_reflection if level == "reflection" else weak_text
    return answer_fn


def call_one(job):
    model, entry, variant = job
    repo_root = os.path.join(SCRATCH_REPOS, entry["repo_name"])
    label = f"{entry['lang']}:{entry['finding']['id']}:{variant}"

    if variant == "strong":
        answer_fn = lambda q, lvl: entry["strong_answer"]  # noqa: E731
    elif variant == "weak":
        answer_fn = lambda q, lvl: entry["weak_answer"]  # noqa: E731
    else:  # improving
        answer_fn = _make_answer_fn(entry["improving_answer"], entry["weak_answer"])

    t0 = time.time()
    try:
        result = run_decision_point(entry["finding"], repo_root, answer_fn, CLIENT, model)
    except Exception as e:
        return {
            "model": model, "label": label, "ok": False, "graded": False,
            "lang": entry["lang"], "category": entry["category"], "variant": variant,
            "error": str(e), "elapsed_s": round(time.time() - t0, 1),
        }

    expected = "exhausted_at_cap" if variant == "weak" else "defended"
    base = {
        "model": model, "label": label, "ok": True,
        "lang": entry["lang"], "category": entry["category"], "variant": variant,
        "verdict": result["verdict"], "matches_expected": result["verdict"] == expected,
        "turns": result["turns"], "elapsed_s": result["elapsed_s"],
    }

    # Track B: 성공한 job만 채점(transcript가 완결된 경우만 채점 의미 있음)
    try:
        question = result["transcript"][0]["question"]
        answer_text = _transcript_text(result["transcript"])
        graded = lig.grade_answer(CLIENT, entry["finding"], question, answer_text)
        base["graded"] = True
        base["grading"] = {axis: graded[axis]["score"] for axis in lig.FR_AXES}
    except Exception as e:
        base["graded"] = False
        base["grading_error"] = str(e)

    return base


def summarize(all_results: list) -> dict:
    summary = {}
    for model in MODELS:
        rows = [r for r in all_results if r["model"] == model]
        ok_rows = [r for r in rows if r["ok"]]
        total = len(rows)
        ok_count = len(ok_rows)
        matched = sum(1 for r in ok_rows if r.get("matches_expected"))
        graded_rows = [r for r in ok_rows if r.get("graded")]

        def mean_axis(variant, axis):
            vals = [r["grading"][axis] for r in graded_rows if r["variant"] == variant]
            return sum(vals) / len(vals) if vals else None

        strong_avg = [sum(r["grading"].values()) / len(r["grading"]) for r in graded_rows if r["variant"] == "strong"]
        weak_avg = [sum(r["grading"].values()) / len(r["grading"]) for r in graded_rows if r["variant"] == "weak"]
        # Track B 정밀도: strong 평균점수 > weak 평균점수인 비율 (기존 Track B 방법론 재사용,
        # finding 단위로 짝지어 비교)
        by_finding_strong = {r["label"].rsplit(":", 1)[0]: sum(r["grading"].values()) / len(r["grading"])
                              for r in graded_rows if r["variant"] == "strong"}
        by_finding_weak = {r["label"].rsplit(":", 1)[0]: sum(r["grading"].values()) / len(r["grading"])
                            for r in graded_rows if r["variant"] == "weak"}
        common = set(by_finding_strong) & set(by_finding_weak)
        precision_hits = sum(1 for f in common if by_finding_strong[f] > by_finding_weak[f])

        self_correction_improving = mean_axis("improving", "자기_수정")
        self_correction_weak = mean_axis("weak", "자기_수정")

        summary[model] = {
            "job_success_rate": round(ok_count / total, 3) if total else 0.0,
            "verdict_matches_expected_rate": round(matched / ok_count, 3) if ok_count else None,
            "mean_elapsed_s": round(sum(r["elapsed_s"] for r in ok_rows) / ok_count, 1) if ok_count else None,
            "grading_success_rate": round(len(graded_rows) / ok_count, 3) if ok_count else None,
            "track_b_precision": round(precision_hits / len(common), 3) if common else None,
            "mean_score_strong": round(sum(strong_avg) / len(strong_avg), 2) if strong_avg else None,
            "mean_score_weak": round(sum(weak_avg) / len(weak_avg), 2) if weak_avg else None,
            "self_correction_improving": round(self_correction_improving, 2) if self_correction_improving is not None else None,
            "self_correction_weak": round(self_correction_weak, 2) if self_correction_weak is not None else None,
            "n_ok": ok_count, "n_total": total, "n_graded": len(graded_rows),
        }
    return summary


def main():
    global CLIENT
    pool = NvidiaKeyPool.from_env()
    CLIENT = NvidiaRotatingClient(pool=pool)

    out_dir = os.path.dirname(os.path.abspath(__file__))
    raw_path = os.path.join(out_dir, "turn_engine_grading_multilang_results.json")

    results = []
    for model in MODELS:
        jobs = [(model, entry, variant) for entry in FINDINGS for variant in ("strong", "weak", "improving")]
        print(f"=== {model}: {len(jobs)} jobs ===", flush=True)
        results.extend(run_concurrent(jobs, call_one, max_workers=6, progress=print_progress))
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        time.sleep(3)

    summary = summarize(results)
    with open(os.path.join(out_dir, "turn_engine_grading_multilang_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== 요약 ===")
    for model, s in summary.items():
        print(f"{model}: job_success={s['job_success_rate']*100:.0f}% "
              f"trackB_precision={(s['track_b_precision'] or 0)*100:.0f}% "
              f"자기수정(improving/weak)={s['self_correction_improving']}/{s['self_correction_weak']} "
              f"mean_elapsed={s['mean_elapsed_s']}s ({s['n_ok']}/{s['n_total']})")


if __name__ == "__main__":
    main()
