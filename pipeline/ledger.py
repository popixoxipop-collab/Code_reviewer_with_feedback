import json
import os
from datetime import datetime, timezone

# D23: 파이프라인 실행 결과를 append-only 원장(ledger.jsonl)에 영구 저장
#   WHY: run_pipeline.py는 실행 1회의 비교표만 stdout/파일로 뽑고 끝 — "지금까지 시도한
#        방법론들을 비교해서 보여달라"는 질문에 답할 축적된 데이터가 없었음(2026-07-01 실측
#        확인). 매 주입마다 결과를 한 줄씩 append하면 나중에 언제든 집계 가능
#   COST: 같은 methodology를 여러 repo/여러 번 실행하면 로그가 계속 늘어남(무한정 append) —
#        정리(retention) 정책 없음
#   EXIT: 파일이 너무 커지면 SQLite로 교체(스키마는 그대로, append_entry/load_entries 인터페이스만 유지)

LEDGER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger.jsonl")


# D25: repo 식별자를 원본 경로가 아니라 정규화된 이름으로 집계
#   WHY: 실측 발견 — 같은 저장소를 "Study-Match-/src"(backfill)와 "repo_candidates/Study-Match-/src"
#        (실제 cwd 기준 실행)처럼 실행 위치에 따라 다른 상대경로로 기록해, 집계에서 "적용 repo 수"가
#        1이어야 할 게 2로 잘못 카운트됨
#   COST: 서로 다른 두 repo가 우연히 같은 마지막 세그먼트 이름을 가지면 하나로 합쳐질 위험(드묾)
#   EXIT: 정말 정확한 식별이 필요해지면 원격 git URL(`git remote get-url origin`)을 저장하는 방식으로 교체
def normalize_repo(path):
    p = path.rstrip("/")
    if os.path.basename(p) in ("src", "lib", "app"):
        p = os.path.dirname(p)
    return os.path.basename(p.rstrip("/")) or p


def append_entry(entry, ledger_path=LEDGER_PATH):
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_entries(ledger_path=LEDGER_PATH):
    if not os.path.exists(ledger_path):
        return []
    entries = []
    with open(ledger_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def build_entry(repo, injection, before_snap, after_snap):
    changed = [
        {"id": fid, "before": before_snap.get(fid, "(없음)"), "after": after_snap.get(fid, "(제거됨)")}
        for fid in sorted(set(before_snap) | set(after_snap))
        if before_snap.get(fid) != after_snap.get(fid)
    ]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo": repo,
        "methodology": injection["type"],
        "key": injection.get("pattern_key") or injection.get("trigger"),
        "label": injection.get("label", injection["type"]),
        "note": injection.get("note", ""),
        "findings_total": len(after_snap),
        "findings_changed": len(changed),
        "changed": changed,
    }
