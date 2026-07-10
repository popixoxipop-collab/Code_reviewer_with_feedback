# D94: D93(Track A+B+turn_engine 통합, 7모델)을 16개 후보 전체로 확장 + 답변 생성 방식 교체.
#   WHY: 사용자 요청 -- (1) NVIDIA Build 라이브 카탈로그(121개) 재조회로 16개 후보(검증 7 +
#        신규 9)/105개 제외를 확정(아티팩트 페이지에 이미 반영, 근거는 이 파일이 아니라
#        WebFetch로 카탈로그를 직접 재조회해 얻음 -- 카테고리 크기가 페이지 설명과 정확히
#        일치함을 확인했다). (2) turn_engine의 질의응답에서 "답변" 쪽을 D89~D93처럼 고정
#        strong/weak/improving 텍스트가 아니라 Sonnet이 매 턴 실시간으로 생성하도록 교체 --
#        단 3-조건(strong/weak/improving) 설계 자체는 유지(사용자 결정, Track B 정밀도/
#        자기수정 지표 계산이 이 구조에 의존하므로).
#   설계: turn_engine.run_decision_point(finding, repo_root, answer_fn, client, model)의
#        answer_fn(question, level) 시임을 그대로 사용 -- 이 시임은 D87이 "실제 세션이면
#        학생에게 묻는 함수, 벤치마크면 미리 준비된 답변을 순서대로 꺼내주는 함수로 교체 가능한
#        지점"이라고 이미 문서화해뒀다. 여기서는 세 번째 구현체를 추가한다: 매 호출마다
#        `claude -p --model sonnet --safe-mode`를 서브프로세스로 띄워 그 턴의 질문+finding
#        맥락에 실시간으로 답하게 한다. `--safe-mode`는 CLAUDE.md/hooks/MCP/skills를 전부
#        끄면서(이 리포의 무거운 전역 CLAUDE.md + 수십 개 MCP 서버가 매 호출마다 로딩되면
#        호출당 2분+ 걸림을 실측 확인, --safe-mode는 3.5초) OAuth 인증은 그대로 쓴다(--bare와
#        달리 keychain을 계속 읽음) -- 새 ANTHROPIC_API_KEY 발급 없이 기존 구독 인증 재사용.
#   COST: (1) 페르소나 프롬프트가 자기수정 답변에 "그래서/지금 보니/개선해야" 같은 표현을
#        직접 요구하지는 않지만, reflection_signal.py의 confirmed 패턴이 바로 이런 표현에서
#        나온 것이므로(D51/D88) Sonnet이 자연스럽게 비슷한 어투로 답할 경우 defended가, 다른
#        어투를 쓰면(내용은 진짜 자기수정이어도) 여전히 표면/부분으로 판정될 수 있다 -- 이건
#        새 버그가 아니라 D87 자체가 이미 문서화한 "정규식 채점기가 답변의 미묘한 표현 차이에
#        취약하다"는 알려진 한계가 실시간 생성 답변에서도 그대로 나타나는 것. (2) Sonnet 서브
#        프로세스 호출이 job당 최대 4회 추가되어 총 API 표면이 NVIDIA(질문생성+채점)와 별개로
#        최대 ~960회 더 늘어난다 -- 실행 규모는 사용자 확인 완료(16 x 4언어 x 8findings x
#        3variants, NVIDIA ~1500콜 + Sonnet ~700-1500콜, 1-3시간+ 예상).
#   EXIT: 16개 중 검증 완료 7개는 D93과 동일 finding/스크래치 repo 재사용. 신규 9개가 D93처럼
#        429/tool_choice 미준수로 낮은 성공률을 보이면 다중 키 확보가 우선순위(D89 EXIT와 동일
#        결론). 페르소나 프롬프트가 confirmed 패턴과 다른 어투로 수렴하면(COST 참고)
#        PERSONA_PROMPTS에 예시 어투를 추가하는 게 다음 조정 지점.
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "feedback"))
sys.path.insert(0, os.path.join(REPO, "judgment"))
sys.path.insert(0, os.path.join(REPO, "pipeline"))
sys.path.insert(0, os.path.join(REPO, "benchmarks"))
sys.path.insert(0, REPO)

from timeout_config import DEFAULT_TIMEOUT_S  # noqa: E402
from turn_engine import run_decision_point, _transcript_text  # noqa: E402
import llm_interview_grader as lig  # noqa: E402
from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402
from harness import run_concurrent, print_progress  # noqa: E402

