# D106: 4축 벤치마크 재구성 (사용자 지시: "호출 안정성/정밀도/재현성/속도 축 4개로 벤치마킹")
#   WHY: 4축 중 2축이 기존 데이터로는 결손 상태였다.
#     (1) 재현성 -- D89~D94 내내 REPEATS=1로 미측정(README가 반복 명시해온 한계).
#     (2) 정밀도 -- 더 심각한 발견: D93 헤더는 "turn_engine을 실행한 그 모델이 자기
#         transcript를 채점한다"(기획명세서 Locked: 질문생성기=채점기 동일 모델)고 선언했지만,
#         repo 전체에 lig.MODEL을 후보 모델로 바꾸는 코드가 없다 -- grade_answer()는 모듈
#         전역 MODEL(기본 qwen3-next-80b)로만 채점해왔다. 즉 지금까지의 track_b_precision은
#         "고정 grader가 후보의 질문으로 만들어진 transcript를 채점"한 값이지 "후보가 채점기
#         역할을 얼마나 잘하나"가 아니었다(모든 모델의 grading_success_rate가 1.0이었던 것도
#         이것으로 설명됨 -- 채점기는 항상 검증된 qwen이었으니까).
#   설계: 신뢰 가능 5개 모델의 기존 ok transcript(Sonnet 답변 포함, 총 113건)를 재사용해
#     각 후보 모델이 "자기" transcript를 REPEATS=3회 채점한다(temperature=0.0).
#     - 정밀도(신규): candidate-as-grader로 strong>weak 분리(기존 summarize()와 동일 산식,
#       3회 반복 평균 점수 기준) -- 이제서야 스펙이 말한 "채점기 역할" 측정.
#     - 재현성(신규): 같은 입력 3회 채점의 5축 벡터 완전일치율(headline) + 총점 spread.
#     - 채점 규격준수율(보조): 채점 tool-call이 유효 스키마로 돌아온 비율 -- 질문생성기
#       역할의 job 성공률과 별개로, 채점기 역할의 안정성.
#     - 호출 안정성/속도: 기존 summary(job_success_rate/mean_elapsed_s) 재사용(질문생성 역할).
#   COST: Sonnet 호출 0건(transcript 재사용). NVIDIA 채점 콜 113 x 3 = 339건, 전역 12rpm
#     페이싱으로 ~29분. 대상은 신뢰 가능 5개(순위가 의미있는 집합)만 -- 부분성공 4개는 표본
#     자체가 부족해 재채점해도 순위 신뢰도가 안 생기고, mistral-large-3는 현재 모델 스코프
#     스로틀에 막혀 있다(D103).
#   EXIT: 5개 외 모델로 확장하려면 MODELS_5에 추가(표본이 생긴 뒤에). REPEATS 상향은 상수 하나.
#     lig.MODEL 갭 자체의 수정(공식 하니스가 후보를 채점기로 쓰게)은 별도 결정 사항 --
#     이 스크립트는 하니스 무수정으로 옆에서 측정한다.
#
#   재시도 정책: 이 스크립트에는 재시도 루프가 아예 없다 -- 채점 콜은 job당 정확히 1회,
#   실패는 그대로 기록하고 다음 job으로 넘어간다(재현성 측정에서 실패도 데이터다).
#   순간 처리율은 RateLimitedClient(전역 12rpm 슬라이딩 윈도우)가 담당한다.
#   # retry-backoff-guard: intentional-no-backoff
from __future__ import annotations

import collections
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
sys.path.insert(0, REPO)

from timeout_config import DEFAULT_TIMEOUT_S, DEFAULT_MAX_TOKENS  # noqa: E402
from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402
from harness import run_concurrent, print_progress  # noqa: E402
from turn_engine import _transcript_text  # noqa: E402
import llm_interview_grader as lig  # noqa: E402

_spec94 = importlib.util.spec_from_file_location("d94", os.path.join(REPO, "benchmark_turn_engine_grading_16models_sonnet.py"))
d94 = importlib.util.module_from_spec(_spec94)
_spec94.loader.exec_module(d94)

_specretry = importlib.util.spec_from_file_location("retry40", os.path.join(REPO, "retry_16models_sonnet_40rpm.py"))
retry40 = importlib.util.module_from_spec(_specretry)
_specretry.loader.exec_module(retry40)

