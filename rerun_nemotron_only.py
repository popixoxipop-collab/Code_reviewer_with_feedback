# D94b (nemotron 단독): llama-3.3-70b-instruct는 사용자 판단으로 이번 라운드에서 보류
#   (600s 타임아웃에도 9/9 전부 실패, 워커 과부하가 일시적이 아니라 지속적인 것으로 보여
#   시간 대비 실익이 낮다고 판단) -- nemotron-super-49b-v1.5만 먼저 채운다.
#   설정은 rerun_two_models_fixed_settings.py의 기존 튜닝값(다른 세션이 조정) 그대로 재사용:
#   timeout_s=300, workers=1, RPM_CAP=12.
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
NEMOTRON_TIMEOUT_S = 600.0
NEMOTRON_WORKERS = 4
# workers=1 was inherited caution from llama-3.3-70b-instruct's *different* failure mode
# (NVIDIA worker-queue overload, HTTP 503 "153/16"). nemotron's issue was max_tokens
# starvation (now fixed), not queue contention -- and RateLimitedClient's sliding-window
# lock is already thread-safe and proven under workers=4 in the earlier 16-model retry.
# No reason to also serialize here (user question, 2026-07-10).


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
        if r["model"] == "nvidia/llama-3.3-nemotron-super-49b-v1.5" and r["ok"]
    }
    jobs = [("nvidia/llama-3.3-nemotron-super-49b-v1.5", entry, variant)
            for (lang_finding, variant), entry in all_labels.items()
            if (lang_finding, variant) not in already_ok]

    print(f"=== nemotron-super-49b-v1.5 재시도: {len(jobs)}/{len(all_labels)} jobs (기존 성공 {len(already_ok)}건은 스킵, timeout_s={NEMOTRON_TIMEOUT_S:.0f}, max_tokens=2048, workers={NEMOTRON_WORKERS}) ===", flush=True)
    # rerun2.call_one_with_tokens reads CLIENT off its OWN separately-loaded copy of the
    # d94 module (importlib.util module_from_spec makes independent instances per load) --
    # setting it on this file's `d94` name does nothing for that call path. Set both so
    # this file's own d94.FINDINGS/summarize() calls below stay consistent too.
    client = retry40.RateLimitedClient(NvidiaRotatingClient(pool=pool, timeout_s=NEMOTRON_TIMEOUT_S), rpm=RPM_CAP)
    d94.CLIENT = client
    rerun2.d94.CLIENT = client
    new_rows = run_concurrent(
        jobs,
        lambda j: rerun2.call_one_with_tokens(j, 2048),
        max_workers=NEMOTRON_WORKERS,
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

    backup_path = raw_path + ".bak2"
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

    s = summary["nvidia/llama-3.3-nemotron-super-49b-v1.5"]
    print(f"\nnemotron-super-49b-v1.5: job_success={s['job_success_rate']*100:.0f}% "
          f"trackB_precision={(s['track_b_precision'] or 0)*100:.0f}% "
          f"자기수정(improving/weak)={s['self_correction_improving']}/{s['self_correction_weak']} "
          f"mean_elapsed={s['mean_elapsed_s']}s ({s['n_ok']}/{s['n_total']})")


if __name__ == "__main__":
    main()
