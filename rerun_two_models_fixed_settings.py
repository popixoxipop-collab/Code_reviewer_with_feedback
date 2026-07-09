# D94b: llama-3.3-70b-instruct / nemotron-super-49b-v1.5 재실행(진단으로 확정된 원인에 맞춰
#   설정값만 조정 -- 사용자 요청: "이 두 모델만 고친 설정으로 재실행해서 실데이터까지 채워라").
#   WHY: D94 raw HTTP 진단(README D94 참고)으로 두 모델 다 "영구 결함"이 아니라 "설정값이 안
#        맞음"으로 확정됐다. llama-3.3-70b-instruct는 NVIDIA가 HTTP 503
#        "Worker local total request limit reached (153/16)"을 직접 반환했고 재시도 시
#        188초 만에 정상 응답 -- client 기본 timeout(120s)이 짧을 뿐이라 timeout_s=240으로
#        올려서 재실행한다. nemotron-super-49b-v1.5는 reasoning 모델이라 max_tokens=512(기본)
#        로는 내부 chain-of-thought만 쓰다 finish_reason="length"로 끊기는 게 3회 진단 전부
#        재현됐다 -- turn_engine.py(D94b에서 max_tokens를 선택 인자로 추가, 기본값은 무변경)
#        에 max_tokens=2048을 넘겨 재실행한다.
#   설계: 두 모델은 서로 다른 client 설정이 필요해(타임아웃 vs 토큰수) 순차로 나눠 실행한다.
#        레이트리밋 게이팅은 retry_16models_sonnet_40rpm.py의 RateLimitedClient를 그대로
#        재사용(모델 1개씩 순차라 폭주 위험은 낮지만 안전장치로 유지).
#   EXIT: 이번에도 회복이 안 되면(예: 이 시점에도 워커 큐가 과부하) 진짜 시간대 의존적 문제라는
#        게 재확인되는 것 -- 다른 시간대 재시도가 다음 단계.
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

from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402
from harness import run_concurrent, print_progress  # noqa: E402
from turn_engine import run_decision_point, _transcript_text  # noqa: E402
import llm_interview_grader as lig  # noqa: E402

_spec94 = importlib.util.spec_from_file_location("d94", os.path.join(REPO, "benchmark_turn_engine_grading_16models_sonnet.py"))
d94 = importlib.util.module_from_spec(_spec94)
_spec94.loader.exec_module(d94)

_specretry = importlib.util.spec_from_file_location("retry40", os.path.join(REPO, "retry_16models_sonnet_40rpm.py"))
retry40 = importlib.util.module_from_spec(_specretry)
_specretry.loader.exec_module(retry40)

# D94c: long-running rerun should mimic the single-call diagnosis more closely.
# A single API key + long-latency models + 4 workers pushed llama-3.3-70b back
# into worker-queue overload. Run both models effectively serially, with a lower
# RPM cap, so timeout/max_tokens changes can be evaluated without extra burst.
RPM_CAP = 12
LLAMA_TIMEOUT_S = 360.0
LLAMA_WORKERS = 1
NEMOTRON_TIMEOUT_S = 180.0
NEMOTRON_WORKERS = 1


def _is_dns_failure(row):
    err = row.get("error", "")
    return "nodename nor servname provided" in err or "Name or service not known" in err


def call_one_with_tokens(job, max_tokens):
    model, entry, variant = job
    repo_root = os.path.join(d94.SCRATCH_REPOS, entry["repo_name"])
    label = f"{entry['lang']}:{entry['finding']['id']}:{variant}"
    answer_fn = d94._make_sonnet_answer_fn(variant, entry["finding"])

    import time
    t0 = time.time()
    try:
        result = run_decision_point(entry["finding"], repo_root, answer_fn, d94.CLIENT, model, max_tokens=max_tokens)
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
        "transcript": result["transcript"],
    }
    try:
        question = result["transcript"][0]["question"]
        answer_text = _transcript_text(result["transcript"])
        graded = lig.grade_answer(d94.CLIENT, entry["finding"], question, answer_text)
        base["graded"] = True
        base["grading"] = {axis: graded[axis]["score"] for axis in lig.FR_AXES}
    except Exception as e:
        base["graded"] = False
        base["grading_error"] = str(e)
    return base


