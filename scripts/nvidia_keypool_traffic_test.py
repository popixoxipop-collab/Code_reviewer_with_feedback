#!/usr/bin/env python3
"""Local sliding-window traffic test for NVIDIA_API_KEY_1..N rotation.

This does not call NVIDIA Build. It exercises the same key-pool acquire path
used by scripts/java_curriculum_nvidia_pipeline.py and proves the theoretical
capacity boundary:

- 7 keys x 40 requests/minute/model = 280 immediate reservations
- the 281st reservation in the same 60s window is blocked
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PIPELINE = REPO / "scripts" / "java_curriculum_nvidia_pipeline.py"


def load_pipeline_module():
    spec = importlib.util.spec_from_file_location("java_curriculum_nvidia_pipeline", PIPELINE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {PIPELINE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keys", type=int, default=7)
    parser.add_argument("--capacity-per-minute", type=int, default=40)
    parser.add_argument("--model", default="traffic-test/model")
    parser.add_argument("--out", default="docs/java_curriculum_pipeline_rate_smoke/keypool_traffic_test.json")
    args = parser.parse_args()

    pipe = load_pipeline_module()
    pool = pipe.CountingNvidiaKeyPool(
        [f"dummy-key-{i}" for i in range(args.keys)],
        capacity_per_minute=args.capacity_per_minute,
    )
    theoretical = args.keys * args.capacity_per_minute

    acquired = 0
    for _ in range(theoretical):
        pool.acquire(args.model, max_wait_s=0.001)
        acquired += 1

    blocked = False
    blocked_error = None
    try:
        pool.acquire(args.model, max_wait_s=0.001)
    except Exception as exc:  # noqa: BLE001 - exact type comes from vendored key pool.
        blocked = True
        blocked_error = f"{type(exc).__name__}: {exc}"

    audit = pipe.build_rate_audit(pool.acquire_events, args.capacity_per_minute, args.keys)
    result = {
        "keys": args.keys,
        "capacity_per_minute": args.capacity_per_minute,
        "theoretical_capacity_per_model_per_60s": theoretical,
        "acquired_without_wait": acquired,
        "extra_request_blocked": blocked,
        "extra_request_error": blocked_error,
        "rate_audit": audit,
        "pass": acquired == theoretical and blocked and audit["within_policy"],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
