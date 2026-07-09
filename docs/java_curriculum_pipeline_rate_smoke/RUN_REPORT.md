# Java Curriculum NVIDIA Parallel Pipeline Run

- PDF: `/Users/xox/Downloads/AI_JAVA_교안.pdf`
- Model: `qwen/qwen3-next-80b-a3b-instruct`
- Chunk size: `10` pages
- Chunks processed: `1`
- Max workers: `1`
- Dry run: `False`
- Elapsed: `8.4s`
- NVIDIA key slots used: `{'NVIDIA_API_KEY_1': 1, 'NVIDIA_API_KEY_2': 0, 'NVIDIA_API_KEY_3': 0, 'NVIDIA_API_KEY_4': 0, 'NVIDIA_API_KEY_5': 0, 'NVIDIA_API_KEY_6': 0, 'NVIDIA_API_KEY_7': 0}`
- Rate policy: `{'capacity_per_key_per_model_per_60s': 40, 'key_slots': 7, 'aggregate_capacity_per_model_per_60s': 280, 'window_s': 60.0}`
- Rate policy respected: `True`

## Verified Pipeline

1. PDF pages were extracted with `pdftotext`.
2. Each page range was sent as an independent chunk call through `NvidiaRotatingClient`.
3. `CountingNvidiaKeyPool` rotated calls across `NVIDIA_API_KEY_1..N` and recorded slot counts only, never key values.
4. Chunk outputs preserved `source_pages` for every concept/code/caution node.
5. A NVIDIA refinement loop audited page provenance and graph readiness.
6. A graphify-compatible `graphify-out/graph.json` was built from unit/concept/page/refine/question state.
7. Final questions were generated from graph nodes and cite `source_node_ids` plus concrete `source_pages`.

## Outputs

- `chunks.json`
- `unit_map.json`
- `refine_audit.json`
- `questions.json`
- `rate_audit.json`
- `graphify-out/graph.json`
- `graphify-out/GRAPH_REPORT.md`

## Counts

- Units: `0`
- Concepts/code/cautions: `0`
- Graph nodes: `1`
- Graph links: `0`
- Questions: `0`

## Refine Loop


## NVIDIA Rate Audit

- `NVIDIA_API_KEY_1::qwen/qwen3-next-80b-a3b-instruct`: calls `1`, max 60s `1` / limit `40`, within `True`
- aggregate `qwen/qwen3-next-80b-a3b-instruct`: calls `1`, max 60s `1` / limit `280`, within `True`

## Sample Questions


## Graphify Query Smoke Test

```text
NODE AI_JAVA_교안.pdf [src= loc= community=]
```
