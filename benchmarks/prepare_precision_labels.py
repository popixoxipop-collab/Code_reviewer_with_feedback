"""D119 3.1 -- stratified sample of P02 findings for the human labeling sprint.

Re-runs judgment (cheap, local, already-cloned corpus from judgment_4axis_benchmark.py)
across all 39 examples/ repos, pools every finding, and stratified-samples ~50 across
(priority tier x language) so no single tier/language dominates the labeling set.

Writes benchmarks/judgment_precision_labels.jsonl with label fields left null --
2 labelers fill "question_value_label" (true/false: "is this actually a genuine
decision point worth asking about, or a false positive/noise") independently.
Kappa is computed from the filled file, not this one.

Usage: python3 benchmarks/prepare_precision_labels.py [--n 50]
"""
import argparse
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from judgment_4axis_benchmark import discover_corpus, CACHE, run_scan_judge  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "benchmarks" / "judgment_precision_labels.jsonl"

# D119: sampling only, not a scoring decision -- any fixed seed is fine since this
#   just needs to be reproducible run-to-run, not statistically special.
RANDOM_SEED = 20260712


def collect_all_findings(repos):
    pool = []
    for i, repo in enumerate(repos, 1):
        print(f"[labels] [{i}/{len(repos)}] {repo['label']}", file=sys.stderr, flush=True)
        dest = CACHE / repo["label"]
        if not (dest / ".git").exists():
            continue
        r = run_scan_judge(dest)
        if not r["ok"]:
            continue
        for f in r["judgment"]["findings"]:
            pool.append({
                "repo": repo["label"], "lang_tag": repo["lang_tag"],
                "finding_id": f["id"], "file": f.get("file"), "finding_text": f["finding"],
                "priority": f["priority"], "design_intent": f["design_intent"],
                "question_value": f["question_value"], "risk": f["risk"],
            })
    return pool


def stratified_sample(pool, n):
    random.seed(RANDOM_SEED)
    strata = {}
    for item in pool:
        key = (item["lang_tag"], item["priority"])
        strata.setdefault(key, []).append(item)
    for items in strata.values():
        random.shuffle(items)

    sample = []
    keys = sorted(strata.keys())
    idx = 0
    while len(sample) < n and any(strata[k] for k in keys):
        key = keys[idx % len(keys)]
        if strata[key]:
            sample.append(strata[key].pop())
        idx += 1
    return sample


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    args = ap.parse_args()

    repos = discover_corpus()
    print(f"[labels] collecting findings from {len(repos)} repos...", file=sys.stderr)
    pool = collect_all_findings(repos)
    print(f"[labels] {len(pool)} findings total in corpus", file=sys.stderr)

    sample = stratified_sample(pool, args.n)
    print(f"[labels] sampled {len(sample)} for labeling", file=sys.stderr)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for item in sample:
            record = {
                **item,
                "labeler_a_id": None, "labeler_a_label": None, "labeler_a_timestamp": None,
                "labeler_b_id": None, "labeler_b_label": None, "labeler_b_timestamp": None,
                "instructions": (
                    "question_value_label: true/false -- 이 finding을 학생에게 물었을 때 "
                    "실제로 이해도 격차가 드러나는 '진짜 결정 지점'인가(true), 아니면 오탐/관용패턴/"
                    "질문가치 없는 잡음인가(false). finding_text와 file만 보고 판단 -- design_intent/"
                    "question_value/risk 필드(파이프라인 자체 채점 결과)는 라벨링 시 참고하지 말 것"
                    "(순환논증 방지 -- 이 라벨이 그 채점을 검증하는 ground truth가 되어야 함)."
                ),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"[labels] wrote {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
