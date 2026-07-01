import json
import os
import sys
from datetime import datetime, timezone

from idiom_filter import IDIOMS_ROOT, SUPPORTED_LANGS, patterns_path_for, log_path_for

# D6: 단일 피드백으로 즉시 confirmed 승격하지 않고 threshold(기본 3회) 반복 확인 후 승격
#   WHY: 한 번의 판단으로 관용패턴 확정 시, 특정 사례 하나에 과적합되어 실제 위험 신호까지
#        묻어버릴 위험 있음(RunPod_Deploy_Agent BLOCK 남발 금지 사례, arXiv:2603.18059 —
#        엄격 policy(P4)에서 task 성공률 0.356→0.067로 붕괴한 선례를 그대로 적용)
#   COST: 승격까지 시간이 걸려 초반엔 관용패턴이 계속 "질문가치 상"으로 남아있음(느린 수렴)
#   EXIT: promotion_threshold는 idiom_patterns.json 필드로 노출되어 있어 값만 바꾸면 즉시 조정 가능
#
# D7: 이 재귀 루프 자체가 언어별로 독립 실행됨(judgment/idioms/<lang>/ 아래에서만 읽고 씀)
#   → 한 언어의 피드백 로그가 다른 언어의 승격 판정에 절대 섞이지 않는다.
#
# 재귀 루프 구조 (언어별로 동일하게 반복):
#   score_findings.py 실행 → (사람 또는 후속 리뷰가) finding을 "그냥 관용 패턴이었다"고 판정
#   → record_feedback(lang, ...)으로 idioms/<lang>/idiom_feedback_log.jsonl에 적재
#   → recursive_update(lang) 실행 → 같은 pattern_key가 threshold 이상 쌓이면 candidate→confirmed 승격
#     (아직 idiom_patterns.json에 없는 pattern_key면 자동으로 candidate 항목을 새로 만듦)
#   → 다음 score_findings.py 실행부터 idiom_filter.py가 해당 언어에서만 자동으로 질문가치를 낮춤


def _ensure_lang_dir(lang):
    if lang not in SUPPORTED_LANGS:
        raise ValueError(f"unsupported lang '{lang}', must be one of {SUPPORTED_LANGS}")
    os.makedirs(os.path.join(IDIOMS_ROOT, lang), exist_ok=True)


def _load_patterns(lang):
    path = patterns_path_for(lang)
    if not os.path.exists(path):
        return {"promotion_threshold": 3, "patterns": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_patterns(lang, data):
    with open(patterns_path_for(lang), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def record_feedback(lang, pattern_key, verdict, note="", description=""):
    """사람/후속 리뷰가 finding에 대해 내린 판정을 해당 언어 로그에만 적재한다.

    verdict: "idiom_not_decision"(그냥 관용 패턴) | "real_decision"(진짜 설계 판단이었음)
    즉시 idiom_patterns.json을 바꾸지 않음 — 승격은 recursive_update()에서만 일어난다.
    """
    _ensure_lang_dir(lang)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lang": lang,
        "pattern_key": pattern_key,
        "verdict": verdict,
        "note": note,
        "description": description,
    }
    with open(log_path_for(lang), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def recursive_update(lang):
    """해당 언어 로그 전체를 다시 집계해 threshold 이상인 pattern_key를 confirmed로 승격.

    다른 언어의 idioms/ 디렉토리는 전혀 건드리지 않는다(D7).
    """
    _ensure_lang_dir(lang)
    data = _load_patterns(lang)
    threshold = data["promotion_threshold"]
    by_id = {p["id"]: p for p in data["patterns"]}

    log_path = log_path_for(lang)
    if not os.path.exists(log_path):
        return data, []

    idiom_votes, descriptions = {}, {}
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry["verdict"] != "idiom_not_decision":
                continue
            key = entry["pattern_key"]
            idiom_votes[key] = idiom_votes.get(key, 0) + 1
            if entry.get("description"):
                descriptions[key] = entry["description"]

    promotions = []
    for key, votes in idiom_votes.items():
        if key not in by_id:
            by_id[key] = {"id": key, "description": descriptions.get(key, ""), "status": "candidate", "confirmations": 0}
        entry = by_id[key]
        entry["confirmations"] = votes
        if entry["status"] != "confirmed" and votes >= threshold:
            entry["status"] = "confirmed"
            promotions.append(key)

    data["patterns"] = list(by_id.values())
    _save_patterns(lang, data)
    return data, promotions


def update_all_langs():
    results = {}
    for lang in SUPPORTED_LANGS:
        if os.path.exists(log_path_for(lang)):
            _, promotions = recursive_update(lang)
            results[lang] = promotions
    return results


def main():
    if len(sys.argv) < 2:
        print("usage: idiom_hook.py feedback <lang> <pattern_key> <verdict> [note] [description]", file=sys.stderr)
        print("       idiom_hook.py update <lang>", file=sys.stderr)
        print("       idiom_hook.py update-all", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "feedback":
        lang, pattern_key, verdict = sys.argv[2], sys.argv[3], sys.argv[4]
        note = sys.argv[5] if len(sys.argv) > 5 else ""
        description = sys.argv[6] if len(sys.argv) > 6 else ""
        entry = record_feedback(lang, pattern_key, verdict, note, description)
        print(json.dumps(entry, ensure_ascii=False, indent=2))
    elif cmd == "update":
        lang = sys.argv[2]
        data, promotions = recursive_update(lang)
        print(json.dumps({"lang": lang, "promotions": promotions, "patterns": data["patterns"]}, ensure_ascii=False, indent=2))
    elif cmd == "update-all":
        print(json.dumps(update_all_langs(), ensure_ascii=False, indent=2))
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
