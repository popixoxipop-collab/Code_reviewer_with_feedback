# D94c: D94b 재실행 결과가 Claude 구독 주간 사용량 한도 소진으로 오염된 걸 바로잡는다.
#   WHY: D94b(rerun_two_models_fixed_settings.py, 다른 세션이 편집한 버전)가 도는 도중 이
#        머신의 Claude 구독 주간 한도가 소진됐다. `claude -p --model sonnet --safe-mode`가
#        한도 초과 시 에러를 던지는 대신 "You've hit your weekly limit · resets Jul 11 at
#        12pm (Asia/Seoul)"을 stdout에 그대로 출력하는데, `_sonnet_call()`은 "비어있지
#        않은 문자열이면 유효한 답변"으로만 검사해서(D94 COST에 이미 이 종류의 위험을
#        암시는 했으나 실제로 겪은 건 이번이 처음) 이 문구를 학생의 실제 답변으로 그대로
#        받아들였다. 그 결과 nemotron-super-49b-v1.5는 23/24, llama-3.3-70b-instruct는
#        3/24가 전부 이 가짜 답변으로 채워진 "성공" job이었고(채점기가 이 무의미한 텍스트를
#        정확히 최저점 1점으로 채점해 모든 축이 1.0으로 균일하게 나온 게 오히려 채점기
#        자체는 정상 작동했다는 방증), 이 오염된 데이터가 이미 커밋(939b812)되고
#        origin/main에 push되어 GitHub Pages(popixoxipop-collab.github.io/
#        Code_reviewer_with_feedback)에 "D94b 완료, 95.8%"로 공개 노출된 상태였다.
#   설계: transcript의 answer 필드에서 "weekly limit"/"hit your" 패턴을 검사해 오염된 job을
#        찾아 ok=False로 되돌리고 error 필드에 원인을 명시적으로 남긴다(조용히 삭제하지
#        않음 -- 나중에 왜 이 job이 실패로 재분류됐는지 감사 가능해야 함). 나머지 14개
#        모델의 데이터는 오염 없음을 이미 확인(grep으로 전수조사, 매치 0건) -- 무수정.
#   COST: 이 두 모델은 이번 수정으로 다시 사실상 0%(nemotron은 원래도 500에러 1건 있었으니
#        여전히 0/24, llama-3.3-70b-instruct도 3건 전부 오염이라 0/24)로 돌아간다 -- D94b가
#        시도했던 설정값 수정(timeout 확대/max_tokens 확대) 자체가 틀렸다는 뜻이 아니라,
#        그 시도 도중 완전히 별개의 이유(계정 사용량 한도)로 데이터가 못 쓰게 됐다는 것.
#        진단(README D94)에서 확정한 원인 자체는 여전히 유효 -- 재검증은 한도 리셋 이후.
#   EXIT: 주간 한도가 2026-07-11 12:00(Asia/Seoul)에 리셋되므로 그 이후에 D94b를 다시
#        돌리면 된다. 재발 방지책: `_sonnet_call()`에 "weekly limit"/"usage limit" 패턴
#        가드를 추가해 이런 응답을 즉시 예외로 처리하도록 하는 게 다음 단계(이번 스크립트
#        범위 밖 -- 사후 교정만 담당).
from __future__ import annotations

import json
import os

REPO = os.path.dirname(os.path.abspath(__file__))
RAW_PATH = os.path.join(REPO, "turn_engine_grading_16models_sonnet_results.json")

QUOTA_MARKERS = ("weekly limit", "hit your", "usage limit")


def is_contaminated(row):
    for turn in row.get("transcript") or []:
        answer = turn.get("answer", "")
        if any(m in answer for m in QUOTA_MARKERS):
            return True
    return False


def main():
    with open(RAW_PATH, encoding="utf-8") as f:
        rows = json.load(f)

    fixed = 0
    for r in rows:
        if r.get("ok") and is_contaminated(r):
            r["ok"] = False
            r["graded"] = False
            r.pop("grading", None)
            r.pop("verdict", None)
            r.pop("matches_expected", None)
            r["error"] = "CONTAMINATED: claude -p returned weekly-usage-limit message, not a real answer (D94c correction, 2026-07-10)"
            fixed += 1

    print(f"오염 job {fixed}건을 ok=False로 교정")

    with open(RAW_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    import importlib.util
    import sys
    sys.path.insert(0, os.path.join(REPO, "feedback"))
    sys.path.insert(0, os.path.join(REPO, "judgment"))
    sys.path.insert(0, os.path.join(REPO, "pipeline"))
    sys.path.insert(0, os.path.join(REPO, "benchmarks"))
    spec = importlib.util.spec_from_file_location("d94", os.path.join(REPO, "benchmark_turn_engine_grading_16models_sonnet.py"))
    d94 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d94)

    summary = d94.summarize(rows)
    lang_summary = d94.by_lang(rows)
    with open(os.path.join(REPO, "turn_engine_grading_16models_sonnet_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(REPO, "turn_engine_grading_16models_sonnet_by_lang.json"), "w", encoding="utf-8") as f:
        json.dump(lang_summary, f, ensure_ascii=False, indent=2)

    print("\n=== 교정 후 두 모델 상태 ===")
    for m in ["meta/llama-3.3-70b-instruct", "nvidia/llama-3.3-nemotron-super-49b-v1.5"]:
        s = summary[m]
        print(f"{m}: job_success={s['job_success_rate']*100:.0f}% (n_ok={s['n_ok']}/{s['n_total']})")

    ok_total = sum(1 for r in rows if r["ok"])
    print(f"\n전체 성공률(교정 후): {ok_total}/{len(rows)} ({ok_total/len(rows)*100:.0f}%)")


if __name__ == "__main__":
    main()
