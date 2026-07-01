import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import load_entries, normalize_repo  # noqa: E402

# D24: "방법론간 비교표"는 ledger.jsonl을 그때그때 집계해서 만든다(별도 캐시/DB 없음)
#   WHY: 원장 자체가 이미 append-only 진실 소스라 재계산 비용이 무시할 만큼 작음(수백~수천
#        줄 수준). 집계 로직과 저장 로직을 분리해두면 집계 기준이 바뀌어도 원장은 안 건드림
#   COST: 원장이 아주 커지면(수만 줄) 매번 전체를 읽어 느려질 수 있음
#   EXIT: 느려지면 groupby 결과를 별도 캐시 파일로 저장하고 원장 변경 시에만 재계산


def aggregate(entries):
    groups = {}
    for e in entries:
        key = (e["methodology"], e["key"])
        g = groups.setdefault(key, {"repos": set(), "runs": 0, "changed_total": 0, "examples": []})
        g["repos"].add(normalize_repo(e["repo"]))
        g["runs"] += 1
        g["changed_total"] += e["findings_changed"]
        if e["changed"]:
            g["examples"].append((normalize_repo(e["repo"]), e["changed"][0], e["timestamp"]))
    return groups


def render(groups):
    lines = [
        "# 방법론간 비교표 (ledger.jsonl 누적 집계)",
        "",
        "| 방법론 | 키(pattern_key/trigger) | 적용 repo 수 | 총 주입 횟수 | 변경된 finding 누적 | 최근 예시 |",
        "|---|---|---|---|---|---|",
    ]
    for (methodology, key), g in sorted(groups.items()):
        example = "—"
        if g["examples"]:
            repo, change, ts = sorted(g["examples"], key=lambda x: x[2])[-1]
            example = f"`{repo}`: `{change['id']}` {change['before']}→{change['after']}"
        lines.append(
            f"| {methodology} | `{key}` | {len(g['repos'])} | {g['runs']} | {g['changed_total']} | {example} |"
        )
    return "\n".join(lines)


def main():
    entries = load_entries()
    if not entries:
        print("ledger.jsonl이 비어있음 — run_pipeline.py를 먼저 실행해 데이터를 쌓아야 함", file=sys.stderr)
        sys.exit(1)
    print(render(aggregate(entries)))
    print(f"\n(원본 이벤트 {len(entries)}건 기준, `pipeline/ledger.jsonl` 참고)")


if __name__ == "__main__":
    main()
