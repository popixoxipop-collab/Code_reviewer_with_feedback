# D94b: 첫 16모델 라이브 실행(283/384 실패, 26% 성공)의 실패분만 40rpm 전역 레이트리미터로
#   재시도한다.
#   WHY: 사용자 지적 -- 실패 원인 분포(timeout 75/tool_choice 70/429 49/5xx 35/404 24/기타 30)를
#        그냥 D90처럼 무작정 재시도하면 D92가 이미 진단한 자기 자신을 자초한 버스트가 그대로
#        재현된다. D92 실측: `nvidia_client.py`의 429 재시도가 **딜레이 0으로 즉시** 같은
#        루프에서 최대 3회 재시도하고, `run_decision_point()`가 실패 시 즉시 예외를 던지므로
#        "job 1개 실패 = 실제 HTTP 요청 최대 3회"다. 여기에 max_workers=6 동시성이 겹치면
#        순간 처리율이 40rpm을 실제로 넘을 수 있다는 게 D92의 결론 -- 이번 첫 실행(job 384개,
#        16모델 순차)은 이 진단 이후에도 레이트리밋을 코드로 강제한 적이 없었다.
#   설계: `nvidia_client.py`(vendored, D56 원칙에 따라 핵심 오케스트레이션/vendored 코드는
#        무수정)를 직접 고치는 대신, 그 바깥을 얇게 감싸는 RateLimitedClient로 전역
#        슬라이딩윈도우 40rpm을 강제한다 -- `.chat()` 호출 직전 항상 이 게이트를 통과해야
#        한다(스레드 세이프, threading.Lock). vendored 클라이언트 내부의 무백오프 재시도
#        자체는 여전히 안 고쳐지지만(그건 D92 EXIT가 이미 "핵심 오케스트레이션 무수정 원칙과
#        상충해 범위 밖"이라 명시), 바깥 게이트가 40rpm보다 여유(30rpm)를 두면 내부 최대 3배
#        재시도가 순간적으로 튀어도 창 안에 흡수될 여지가 생긴다. max_workers도 6->4로 낮춰
#        슬롯 해제 시점에 몰리는 thundering-herd를 완화한다.
#   대상: 실패 283건 중 kimi-k2.6의 24건(HTTP 404, `/v1/models`엔 있지만 실제 채팅 엔드포인트가
#        모델을 못 찾음 -- 레이트리밋과 무관한 계정 접근권한 문제로 판단, 재시도로 안 풀림)은
#        제외하고 259건만 재시도한다.
#   EXIT: 이번에도 특정 모델이 반복적으로 0건이면(예: gpt-oss-120b의 tool_choice 미준수, 이미
#        D66/D80/D89에서 반복 확인된 결함) 그건 레이트리밋이 아니라 모델 자체 결함으로 확정할
#        수 있다 -- 재시도 후 결과로 구분.
from __future__ import annotations

import collections
import importlib.util
import json
import os
import sys
import threading
import time

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "feedback"))
sys.path.insert(0, os.path.join(REPO, "judgment"))
sys.path.insert(0, os.path.join(REPO, "pipeline"))
sys.path.insert(0, os.path.join(REPO, "benchmarks"))

from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402
from harness import run_concurrent, print_progress  # noqa: E402

spec = importlib.util.spec_from_file_location("d94", os.path.join(REPO, "benchmark_turn_engine_grading_16models_sonnet.py"))
d94 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d94)

RPM_CAP = 30  # 사용자 지시 40rpm보다 여유를 둠 -- vendored client 내부 무백오프 재시도가
              # 논리 호출 1개당 최대 3배까지 튈 수 있어(D92), 바깥 게이트는 30으로 낮춰 잡는다.
NOT_RETRYABLE_MODELS = {"moonshotai/kimi-k2.6"}  # HTTP 404 -- 계정 접근권한 문제, 재시도 무의미


