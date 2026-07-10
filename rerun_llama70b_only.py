# D98: llama-3.3-70b-instruct 재시도 -- 이전 라운드(D97) 보류분을 나중에(시간대 다른 상태에서)
#   재시도. 사전 진단(raw urllib 3회, 57.0/63.9/74.3초 전부 성공)으로 워커 과부하가 지금은
#   풀려있는 것으로 확인 후 착수.
#   설정: workers=4(D97 교훈 -- RateLimitedClient가 이미 스레드세이프, workers=1은 근거
#   없는 과잉보수였음), timeout_s=300(관측된 단일호출 55~75초에 4턴 몰아도 여유), 이미
#   성공한 job은 스킵(재사용 가능하도록 rerun_nemotron_only.py와 동일 구조).
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

RPM_CAP = 12
LLAMA_TIMEOUT_S = DEFAULT_TIMEOUT_S  # D98: centralized in timeout_config.py (user request)
# D98: reverted to workers=1 after 3/3 jobs at workers=4 failed at exactly 300.1s each --
# too consistent to be coincidence. Unlike nemotron (token-budget issue, concurrency-safe),
# this model's failure mode is NVIDIA-side worker-queue capacity ("153/16", D94) -- a
# constraint on simultaneous requests to that model, independent of which of the 7 pooled
# API keys sends them. Concurrency itself reproduces the congestion; serializing avoids it.
LLAMA_WORKERS = 1
MODEL = "meta/llama-3.3-70b-instruct"


def main():
    out_dir = REPO
    raw_path = os.path.join(out_dir, "turn_engine_grading_16models_sonnet_results.json")
    with open(raw_path, encoding="utf-8") as f:
        existing = json.load(f)

    pool = NvidiaKeyPool.from_env()
    all_labels = {(entry["lang"] + ":" + entry["finding"]["id"], variant): entry
                  for entry in d94.FINDINGS for variant in ("strong", "weak", "improving")}
    already_ok = {
        (r["label"].rsplit(":", 1)[0], r["variant"])
        for r in existing
        if r["model"] == MODEL and r["ok"]
    }
    jobs = [(MODEL, entry, variant)
            for (lang_finding, variant), entry in all_labels.items()
            if (lang_finding, variant) not in already_ok]

    print(f"=== {MODEL} 재시도: {len(jobs)}/{len(all_labels)} jobs (기존 성공 {len(already_ok)}건 스킵, "
          f"timeout_s={LLAMA_TIMEOUT_S:.0f}, workers={LLAMA_WORKERS}) ===", flush=True)

    client = retry40.RateLimitedClient(NvidiaRotatingClient(pool=pool, timeout_s=LLAMA_TIMEOUT_S), rpm=RPM_CAP)
    d94.CLIENT = client
    rerun2.d94.CLIENT = client

    new_rows = run_concurrent(
        jobs,
        lambda j: rerun2.call_one_with_tokens(j, DEFAULT_MAX_TOKENS),  # D104: was literal 512
        max_workers=LLAMA_WORKERS,
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

    backup_path = raw_path + ".bak3"
    shutil.copyfile(raw_path, backup_path)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n회복된 건: {replaced}/{len(new_rows)}")
    ok_total = sum(1 for r in merged if r["ok"])
    print(f"전체 성공률(병합 후): {ok_total}/{len(merged)} ({ok_total/len(merged)*100:.0f}%)")

    summary = d94.summarize(merged)
    lang_summary = d94.by_lang(merged)
    with open(os.path.join(out_dir, "turn_engine_grading_16models_sonnet_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "turn_engine_grading_16models_sonnet_by_lang.json"), "w", encoding="utf-8") as f:
        json.dump(lang_summary, f, ensure_ascii=False, indent=2)

    s = summary[MODEL]
    print(f"\n{MODEL}: job_success={s['job_success_rate']*100:.0f}% "
          f"trackB_precision={(s['track_b_precision'] or 0)*100:.0f}% "
          f"자기수정(improving/weak)={s['self_correction_improving']}/{s['self_correction_weak']} "
          f"mean_elapsed={s['mean_elapsed_s']}s ({s['n_ok']}/{s['n_total']})")


if __name__ == "__main__":
    main()
