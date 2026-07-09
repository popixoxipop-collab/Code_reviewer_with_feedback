from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone


REPO = os.path.dirname(os.path.abspath(__file__))
STATUS_PATH = os.path.join(REPO, "docs", "d94-rerun-status.json")
SUMMARY_PATH = os.path.join(REPO, "turn_engine_grading_16models_sonnet_summary.json")
RESULTS_PATH = os.path.join(REPO, "turn_engine_grading_16models_sonnet_results.json")
TARGET_MODELS = [
    "meta/llama-3.3-70b-instruct",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head_short() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
            text=True,
        ).strip()
    except Exception:
        return None


def top_error_summary(model: str, rows: list[dict]) -> str:
    subset = [r for r in rows if r["model"] == model and not r["ok"]]
    if not subset:
        return "none"
    counts = Counter(r.get("error", "unknown error") for r in subset)
    top = []
    for err, n in counts.most_common(2):
        compact = err.replace("\n", " ")
        if len(compact) > 80:
            compact = compact[:77] + "..."
        top.append(f"{n}x {compact}")
    return " | ".join(top)


def build_completed_payload(args) -> dict:
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        summary = json.load(f)
    with open(RESULTS_PATH, encoding="utf-8") as f:
        results = json.load(f)

    models = {}
    for model in TARGET_MODELS:
        row = summary.get(model, {})
        models[model] = {
            "n_ok": row.get("n_ok"),
            "n_total": row.get("n_total"),
            "job_success_rate_pct": (
                f"{row['job_success_rate'] * 100:.1f}%"
                if row.get("job_success_rate") is not None
                else "n/a"
            ),
            "mean_elapsed_s": row.get("mean_elapsed_s"),
            "track_b_precision": row.get("track_b_precision"),
            "self_correction_improving": row.get("self_correction_improving"),
            "self_correction_weak": row.get("self_correction_weak"),
            "top_error_summary": top_error_summary(model, results),
        }

    return {
        "status": "completed",
        "headline": "D94b two-model rerun completed",
        "message": "Low-concurrency rerun finished and the repository JSON artifacts were refreshed.",
        "updated_at": now_iso(),
        "started_at": args.started_at,
        "source_commit": git_head_short(),
        "notes": [
            "llama-3.3-70b-instruct: timeout increase + single-worker run",
            "nvidia/llama-3.3-nemotron-super-49b-v1.5: max_tokens=2048 + single-worker run",
            f"Local log: {args.log_name}" if args.log_name else "Local log: n/a",
        ],
        "models": models,
    }


def build_noncompleted_payload(args) -> dict:
    headline = {
        "pending": "D94b two-model rerun is pending",
        "running": "D94b two-model rerun is in progress",
        "failed": "D94b two-model rerun ended in failure",
    }[args.status]
    message = {
        "pending": "The long-running rerun has not started yet.",
        "running": "A low-concurrency long loop is currently trying to recover the two blocked models.",
        "failed": "The long-running rerun did not complete successfully. See notes for context.",
    }[args.status]
    return {
        "status": args.status,
        "headline": headline,
        "message": message,
        "updated_at": now_iso(),
        "started_at": args.started_at,
        "source_commit": git_head_short(),
        "notes": args.note,
        "models": {},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", choices=["pending", "running", "completed", "failed"], required=True)
    parser.add_argument("--started-at", default=None)
    parser.add_argument("--log-name", default="")
    parser.add_argument("--note", action="append", default=[])
    args = parser.parse_args()

    payload = build_completed_payload(args) if args.status == "completed" else build_noncompleted_payload(args)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"wrote {STATUS_PATH}")


if __name__ == "__main__":
    main()