# D89 스크립트를 파일로 로드해 FINDINGS(8건, lang/category/repo_name/finding)와 SCRATCH_REPOS를
# 재사용 -- strong_answer/weak_answer 텍스트 필드는 이 파일에서 안 쓴다(Sonnet이 대체).
_spec = importlib.util.spec_from_file_location("bte_d89", os.path.join(REPO, "benchmark_turn_engine_multilang.py"))
_bte_d89 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bte_d89)

SCRATCH_REPOS = _bte_d89.SCRATCH_REPOS
FINDINGS = _bte_d89.FINDINGS

# 16개 후보 = 검증 완료 7개(D89/D93, MODEL_ORDER와 동일 순서 유지) + 신규 9개(2026-07-08
# /v1/models 라이브 재조회, 121개 카탈로그에서 임베딩/비전/안전/번역/코드전용/도메인특화/
# 초대형/구형·극소형을 제외하고 남은 65개 범용 instruct 후보 중 선정 -- 아티팩트 페이지의
# "16개 후보 · 105개 제외 전체 목록"과 정합).
MODELS = [
    # 검증 완료 7개
    "qwen/qwen3-next-80b-a3b-instruct",
    "stepfun-ai/step-3.5-flash",
    "deepseek-ai/deepseek-v4-pro",
    "meta/llama-4-maverick-17b-128e-instruct",
    "openai/gpt-oss-120b",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "mistralai/mistral-nemotron",
    # 신규 9개
    "z-ai/glm-5.2",
    "moonshotai/kimi-k2.6",
    "minimaxai/minimax-m3",
    "qwen/qwen3.5-122b-a10b",
    "mistralai/mistral-medium-3.5-128b",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "nvidia/nemotron-3-super-120b-a12b",
    "meta/llama-3.3-70b-instruct",
    "openai/gpt-oss-20b",
]

SONNET_TIMEOUT_S = DEFAULT_TIMEOUT_S  # D98: centralized in timeout_config.py (user request)
SONNET_MAX_BUDGET_USD = "0.30"  # 호출당 안전장치 -- 정상 답변은 이 근처도 안 감

PERSONA_PROMPTS = {
    "strong": (
        "당신은 코드 리뷰 면접에서 자신의 설계 판단을 방어하는 학생입니다. 아래 질문에 "
        "자신감 있고 구체적인 근거를 들어 한국어로 2~4문장으로 답하세요. 실제 트레이드오프나 "
        "대안을 언급하며 명확하게 방어하세요. 다른 설명 없이 답변 텍스트만 출력하세요.\n\n"
        "## 코드/finding 맥락\n{context}\n\n## 질문\n{question}"
    ),
    "weak": (
        "당신은 코드 리뷰 면접에서 자신의 설계 판단에 확신이 없고 얼버무리는 학생입니다. "
        "아래 질문에 짧고(1~2문장) 모호하게, 구체적인 근거 없이 답하세요 -- '그냥 그렇게 "
        "했다', '잘 모르겠다' 같은 톤으로. 다른 설명 없이 답변 텍스트만 출력하세요.\n\n"
        "## 코드/finding 맥락\n{context}\n\n## 질문\n{question}"
    ),
    "improving_reflection": (
        "당신은 코드 리뷰 면접에서 여러 차례 반례 질문을 받은 끝에, 방금 자신의 설계 판단에 "
        "실제 결함이 있었음을 스스로 깨달은 학생입니다. 아래 질문에 진짜 자기수정을 담아 "
        "한국어로 2~4문장으로 답하세요: (1) 구체적으로 무엇을 놓쳤는지 인정하고, (2) 왜 "
        "그게 문제인지 이유를 설명하고, (3) 어떻게 고칠지 구체적인 개선안을 제시하세요. "
        "다른 설명 없이 답변 텍스트만 출력하세요.\n\n"
        "## 코드/finding 맥락\n{context}\n\n## 질문\n{question}"
    ),
}


# D94c: claude -p가 구독 사용량 한도를 넘으면 에러 종료 대신 이 문구를 stdout에 그대로
# 찍는다 -- 2026-07-10 실측(다른 세션의 D94b 재실행 도중 발생, 26개 job이 이 문구를 "학생
# 답변"으로 그대로 먹어 채점기가 전부 최저점 처리한 걸 사후 발견). 빈 문자열만 걸러내던
# 기존 가드로는 안 잡혀서 여기에 명시적으로 추가한다.
QUOTA_EXHAUSTED_MARKERS = ("weekly limit", "usage limit", "hit your")