def main():
    out_dir = REPO
    raw_path = os.path.join(out_dir, "turn_engine_grading_16models_sonnet_results.json")
    with open(raw_path, encoding="utf-8") as f:
        existing = json.load(f)

    pool = NvidiaKeyPool.from_env()
    jobs_llama = [("meta/llama-3.3-70b-instruct", entry, variant)
                  for entry in d94.FINDINGS for variant in ("strong", "weak", "improving")]
    jobs_nemotron = [("nvidia/llama-3.3-nemotron-super-49b-v1.5", entry, variant)
                      for entry in d94.FINDINGS for variant in ("strong", "weak", "improving")]

    all_new = []

    print(
        f"=== llama-3.3-70b-instruct: {len(jobs_llama)} jobs "
        f"(timeout_s={LLAMA_TIMEOUT_S:.0f}, max_tokens=512, workers={LLAMA_WORKERS}) ===",
        flush=True,
    )
    d94.CLIENT = retry40.RateLimitedClient(NvidiaRotatingClient(pool=pool, timeout_s=LLAMA_TIMEOUT_S), rpm=RPM_CAP)
    all_new.extend(
        run_concurrent(
            jobs_llama,
            lambda j: call_one_with_tokens(j, 512),
            max_workers=LLAMA_WORKERS,
            progress=print_progress,
        )
    )

    print(
        f"\n=== nemotron-super-49b-v1.5: {len(jobs_nemotron)} jobs "
        f"(timeout_s={NEMOTRON_TIMEOUT_S:.0f}, max_tokens=2048, workers={NEMOTRON_WORKERS}) ===",
        flush=True,
    )
    d94.CLIENT = retry40.RateLimitedClient(
        NvidiaRotatingClient(pool=pool, timeout_s=NEMOTRON_TIMEOUT_S),
        rpm=RPM_CAP,
    )
    all_new.extend(
        run_concurrent(
            jobs_nemotron,
            lambda j: call_one_with_tokens(j, 2048),
            max_workers=NEMOTRON_WORKERS,
            progress=print_progress,
        )
    )

    if all_new and all(not r["ok"] for r in all_new) and all(_is_dns_failure(r) for r in all_new):
        raise RuntimeError(
            "all rerun jobs failed with DNS/network resolution errors; refusing to overwrite existing results"
        )

    new_by_key = {(r["model"], r["label"]): r for r in all_new}
    merged = []
    replaced = 0
    preserved_ok = 0
    for r in existing:
        key = (r["model"], r["label"])
        if key in new_by_key:
            nr = new_by_key[key]
            if nr["ok"]:
                if not r["ok"]:
                    replaced += 1
                merged.append(nr)
            else:
                if r["ok"]:
                    preserved_ok += 1
                    merged.append(r)
                else:
                    merged.append(nr)
        else:
            merged.append(r)

    backup_path = raw_path + ".bak"
    shutil.copyfile(raw_path, backup_path)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n회복된 건: {replaced}/{len(all_new)}")
    print(f"기존 성공 결과 보존: {preserved_ok}건")
    ok_total = sum(1 for r in merged if r["ok"])
    print(f"전체 성공률(병합 후): {ok_total}/{len(merged)} ({ok_total/len(merged)*100:.0f}%)")

    summary = d94.summarize(merged)
    lang_summary = d94.by_lang(merged)
    with open(os.path.join(out_dir, "turn_engine_grading_16models_sonnet_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "turn_engine_grading_16models_sonnet_by_lang.json"), "w", encoding="utf-8") as f:
        json.dump(lang_summary, f, ensure_ascii=False, indent=2)

    print("\n=== 요약 (해당 2모델) ===")
    for model in ["meta/llama-3.3-70b-instruct", "nvidia/llama-3.3-nemotron-super-49b-v1.5"]:
        s = summary[model]
        print(f"{model}: job_success={s['job_success_rate']*100:.0f}% "
              f"trackB_precision={(s['track_b_precision'] or 0)*100:.0f}% "
              f"자기수정(improving/weak)={s['self_correction_improving']}/{s['self_correction_weak']} "
              f"mean_elapsed={s['mean_elapsed_s']}s ({s['n_ok']}/{s['n_total']})")


if __name__ == "__main__":
    main()
