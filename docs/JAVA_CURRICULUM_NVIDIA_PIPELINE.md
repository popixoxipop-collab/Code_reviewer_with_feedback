# Java Curriculum NVIDIA Pipeline

This document records the implemented pipeline for page-grounded Java curriculum analysis with NVIDIA Build key rotation.

## Pipeline

1. `AI_JAVA_교안.pdf` is read with `pdftotext` in 10-page chunks.
2. Each chunk is submitted as an independent NVIDIA Build chat request through `NvidiaRotatingClient`.
3. `CountingNvidiaKeyPool` rotates across `NVIDIA_API_KEY_1..N` while enforcing the same per-model sliding-window budget as `feedback/nvidia_key_pool.py`.
4. Chunk responses preserve page provenance as `source_pages` on each unit, concept, code example, and caution.
5. A refine loop audits page coverage, duplicate concepts, unit boundaries, and graph readiness.
6. A graphify-compatible `graphify-out/graph.json` is built with document, unit, concept, page, refine-issue, and diagnostic-question nodes.
7. Diagnostic questions are generated from graph nodes and must cite both `source_node_ids` and concrete `source_pages`.

## Implementation

- Pipeline script: `scripts/java_curriculum_nvidia_pipeline.py`
- Rate traffic test: `scripts/nvidia_keypool_traffic_test.py`
- Successful 3-chunk live NVIDIA smoke output: `docs/java_curriculum_pipeline_run_smoke/`
- Rate audit smoke output: `docs/java_curriculum_pipeline_rate_smoke/`

## Rate-Limit Verification

NVIDIA Build's documented working assumption in this repo is 40 requests/minute per `(key, model)` pair. With `NVIDIA_API_KEY_1..7`, the theoretical aggregate ceiling is:

```text
40 requests/min/key/model * 7 keys = 280 requests/min/model
```

The local sliding-window traffic test exercises the same key-pool `acquire()` path without sending 280 real requests to NVIDIA:

```bash
python3 scripts/nvidia_keypool_traffic_test.py
```

Result:

- `acquired_without_wait`: `280`
- `extra_request_blocked`: `true`
- aggregate max in any 60s window: `280 / 280`
- each key slot max in any 60s window: `40 / 40`
- `pass`: `true`

Raw result: `docs/java_curriculum_pipeline_rate_smoke/keypool_traffic_test.json`.

## Live NVIDIA Smoke

The successful smoke run used the real NVIDIA Build API on the first 3 chunks:

```bash
python3 scripts/java_curriculum_nvidia_pipeline.py \
  --pdf-password aivle202609 \
  --max-chunks 3 \
  --max-workers 2 \
  --refine-iters 1 \
  --timeout-s 240 \
  --capacity-per-minute 20 \
  --out-dir docs/java_curriculum_pipeline_run_smoke
```

Observed:

- chunks processed: `3`
- successful chunks: `3`
- units: `2`
- concepts/code/cautions: `35`
- graph nodes: `65`
- graph links: `108`
- generated questions: `4`
- key slots used: `NVIDIA_API_KEY_1..5`
- rate policy respected: true for the later rate-audited smoke; the successful 3-chunk smoke predated the `rate_audit.json` writer but used the same key-pool acquire path.

Report: `docs/java_curriculum_pipeline_run_smoke/RUN_REPORT.md`.

## Full-Run Note

The full 251-page run was attempted with higher concurrency. It exposed NVIDIA model/server availability constraints rather than a key-pool limit:

- `qwen/qwen3-next-80b-a3b-instruct` completed most chunk calls at low concurrency, but failed before final write on malformed JSON in one refine pass. The script now preserves refine failures as audit state instead of aborting.
- `max_workers=8` and `max_workers=5` runs hit NVIDIA-side timeout/gateway-timeout behavior for the first wave, even though the local key-pool budget was below `40*7/min`.
- `stepfun-ai/step-3.5-flash` is fast in prior repo benchmarks, but in this JSON extraction prompt returned empty content with `finish_reason=length`, so it was not used for final curriculum extraction.

Conclusion: the implemented traffic gate can reach the theoretical 280 RPM local reservation ceiling and blocks the 281st request. Real full-document throughput is currently bounded by model/server latency and JSON-response reliability, not by local key rotation capacity.