# D106c: mistral-large-3가 게이트 러너로 24/24(100%) 완전 회복(D103 EXIT 이행)하면서
#   신뢰 가능 티어가 5 -> 6개로 확장 -- 재채점 대상에 포함.
# D110b: "개별 진단 미실시 5개"의 실패분 재실행(rerun_partial_five.py)으로 전원 20+/24
#   진입(deepseek 24/24, minimax·nemotron-3 23/24, glm 21/24, qwen3.5 20/24) --
#   신뢰 티어 6 -> 11개. 승격 5개를 4축 재채점 대상에 추가.
RELIABLE_MODELS = [
    "qwen/qwen3-next-80b-a3b-instruct",
    "stepfun-ai/step-3.5-flash",
    "mistralai/mistral-medium-3.5-128b",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "meta/llama-4-maverick-17b-128e-instruct",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "minimaxai/minimax-m3",
    "qwen/qwen3.5-122b-a10b",
    "deepseek-ai/deepseek-v4-pro",
    "nvidia/nemotron-3-super-120b-a12b",
    "z-ai/glm-5.2",
]
# D115: REPEATS를 env로 조절 가능하게(사용자 지시: "재현성 엄밀성을 위해 100번 반복
#   밴치마킹") -- 기본값 3은 유지(기존 스크립트/문서가 이 기본값을 전제로 함), 대규모
#   재현성 재측정만 REGRADE_REPEATS=100으로 명시 실행.
REPEATS = int(os.environ.get("REGRADE_REPEATS", "3"))
# D106e: mistral-large-3 실측(2026-07-10) -- 이 flagship 모델의 429는 분당 창이 아니라
#   천천히 재충전되는 시간 단위 총량 버킷이다: 단발 프로브는 통과(65s 간격 3연속 200)해도
#   72콜 일괄 발사는 전멸했고, ~100콜 소진 후엔 단발조차 ~1시간 전멸했다. 이런 모델은
#   낮은 rpm으로 버킷 재충전 속도 아래에서 돌려야 하므로 env로 페이스 조절 가능하게 한다.
RPM_CAP = int(os.environ.get("REGRADE_RPM", "12"))
WORKERS = int(os.environ.get("REGRADE_WORKERS", "4"))

# D108b: 채점기 역할 자체가 결함으로 확정된 모델 -- 재채점 반복이 무의미(콜당 전체 토큰
#   예산을 태우며 실패)하므로 재실행 대상에서 제외하고 사유를 summary에 남긴다.
#   mistral-large-3 실측(2026-07-10, 단건 재현 3회): 5축 채점 tool-call에서 퇴행 생성 루프 --
#   cap=2048/4096/8192 전부 finish_reason="length"로 예산 완전 소진(completion_tokens=cap)인데
#   가시 출력은 args 809~907자 + reasoning_content 0자. 캡 2배 상향이 args를 60자만 늘림 =
#   유한한 캡으로 해결 불가. 단순 스키마(ask_question, 1필드)는 24/24 정상이므로 이건
#   "복잡한 스키마에서만 터지는" 모델/서빙측 결함 -- 질문생성기 적합, 채점기 부적합.
GRADER_ROLE_DEFECTS = {
    "mistralai/mistral-large-3-675b-instruct-2512": (
        "degenerate tool-call loop on the 5-axis grading schema: caps 2048/4096/8192 all "
        "burn the FULL completion budget (completion_tokens == cap, finish_reason=length) "
        "while emitting only ~850-907 chars of arguments and zero reasoning_content -- no "
        "finite cap can fix this. The simple ask_question schema works fine (24/24), so the "
        "model is usable as question generator but NOT as grader (locked spec requires both roles)."
    ),
}

# D109: 장기 서빙 장애로 재채점(채점기 역할 측정) 자체가 불가능했던 모델 -- 사용자 결정으로
#   "이 모델도 연결 안정성이 떨어진다"로 기록하고 벤치마크 마감. D108c 원칙 그대로:
#   10시간+ 동안 단순 호출("Say OK")조차 전부 타임아웃(3분/10분 간격 워처 2라운드, 총 82회
#   프로브 전부 실패)이면 채점기 역할의 실효 가용성은 0이다 -- 원인이 모델 결함이 아니라
#   NVIDIA 서빙이라는 건 annotation으로 남기되, 축 점수는 실측 그대로(안정성 0) 반영한다.
SERVING_OUTAGE = {
    "meta/llama-4-maverick-17b-128e-instruct": (
        "sustained NVIDIA serving outage: every probe over a 10+ hour window timed out "
        "(82 probes across two watcher rounds, even plain 'Say OK' calls), so the grader "
        "role could never be measured. Per the D108c end-to-end rule a grader that cannot "
        "be reached grades nothing -- stability(grader)=0, precision/reproducibility=0. "
        "Question-generator stability (0.875, 21/24) was measured before the outage."
    ),
}

