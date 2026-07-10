# D100 EXIT: mistral-nemotron(HTTP 500, D73/D89 계보)과 mistral-large-3(시간 단위 차단,
#   D90/D91 계보)는 nemotron-super-49b-v1.5와 달리 "설정값이 안 맞아서"가 아니라
#   "그 시점 NVIDIA 서버/계정 상태가 안 좋아서" 실패했을 가능성 -- 즉 원인이 일시적일
#   수 있다는 가설. D91은 단일 키로 90분 폴링해도 mistral-large-3가 전혀 안 풀리는 걸
#   확인했지만(가설 반증), 그때는 API 키가 1개뿐이었다. 지금은 7개 키 풀이 있고
#   NvidiaKeyPool이 매 요청마다 라운드로빈하므로, 이번 재시도는 D91의 EXIT가 요구했던
#   "다중 키 동시 테스트"를 사실상 처음으로 수행한다 -- 여전히 전부 실패하면 "시간단위
#   클라이언트 버킷"이 아니라 "서버 정책적 차단"이라는 결론이 강해진다.
#
# D103: 위의 "reasoning 모델이 아니니 max_tokens=512면 충분"이라는 가정이 실측으로
#   반증됨. 512로 돌린 1차 재시도에서 mistral-large-3 실패 17건의 error가 전부
#   'Unterminated string starting at: line 1 column 14' 한 종류 -- 모델이 ask_question
#   tool은 제대로 호출하는데 arguments JSON이 max_tokens 캡에 걸려 중간에 잘린 것.
#   (단문 프롬프트 진단은 0.6~1.4s에 통과했으나 실제 job은 코드 컨텍스트가 붙어 질문이
#   길어짐. 같은 512 run에서도 질문이 우연히 짧게 나온 6건은 통과 -- truncation 복권.)
#   같은 job을 max_tokens=2048로 단건 재현 -> 93.1s에 4턴 정상 완료로 검증.
#   즉 D90/D91의 "시간 단위 차단"은 이미 풀렸고(즉발 429가 더는 없음), 남은 문제는
#   nemotron(D97)과 같은 부류(max_tokens 기아)의 다른 증상(내부 reasoning 소진이 아니라
#   tool arguments 서술이 김). reasoning 모델 여부로 2048 필요성을 판단하면 안 된다는 교훈.
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

# D102: mistral-nemotron dropped from this run after a raw single-call diagnostic
#   (bypassing the whole harness, client-side cap set well above the observed cutoff so
#   our own client-side limit couldn't fire first) came back "HTTPError after 302.3s:
#   code=504 reason=Gateway Timeout" -- NVIDIA's own gateway is killing the request
#   around ~300s regardless of what we ask for client-side, so no client setting
#   (workers, timeout_s, max_tokens) can fix this. The first 16/16 jobs in the actual
#   harness run all failed at an identical ~302s too, consistent with this. Re-add
#   "mistralai/mistral-nemotron" here if NVIDIA's side recovers later.
TARGET_MODELS = ["mistralai/mistral-large-3-675b-instruct-2512"]
RPM_CAP = 12
RETRY_TIMEOUT_S = DEFAULT_TIMEOUT_S  # D98: centralized in timeout_config.py (user request)
RETRY_WORKERS = 4  # no queue-overload diagnosis for these two (unlike llama-3.3-70b-instruct) -- no reason to serialize
MAX_TOKENS = DEFAULT_MAX_TOKENS  # D103 root cause -> D104 centralized (512 truncated tool-call args mid-JSON, 17/17 identical errors; 2048 repro passed)


def main():
    out_dir = REPO
    raw_path = os.path.join(out_dir, "turn_engine_grading_16models_sonnet_results.json")
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

    print(f"=== {' + '.join(TARGET_MODELS)} 재시도: {len(jobs)}/{len(all_labels) * len(TARGET_MODELS)} jobs "
          f"(timeout_s={RETRY_TIMEOUT_S:.0f}, max_tokens={MAX_TOKENS}, workers={RETRY_WORKERS}) ===", flush=True)
    client = retry40.RateLimitedClient(NvidiaRotatingClient(pool=pool, timeout_s=RETRY_TIMEOUT_S), rpm=RPM_CAP)
    d94.CLIENT = client
    rerun2.d94.CLIENT = client
    new_rows = run_concurrent(
        jobs,
        lambda j: rerun2.call_one_with_tokens(j, MAX_TOKENS),
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

    for m in TARGET_MODELS:
        s = summary[m]
        print(f"\n{m}: job_success={s['job_success_rate']*100:.0f}% "
              f"trackB_precision={(s['track_b_precision'] or 0)*100:.0f}% "
              f"자기수정(improving/weak)={s['self_correction_improving']}/{s['self_correction_weak']} "
              f"mean_elapsed={s['mean_elapsed_s']}s ({s['n_ok']}/{s['n_total']})")


if __name__ == "__main__":
    main()