class RateLimitedClient:
    """`.chat()` 호출 직전 전역 슬라이딩윈도우(RPM_CAP/분)를 강제하는 얇은 래퍼.
    vendored NvidiaRotatingClient는 무수정 -- D56 원칙 유지."""

    def __init__(self, inner, rpm=RPM_CAP):
        self._inner = inner
        self._rpm = rpm
        self._lock = threading.Lock()
        self._timestamps = collections.deque()

    def chat(self, *args, **kwargs):
        self._wait_for_slot()
        return self._inner.chat(*args, **kwargs)

    def _wait_for_slot(self):
        while True:
            with self._lock:
                now = time.time()
                while self._timestamps and now - self._timestamps[0] > 60:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._rpm:
                    self._timestamps.append(now)
                    return
                sleep_for = 60 - (now - self._timestamps[0]) + 0.05
            time.sleep(max(sleep_for, 0.05))


def _entry_for_label(label):
    lang_finding = label.rsplit(":", 1)[0]
    for entry in d94.FINDINGS:
        if f"{entry['lang']}:{entry['finding']['id']}" == lang_finding:
            return entry
    raise KeyError(label)


def main():
    out_dir = REPO
    raw_path = os.path.join(out_dir, "turn_engine_grading_16models_sonnet_results.json")
    with open(raw_path, encoding="utf-8") as f:
        existing = json.load(f)

    failed = [r for r in existing if not r["ok"] and r["model"] not in NOT_RETRYABLE_MODELS]
    print(f"재시도 대상: {len(failed)}건 (전체 실패 {sum(1 for r in existing if not r['ok'])}건 중 "
          f"kimi-k2.6 {sum(1 for r in existing if not r['ok'] and r['model'] in NOT_RETRYABLE_MODELS)}건 제외)")

    jobs = []
    for r in failed:
        entry = _entry_for_label(r["label"])
        variant = r["variant"]
        jobs.append((r["model"], entry, variant))

    pool = NvidiaKeyPool.from_env()
    d94.CLIENT = RateLimitedClient(NvidiaRotatingClient(pool=pool), rpm=RPM_CAP)

    print(f"=== 재시도 {len(jobs)} jobs (전역 {RPM_CAP}rpm, max_workers=4) ===", flush=True)
    retried = run_concurrent(jobs, d94.call_one, max_workers=4, progress=print_progress)

    # 병합: label+model 키로 매칭해 성공한 재시도만 원본 실패 행을 교체(D90 병합 패턴 재사용)
    retried_by_key = {(r["model"], r["label"]): r for r in retried}
    merged = []
    replaced = 0
    for r in existing:
        key = (r["model"], r["label"])
        if key in retried_by_key:
            new_r = retried_by_key[key]
            if new_r["ok"] and not r["ok"]:
                replaced += 1
            merged.append(new_r)
        else:
            merged.append(r)

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n재시도로 회복된 건: {replaced}/{len(jobs)}")
    ok_total = sum(1 for r in merged if r["ok"])
    print(f"전체 성공률(병합 후): {ok_total}/{len(merged)} ({ok_total/len(merged)*100:.0f}%)")

    summary = d94.summarize(merged)
    lang_summary = d94.by_lang(merged)
    with open(os.path.join(out_dir, "turn_engine_grading_16models_sonnet_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "turn_engine_grading_16models_sonnet_by_lang.json"), "w", encoding="utf-8") as f:
        json.dump(lang_summary, f, ensure_ascii=False, indent=2)

    print("\n=== 요약 (병합 후) ===")
    for model, s in summary.items():
        print(f"{model}: job_success={s['job_success_rate']*100:.0f}% "
              f"trackB_precision={(s['track_b_precision'] or 0)*100:.0f}% "
              f"자기수정(improving/weak)={s['self_correction_improving']}/{s['self_correction_weak']} "
              f"mean_elapsed={s['mean_elapsed_s']}s ({s['n_ok']}/{s['n_total']})")


if __name__ == "__main__":
    main()