# D111/D116: raw 행은 있으나 실패 원인이 모델이 아니라 측정 시간대의 NVIDIA 서빙 장애인 모델 --
#   순위 점수(안정성 0)는 실측 그대로 두되, 원인을 annotation으로 명시(억울한 판정 방지).
GRADER_MEASUREMENT_OUTAGE = {
    # D116: D111의 DEGRADED 사건과는 별개 재발 -- REPEATS=100 재측정(2026-07-12) 도중
    #   2300/2300 콜 전부 다시 HTTP 400 DEGRADED. 사용자 결정으로 재시도 없이 이 결과를
    #   그대로 최종 기록(라이브 프로브로 종료 직후 정상 복구 확인 -- 모델 결함 아님, 측정
    #   창에서만 강등된 것).
    "minimaxai/minimax-m3": (
        "2300/2300 grading calls in the REPEATS=100 rerun (2026-07-12) hit a uniform "
        "HTTP 400 '...DEGRADED function cannot be invoked' -- a recurrence of the same "
        "DEGRADED-function pattern first seen in the REPEATS=3 run. NOT a model defect: "
        "a live probe immediately after this run completed got HTTP 200 in 0.6s, and the "
        "question-generator role passed 23/24 throughout. User decision: record as final "
        "rather than re-run (2026-07-12) -- the composite score reflects an infra outage "
        "window, not the model's real grading capability."
    ),
}

# D116: 새로 발견된 패턴 -- mistral-large-3(D103)에서만 본 "모델별 천천히 재충전되는
#   총량 쿼타 버킷"이 사실은 더 넓게 존재했다. REPEATS=100 재측정에서 한 모델에 30~40분
#   동안 2000+콜을 몰아치자 glm-5.2(2100콜 중 1883건 429)·deepseek-v4-pro(2400콜 중
#   1719건 429)가 무너짐 -- 두 모델 다 몇 시간 전 REPEATS=3에서는 각각 98.4%/100%
#   완벽했다. 종료 직후 라이브 단발 프로브로도 둘 다 여전히 429 확인(버킷이 아직 안 풀림,
#   추측이 아니라 실측). D112/D113가 검증한 "60rpm 안전"은 step-3.5-flash 한 모델로만
#   확인한 것이라 전 모델에 일반화되지 않는다는 걸 이번에 알았다 -- 다음에 이런 대량
#   단일모델 벤치마크를 설계할 때는 모델별로 낮은 rpm(mistral-large-3에 썼던 6rpm 수준)을
#   기본값으로 삼아야 한다.
VOLUME_QUOTA_BURST_INCIDENT = {
    "z-ai/glm-5.2": (
        "1883/2100 grading calls in the REPEATS=100 rerun (2026-07-12) hit HTTP 429 "
        "'Too Many Requests' after ~35 minutes of sustained ~60/min load to this single "
        "model -- the same slow-recharging model-scoped quota bucket pattern documented "
        "for mistral-large-3 (D103), now confirmed on a second model. NOT a rate-limit "
        "logic bug (D112/D113 verified the pool respects per-key 40rpm with zero 429s "
        "using step-3.5-flash) and NOT a reproducibility problem: this same model scored "
        "98.4% grading success hours earlier at REPEATS=3, low volume. A live probe "
        "immediately after this run completed still got HTTP 429. User decision: record "
        "as final rather than wait-and-retry (2026-07-12)."
    ),
    "deepseek-ai/deepseek-v4-pro": (
        "1719/2400 grading calls in the REPEATS=100 rerun (2026-07-12) hit HTTP 429 "
        "after ~40 minutes of sustained ~60/min load to this single model -- same pattern "
        "as glm-5.2 above. This model had PERFECT end-to-end stability (24/24 question-gen, "
        "72/72 grading) at REPEATS=3 just hours earlier. A live probe immediately after "
        "this run completed still got HTTP 429. User decision: record as final rather "
        "than wait-and-retry (2026-07-12)."
    ),
}
# D106b: NVIDIA 부분 장애(같은 시각 qwen·maverick만 90s 프로브 초과, 나머지 정상) 대응 --
#   CLI 인자로 대상 모델 서브셋 지정 가능. raw 파일은 모델 단위로 병합(이번 대상만 교체,
#   나머지 모델의 기존 행 보존)해서 장애 모델은 회복 후 개별 재실행하면 된다.
# D106d: --aggregate-only = API 콜 없이 기존 raw 파일만 재집계(집계 로직 수정 후 재계산용)
AGGREGATE_ONLY = "--aggregate-only" in sys.argv
_args = [a for a in sys.argv[1:] if a != "--aggregate-only"]
TARGETS = _args if _args else RELIABLE_MODELS
for _t in TARGETS:
    if _t not in RELIABLE_MODELS:
        raise SystemExit(f"unknown target model: {_t} (choose from RELIABLE_MODELS)")