def _sonnet_call(prompt: str) -> str:
    result = subprocess.run(
        [
            "claude", "-p", prompt,
            "--model", "sonnet",
            "--safe-mode",
            "--no-session-persistence",
            "--max-budget-usd", SONNET_MAX_BUDGET_USD,
        ],
        capture_output=True, text=True, timeout=SONNET_TIMEOUT_S,
    )
    text = (result.stdout or "").strip()
    if not text:
        raise RuntimeError(f"empty sonnet output (rc={result.returncode}): {(result.stderr or '')[:300]!r}")
    if any(marker in text for marker in QUOTA_EXHAUSTED_MARKERS):
        raise RuntimeError(f"claude -p returned a usage-limit message, not an answer: {text[:200]!r}")
    return text


def sonnet_answer(persona: str, finding: dict, question: str) -> str:
    prompt = PERSONA_PROMPTS[persona].format(context=finding.get("finding", ""), question=question)
    return _sonnet_call(prompt)


def _make_sonnet_answer_fn(variant: str, finding: dict):
    def answer_fn(question, level):
        if variant == "strong":
            return sonnet_answer("strong", finding, question)
        if variant == "weak":
            return sonnet_answer("weak", finding, question)
        persona = "improving_reflection" if level == "reflection" else "weak"
        return sonnet_answer(persona, finding, question)
    return answer_fn


CLIENT = None


def call_one(job):
    model, entry, variant = job
    repo_root = os.path.join(SCRATCH_REPOS, entry["repo_name"])
    label = f"{entry['lang']}:{entry['finding']['id']}:{variant}"
    answer_fn = _make_sonnet_answer_fn(variant, entry["finding"])

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
        "transcript": result["transcript"],  # D94 신규: Sonnet 답변 원문 감사 가능하게 보존
    }

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


def by_lang(all_results: list) -> dict:
    out = {}
    for model in MODELS:
        out[model] = {}
        for lang in ("python", "java", "javascript", "c_cpp"):
            rows = [r for r in all_results if r["model"] == model and r["lang"] == lang]
            ok_rows = [r for r in rows if r["ok"]]
            graded_rows = [r for r in ok_rows if r.get("graded")]
            by_finding_strong = {r["label"].rsplit(":", 1)[0]: sum(r["grading"].values()) / len(r["grading"])
                                  for r in graded_rows if r["variant"] == "strong"}
            by_finding_weak = {r["label"].rsplit(":", 1)[0]: sum(r["grading"].values()) / len(r["grading"])
                                for r in graded_rows if r["variant"] == "weak"}
            common = set(by_finding_strong) & set(by_finding_weak)
            prec = None
            if common:
                hits = sum(1 for f in common if by_finding_strong[f] > by_finding_weak[f])
                prec = round(hits / len(common), 3)
            out[model][lang] = {
                "job": round(len(ok_rows) / len(rows), 3) if rows else None,
                "n": f"{len(ok_rows)}/{len(rows)}",
                "prec": prec,
            }
    return out


def main():
    global CLIENT
    pool = NvidiaKeyPool.from_env()
    CLIENT = NvidiaRotatingClient(pool=pool)

    out_dir = os.path.dirname(os.path.abspath(__file__))
    raw_path = os.path.join(out_dir, "turn_engine_grading_16models_sonnet_results.json")

    results = []
    for model in MODELS:
        jobs = [(model, entry, variant) for entry in FINDINGS for variant in ("strong", "weak", "improving")]
        print(f"=== {model}: {len(jobs)} jobs ===", flush=True)
        results.extend(run_concurrent(jobs, call_one, max_workers=6, progress=print_progress))
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        time.sleep(3)

    summary = summarize(results)
    lang_summary = by_lang(results)
    with open(os.path.join(out_dir, "turn_engine_grading_16models_sonnet_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "turn_engine_grading_16models_sonnet_by_lang.json"), "w", encoding="utf-8") as f:
        json.dump(lang_summary, f, ensure_ascii=False, indent=2)

    print("\n=== 요약 ===")
    for model, s in summary.items():
        print(f"{model}: job_success={s['job_success_rate']*100:.0f}% "
              f"trackB_precision={(s['track_b_precision'] or 0)*100:.0f}% "
              f"자기수정(improving/weak)={s['self_correction_improving']}/{s['self_correction_weak']} "
              f"mean_elapsed={s['mean_elapsed_s']}s ({s['n_ok']}/{s['n_total']})")


if __name__ == "__main__":
    main()
