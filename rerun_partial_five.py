# D110: "개별 진단 미실시 5개" 모델의 실패분 일괄 재실행 (사용자 지시: "병렬로 개별 진단")
#   WHY: 로컬 error 분포 분석으로 진단이 사실상 끝남 -- 5모델의 실패 69건은 3클래스:
#     (a) HTTP 429 (minimax 5·deepseek 13·glm 13): D94b 버스트 시대(무백오프 재시도+동시성6)
#         잔재. 지금의 전역 12rpm 페이싱에선 대부분 통과할 것으로 예상.
#     (b) content=None (qwen3.5-122b 10건 전부): D97 nemotron-49b와 동일 시그니처 --
#         reasoning 모델이 당시 캡 512를 내부 추론으로 소진해 tool 호출 전에 끊김.
#         현재 중앙값 4096(D108)이면 회복 유력.
#     (c) content에 추론 독백/JSON이 그대로 (nemotron-3 17건, glm 8건): 512가 tool 호출
#         전에 생성을 끊었거나(회복 가능) 모델이 tool_calls 대신 content에 흉내내는
#         진짜 미준수(회복 불가) -- 재실행이 곧 판별 실험.
#   설계: 5모델의 not-ok 행만 현재 설정(중앙 4096/600s, 12rpm, workers=4, 답변=haiku D107)
#     으로 재실행. 실패는 그대로 기록(재시도 없음) -- 클래스별 회복률이 곧 진단 결론.
#   COST: ~69 job x 5~7콜 ≈ 400+콜, 12rpm ≈ 35~40분. 신규 성공 행의 answer_model=haiku로
#     기존(sonnet)과 섞임 -- D107 감사 필드로 구분, 모델 간 비교 시 주의.
#   EXIT: 회복된 모델이 20+/24가 되면 신뢰 티어 승격 + 4축 재채점 대상(RELIABLE_MODELS 추가).
#
#   재시도 정책: 이 스크립트에 재시도 루프 없음(job당 1회, 실패도 데이터).
#   # retry-backoff-guard: intentional-no-backoff
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys

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

_spec94 = importlib.util.spec_from_file_location("d94", os.path.join(REPO, "benchmark_turn_engine_grading_16models_sonnet.py"))
d94 = importlib.util.module_from_spec(_spec94)
_spec94.loader.exec_module(d94)

_specretry = importlib.util.spec_from_file_location("retry40", os.path.join(REPO, "retry_16models_sonnet_40rpm.py"))
retry40 = importlib.util.module_from_spec(_specretry)
_specretry.loader.exec_module(retry40)

_specrerun = importlib.util.spec_from_file_location("rerun2", os.path.join(REPO, "rerun_two_models_fixed_settings.py"))
rerun2 = importlib.util.module_from_spec(_specrerun)
_specrerun.loader.exec_module(rerun2)

TARGET_MODELS = [
    "minimaxai/minimax-m3",
    "qwen/qwen3.5-122b-a10b",
    "deepseek-ai/deepseek-v4-pro",
    "nvidia/nemotron-3-super-120b-a12b",
    "z-ai/glm-5.2",
]
RPM_CAP = 12
RETRY_WORKERS = 4


def main():
    raw_path = os.path.join(REPO, "turn_engine_grading_16models_sonnet_results.json")
    with open(raw_path, encoding="utf-8") as f:
        existing = json.load(f)

    pool = NvidiaKeyPool.from_env()
    all_labels = {(entry["lang"] + ":" + entry["finding"]["id"], variant): entry
                  for entry in d94.FINDINGS for variant in ("strong", "weak", "improving")}
    already_ok = {
        (r["model"], r["label"].rsplit(":", 1)[0], r["variant"])
        for r in existing
        if r["model"] in TARGET_MODELS and r["ok"]
    }
    jobs = [(model, entry, variant)
            for model in TARGET_MODELS
            for (lang_finding, variant), entry in all_labels.items()
            if (model, lang_finding, variant) not in already_ok]

    print(f"=== 5모델 실패분 재실행: {len(jobs)}/{len(all_labels) * len(TARGET_MODELS)} jobs "
          f"(timeout_s={DEFAULT_TIMEOUT_S:.0f}, max_tokens={DEFAULT_MAX_TOKENS}, "
          f"rpm={RPM_CAP}, workers={RETRY_WORKERS}, answers={d94.ANSWER_MODEL}) ===", flush=True)

    client = retry40.RateLimitedClient(NvidiaRotatingClient(pool=pool, timeout_s=DEFAULT_TIMEOUT_S), rpm=RPM_CAP)
    d94.CLIENT = client
    rerun2.d94.CLIENT = client
    new_rows = run_concurrent(
        jobs,
        lambda j: rerun2.call_one_with_tokens(j, DEFAULT_MAX_TOKENS),
        max_workers=RETRY_WORKERS,
        progress=print_progress,
    )

    new_by_key = {(r["model"], r["label"]): r for r in new_rows}
    merged = []
    replaced = 0
    for r in existing:
        key = (r["model"], r["label"])
        if key in new_by_key:
            nr = new_by_key[key]
            if nr["ok"] and not r["ok"]:
                replaced += 1
            merged.append(nr)
        else:
            merged.append(r)

    shutil.copyfile(raw_path, raw_path + ".bak4")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n회복된 건: {replaced}/{len(new_rows)}")
    ok_total = sum(1 for r in merged if r["ok"])
    print(f"전체 성공률(병합 후): {ok_total}/{len(merged)} ({ok_total/len(merged)*100:.0f}%)")

    summary = d94.summarize(merged)
    lang_summary = d94.by_lang(merged)
    with open(os.path.join(REPO, "turn_engine_grading_16models_sonnet_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(REPO, "turn_engine_grading_16models_sonnet_by_lang.json"), "w", encoding="utf-8") as f:
        json.dump(lang_summary, f, ensure_ascii=False, indent=2)

    for m in TARGET_MODELS:
        s = summary[m]
        print(f"{m}: {s['n_ok']}/{s['n_total']} ({s['job_success_rate']*100:.0f}%) mean_elapsed={s['mean_elapsed_s']}s")


if __name__ == "__main__":
    main()