CLIENT = None
_findings_by_key = {}
for entry in d94.FINDINGS:
    _findings_by_key[f"{entry['lang']}:{entry['finding']['id']}"] = entry["finding"]


def grade_with_model(model: str, finding: dict, question: str, answer: str) -> dict:
    """lig._grade_via_nvidia와 동일하되 모듈 전역 MODEL 대신 후보 모델을 명시적으로 쓴다.

    lig.MODEL을 임시로 바꿔치기하는 방식은 workers>1에서 레이스가 나므로
    (모듈 전역 = 스레드 공유 상태) 명시 인자 버전을 별도로 둔다.
    """
    response = CLIENT.chat(
        model=model,
        messages=[{"role": "user", "content": lig.build_grading_prompt(finding, question, answer)}],
        tools=[lig._as_openai_tool(lig.GRADING_TOOL)],
        tool_choice={"type": "function", "function": {"name": "grade_interview_answer"}},
        max_tokens=DEFAULT_MAX_TOKENS,
        temperature=0.0,
    )
    return lig.parse_nvidia_tool_response(response)


def call_one(job):
    model, label, variant, finding, question, answer_text, rep = job
    t0 = time.time()
    try:
        graded = grade_with_model(model, finding, question, answer_text)
        return {
            "model": model, "label": label, "variant": variant, "rep": rep, "ok": True,
            "grading": {axis: graded[axis]["score"] for axis in lig.FR_AXES},
            "elapsed_s": round(time.time() - t0, 1),
        }
    except Exception as e:
        return {
            "model": model, "label": label, "variant": variant, "rep": rep, "ok": False,
            "error": str(e)[:300], "elapsed_s": round(time.time() - t0, 1),
        }


