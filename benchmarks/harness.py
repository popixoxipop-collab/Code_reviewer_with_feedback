# D61: full_survey.py/rerun_failed.py의 ThreadPoolExecutor+as_completed+진행률출력 루프를
#   공용 모듈로 추출(3번째 벤치마크가 필요해지는 지금이 추출 시점 — score_findings.py D13
#   EXIT의 "3번째로 필요해지면 공용 모듈로 추출" 원칙과 동일).
#   WHY: 채점 벤치마크(feedback/llm_interview_grader.py)와 MEAS-02 추출기 벤치마크
#        (judgment/meas02_decision_point_extractor.py)가 둘 다 이 동시호출 패턴을 필요로 함 —
#        각자 인라인 구현하면 세 번째 복붙이 됨.
#   COST: 호출부가 늘면 같이 맞춰야 하는 모듈 경계 하나 생김.
#   EXIT: 벤치마크가 하나만 남으면 호출부에 도로 인라인.
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed


def run_concurrent(jobs: list, call_fn, max_workers: int = 8, progress=None) -> list:
    """call_fn(job)을 jobs 전체에 대해 동시 실행한다 — 완료 순서는 보장하지 않는다.

    call_fn(job) -> dict; 예외는 여기서 잡지 않는다 — call_one() 계열 호출부가 이미
    자기 스키마에 맞는 실패 결과를 스스로 만들 줄 알기 때문(full_survey.py/rerun_failed.py의
    기존 call_one() 참고). 어떤 실패 dict가 "정상"인지는 호출부만 안다.

    progress(done, total, result)가 주어지면 매 job 완료 시 호출한다 — 기존
    "[{done}/{total}] {tag} ..." 진행률 출력 컨벤션을 그대로 재사용하기 위함.
    """
    results = []
    total = len(jobs)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(call_fn, job): job for job in jobs}
        done = 0
        for fut in as_completed(futures):
            result = fut.result()
            results.append(result)
            done += 1
            if progress:
                progress(done, total, result)
    return results


def print_progress(done: int, total: int, result: dict) -> None:
    """full_survey.py/rerun_failed.py가 쓰던 진행률 출력 한 줄을 그대로 재현한다."""
    tag = "OK " if result.get("ok") else "ERR"
    model = result.get("model", "?")
    label = result.get("label", result.get("finding_id", result.get("case_id", "?")))
    elapsed = result.get("elapsed_s", 0.0)
    print(f"[{done}/{total}] {tag} {model:45s} {label:45s} {elapsed:>6.1f}s", flush=True)