def main():
    global CLIENT
    raw_path = os.path.join(REPO, "turn_engine_grading_16models_sonnet_results.json")
    with open(raw_path, encoding="utf-8") as f:
        existing = json.load(f)

    raw_out = os.path.join(REPO, "turn_engine_4axis_regrade_raw.json")
    if AGGREGATE_ONLY:
        with open(raw_out, encoding="utf-8") as f:
            rows = json.load(f)
        print(f"=== aggregate-only: {len(rows)} raw rows 재집계 (API 콜 없음) ===", flush=True)
    else:
        # 이 스크립트는 재시도 루프 없음(job당 1콜, 실패도 데이터) -- 헤더 정책 참고.
        # retry-backoff-guard: intentional-no-backoff
        jobs = []
        n_transcripts = 0
        for r in existing:
            if r["model"] not in TARGETS or not r.get("ok") or not r.get("transcript"):
                continue
            lang_finding = r["label"].rsplit(":", 1)[0]
            finding = _findings_by_key.get(lang_finding)
            if finding is None:
                continue
            question = r["transcript"][0]["question"]
            answer_text = _transcript_text(r["transcript"])
            n_transcripts += 1
            for rep in range(REPEATS):
                jobs.append((r["model"], r["label"], r["variant"], finding, question, answer_text, rep))

        print(f"=== 4축 재채점 (대상 {len(TARGETS)}모델): {n_transcripts} transcripts x {REPEATS} repeats = {len(jobs)} grading calls "
              f"(candidate-as-grader, timeout_s={DEFAULT_TIMEOUT_S:.0f}, max_tokens={DEFAULT_MAX_TOKENS}, "
              f"rpm={RPM_CAP}, workers={WORKERS}) ===", flush=True)

        pool = NvidiaKeyPool.from_env()
        CLIENT = retry40.RateLimitedClient(NvidiaRotatingClient(pool=pool, timeout_s=DEFAULT_TIMEOUT_S), rpm=RPM_CAP)

        rows = run_concurrent(jobs, call_one, max_workers=WORKERS, progress=print_progress)

        # D106b: 모델 단위 병합 -- 이번 TARGETS의 행만 교체, 다른 모델의 기존 행은 보존
        merged_rows = []
        if os.path.exists(raw_out):
            with open(raw_out, encoding="utf-8") as f:
                merged_rows = [r for r in json.load(f) if r["model"] not in TARGETS]
        merged_rows.extend(rows)
        rows = merged_rows
        with open(raw_out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

    # ---- 집계 (raw에 행이 있는 모델 전부 -- 부분 실행이 쌓이면 자동으로 커버리지 확장) ----
    old_summary = json.load(open(os.path.join(REPO, "turn_engine_grading_16models_sonnet_summary.json"), encoding="utf-8"))
    covered = [m for m in RELIABLE_MODELS if any(r["model"] == m for r in rows)]
    summary = {}
    for model in covered:
        mrows = [r for r in rows if r["model"] == model]
        by_label = {}
        for r in mrows:
            by_label.setdefault(r["label"], []).append(r)

        n_calls = len(mrows)
        n_ok_calls = sum(1 for r in mrows if r["ok"])

        # D115: mode_agreement_rate/coverage_rate 신규 추가 (사용자 지시로 REPEATS 3->100
        #   대규모 재측정 진행하며 설계). identical_rate의 기존 판정 기준("len(ok_reps)==
        #   REPEATS 완전 성공"만 분모에 포함)은 그대로 둔다 -- 처음엔 ">=2회 성공"으로
        #   완화해봤으나 실측으로 반증됨: qwen3.5-122b(coverage=0.667, 대부분 2/3 성공)의
        #   identical_rate가 0.5->0.733으로 급등하는 걸 확인 -- N이 작을수록(2개 비교가
        #   3개 비교보다) "우연히 다 일치"하기 쉬운 통계적 착시였다(coverage 낮은 모델일수록
        #   유리해지는 역설적 편향). 그래서 이미 공개된 identical_rate/composite_4axis
        #   계산 기준(정확히 REPEATS개 성공해야 분모에 포함)은 변경하지 않고 그대로 유지 --
        #   대신 REPEATS가 커질 때의 "커버리지 급락" 문제는 mode_agreement_rate(성공한
        #   반복 중 최빈 5축 벡터 점유율, 연속값이라 부분 커버리지에도 상대적으로 안정적)와
        #   coverage_rate(모델 일관성과 인프라 노이즈를 분리해서 보여주는 참고 지표)로
        #   별도 노출한다 -- 랭킹에 쓰는 identical_rate는 절대 건드리지 않는다.
        full_ok, identical, spreads = 0, 0, []
        mode_rates, coverages = [], []
        for label, reps in by_label.items():
            ok_reps = [r for r in reps if r["ok"]]
            totals = [sum(r["grading"].values()) for r in ok_reps]
            if reps:
                coverages.append(len(ok_reps) / len(reps))
            if len(ok_reps) >= 2:
                spreads.append(max(totals) - min(totals))
                vecs = [tuple(sorted(r["grading"].items())) for r in ok_reps]
                mode_count = collections.Counter(vecs).most_common(1)[0][1]
                mode_rates.append(mode_count / len(ok_reps))
            if len(ok_reps) == REPEATS:
                full_ok += 1
                vecs = [tuple(sorted(r["grading"].items())) for r in ok_reps]
                if len(set(vecs)) == 1:
                    identical += 1

        # 정밀도(candidate-as-grader): 3회 평균 총점 기준 strong > weak (기존 산식과 동일 구조)
        mean_total = {}
        for label, reps in by_label.items():
            ok_reps = [r for r in reps if r["ok"]]
            if ok_reps:
                mean_total[label] = sum(sum(r["grading"].values()) for r in ok_reps) / len(ok_reps)
        strong_by_finding, weak_by_finding = {}, {}
        for label, total in mean_total.items():
            lang_finding, variant = label.rsplit(":", 1)
            if variant == "strong":
                strong_by_finding[lang_finding] = total
            elif variant == "weak":
                weak_by_finding[lang_finding] = total
        common = set(strong_by_finding) & set(weak_by_finding)
        precision_hits = sum(1 for k in common if strong_by_finding[k] > weak_by_finding[k])

        old = old_summary.get(model, {})
        job_sr = old.get("job_success_rate")
        grader_sr = round(n_ok_calls / n_calls, 3) if n_calls else None
        # D108c(사용자 지적 "그럼 그냥 4축 중에 연결 안정성이 낮은 거잖아"): 안정성 축은
        #   두 역할을 합친 end-to-end다 -- 스펙이 한 모델에 질문생성기+채점기를 둘 다
        #   요구하므로, 실전 job 성공확률 ~= P(질문생성 성공) x P(채점 성공). 채점기
        #   결함(large-3 퇴행 루프, nemotron 스키마 미준수)은 별도 카테고리로 빼서 순위
        #   제외하는 게 아니라 이 축의 낮은 점수로 순위에 반영된다.
        stability_combined = round(job_sr * grader_sr, 3) if (job_sr is not None and grader_sr is not None) else None
        summary[model] = {
            # 축 1: 호출 안정성 = 질문생성 성공률 x 채점 성공률 (end-to-end, 두 역할 통합)
            "stability_combined": stability_combined,
            "stability_question_gen": job_sr,
            "stability_grader_call": grader_sr,
            # 축 2: 정밀도 (채점기 역할, 이번에 처음으로 candidate-as-grader로 측정)
            "precision_candidate_as_grader": round(precision_hits / len(common), 3) if common else None,
            "precision_fixed_grader_legacy": old.get("track_b_precision"),
            # 축 3: 재현성 -- identical_rate(이진, >=2회 성공한 label 중 완전일치 비율,
            #   레거시 연속성 유지) + mode_agreement_rate(연속값, D115 신규 주 지표) +
            #   coverage_rate(REPEATS 대비 실제 성공률 -- 모델 일관성과 인프라 노이즈 분리)
            "reproducibility_identical_rate": round(identical / full_ok, 3) if full_ok else None,
            "reproducibility_mode_agreement_rate": round(sum(mode_rates) / len(mode_rates), 3) if mode_rates else None,
            "reproducibility_mean_total_spread": round(sum(spreads) / len(spreads), 2) if spreads else None,
            "reproducibility_coverage_rate": round(sum(coverages) / len(coverages), 3) if coverages else None,
            "reproducibility_repeats": REPEATS,
            # 축 4: 속도 (질문생성기 역할, 기존 실측 재사용)
            "speed_mean_elapsed_s": old.get("mean_elapsed_s"),
            "n_transcripts": len(by_label), "n_grading_calls": n_calls,
        }

    # 종합 지수: 4축 min-max 정규화 평균 (속도는 역정규화)
    def _norm(vals):
        xs = [v for v in vals if v is not None]
        lo, hi = min(xs), max(xs)
        return {i: ((v - lo) / (hi - lo) if hi > lo else 1.0) if v is not None else None
                for i, v in enumerate(vals)}

    # D109: 서빙 장애로 raw 행이 아예 없는 모델도 순위에 포함 -- 안정성(채점)=0으로 합성 엔트리
    for m, why in SERVING_OUTAGE.items():
        if m in RELIABLE_MODELS and m not in summary:
            old = old_summary.get(m, {})
            job_sr = old.get("job_success_rate")
            summary[m] = {
                "stability_combined": 0.0,
                "stability_question_gen": job_sr,
                "stability_grader_call": 0.0,
                "precision_candidate_as_grader": None,
                "precision_fixed_grader_legacy": old.get("track_b_precision"),
                "reproducibility_identical_rate": None,
                "reproducibility_mean_total_spread": None,
                "speed_mean_elapsed_s": old.get("mean_elapsed_s"),
                "n_transcripts": 0, "n_grading_calls": 0,
                "serving_outage": why,
            }
            covered.append(m)

    # D108b: 채점기 결함 확정 모델은 사유를 summary에 명시(문서화용 -- 순위 제외는 안 함)
    for m, why in GRADER_ROLE_DEFECTS.items():
        if m in summary:
            summary[m]["grader_role_defect"] = why
    # D111: 측정 시간대 서빙 장애 annotation (모델 결함 아님을 명시)
    # D114: 실측이 채워지면(채점 성공 존재) annotation을 달지 않는다 -- minimax가 워처
    #   자동 재채점으로 회복(채점 68/69)했는데 "69콜 전멸" 문구가 계속 붙는 낡음 방지.
    for m, why in GRADER_MEASUREMENT_OUTAGE.items():
        if m in summary and (summary[m].get("stability_grader_call") or 0) == 0:
            summary[m]["grader_measurement_outage"] = why
    # D116: 총량 쿼타 버킷 소진 annotation -- 부분 성공(0%가 아님)이라 위 outage 조건
    #   (==0)에 안 걸리므로 별도 무조건 적용. 사용자 결정으로 재시도 없이 이 수치를 최종
    #   기록하되, 원인이 재현성이 아니라 인프라 총량제임을 명시(D103 mistral-large-3와
    #   동일 계열 패턴이 이번에 2개 모델에서 추가 확인됨).
    for m, why in VOLUME_QUOTA_BURST_INCIDENT.items():
        if m in summary:
            summary[m]["volume_quota_burst_incident"] = why

    # D108c: 전 모델을 순위에 포함한다. 채점 콜이 전멸한 모델(정밀도/재현성 미측정)은
    #   축을 건너뛰는 게 아니라 0으로 친다 -- "채점을 한 번도 성공 못한 채점기"의 유효
    #   정밀도/재현성은 0이 맞다(측정불가 != 무죄). D106d의 "빠진 축 건너뛰고 평균" 왜곡
    #   (large-3가 안정성+속도만으로 1위)과 "특수 카테고리 제외"(사용자 지적) 둘 다 폐기.
    ranked = list(covered)
    stab = _norm([summary[m]["stability_combined"] or 0.0 for m in ranked])
    prec = _norm([summary[m]["precision_candidate_as_grader"] or 0.0 for m in ranked])
    repr_ = _norm([summary[m]["reproducibility_identical_rate"] or 0.0 for m in ranked])
    spd = _norm([-(summary[m]["speed_mean_elapsed_s"] or 0) for m in ranked])
    for i, m in enumerate(ranked):
        parts = [stab[i], prec[i], repr_[i], spd[i]]
        summary[m]["composite_4axis"] = round(sum(parts) / len(parts), 3)
    summary["_meta"] = {
        "covered_models": covered,
        "ranked_models": ranked,
        "note": "stability axis = question-gen success x grader-call success (end-to-end, both roles per locked spec). Models whose grading never succeeded score 0 on precision/reproducibility instead of being excluded -- a grader that cannot grade has zero effective precision. composite_4axis is min-max normalized within ranked_models and uses reproducibility_identical_rate (unchanged formula, for continuity across REPEATS values). D115: reproducibility_mode_agreement_rate is the more robust reproducibility read at large REPEATS -- identical_rate requires a perfect run across ALL repeats to even count a transcript, which under-samples as REPEATS grows (see code comment); reproducibility_coverage_rate separates infra noise (call failures) from actual grader inconsistency (repeated calls disagreeing).",
    }

    with open(os.path.join(REPO, "turn_engine_4axis_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== 4축 결과 ===", flush=True)
    for m in sorted(covered, key=lambda x: -(summary[x]["composite_4axis"] if summary[x]["composite_4axis"] is not None else -1)):
        s = summary[m]
        print(f"{m}\n  안정성(end-to-end)={s['stability_combined']} (질문생성={s['stability_question_gen']} x 채점={s['stability_grader_call']})  "
              f"정밀도(자기채점)={s['precision_candidate_as_grader']}  재현성={s['reproducibility_identical_rate']} "
              f"(mode={s.get('reproducibility_mode_agreement_rate')} coverage={s.get('reproducibility_coverage_rate')} "
              f"spread={s['reproducibility_mean_total_spread']} n={s.get('reproducibility_repeats')})  "
              f"속도={s['speed_mean_elapsed_s']}s  종합={s['composite_4axis']}", flush=True)


if __name__ == "__main__":
    main()
