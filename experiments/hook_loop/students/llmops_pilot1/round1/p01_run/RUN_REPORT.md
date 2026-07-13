# LLMOps Curriculum NVIDIA Parallel Pipeline Run

- PDF: `/Users/xox/Downloads/AI_LLMOps_교안.pdf`
- Model: `qwen/qwen3-next-80b-a3b-instruct`
- Chunk size: `10` pages
- Chunks processed: `16`
- Max workers: `3`
- Dry run: `False`
- Elapsed: `343.6s`
- NVIDIA key slots used: `{'NVIDIA_API_KEY_1': 3, 'NVIDIA_API_KEY_2': 3, 'NVIDIA_API_KEY_3': 3, 'NVIDIA_API_KEY_4': 3, 'NVIDIA_API_KEY_5': 3, 'NVIDIA_API_KEY_6': 3, 'NVIDIA_API_KEY_7': 3}`
- Rate policy: `{'capacity_per_key_per_model_per_60s': 20, 'key_slots': 7, 'aggregate_capacity_per_model_per_60s': 140, 'window_s': 60.0}`
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

- Units: `6`
- Concepts/code/cautions: `342`
- Graph nodes: `493`
- Graph links: `856`
- Questions: `3`

## Refine Loop

- Iteration `1`: `needs_refine` — Refine call failed but preserved as audit state: ValueError: JSON parse failed (Expecting ',' delimiter: line 53 column 6 (char 3849)); repair failed (Expecting ',' delimiter: line 184 column 6 (char 4897)); raw_head='{\n  "iteration": 1,\n  "status": "needs_refine",\n  "coverage_summary": "Unit map covers core LLMOps concepts but has severe page provenance issues, duplicate concepts, and missing concrete page mappings for key topics.",\n  "issues": [\n    {\n      "severity": "high",\n      "issue": "Unit \'Overview\' (unit_id: 01) claims coverage of 80+ pages but contains no concepts derived from most of them; pages are overbroad and not tied to specific concepts.",\n      "source_pages": [1, 2, 3, 4, 5, 6, 11, 12, 1'
- Iteration `2`: `needs_refine` — Extensive concept coverage with strong page provenance, but severe duplication, inconsistent granularity, and missing page alignment for core unit concepts.

## NVIDIA Rate Audit

- `NVIDIA_API_KEY_1::qwen/qwen3-next-80b-a3b-instruct`: calls `3`, max 60s `1` / limit `20`, within `True`
- `NVIDIA_API_KEY_2::qwen/qwen3-next-80b-a3b-instruct`: calls `3`, max 60s `1` / limit `20`, within `True`
- `NVIDIA_API_KEY_3::qwen/qwen3-next-80b-a3b-instruct`: calls `3`, max 60s `1` / limit `20`, within `True`
- `NVIDIA_API_KEY_4::qwen/qwen3-next-80b-a3b-instruct`: calls `2`, max 60s `1` / limit `20`, within `True`
- `NVIDIA_API_KEY_5::qwen/qwen3-next-80b-a3b-instruct`: calls `2`, max 60s `1` / limit `20`, within `True`
- `NVIDIA_API_KEY_6::qwen/qwen3-next-80b-a3b-instruct`: calls `2`, max 60s `1` / limit `20`, within `True`
- `NVIDIA_API_KEY_7::qwen/qwen3-next-80b-a3b-instruct`: calls `2`, max 60s `1` / limit `20`, within `True`
- aggregate `qwen/qwen3-next-80b-a3b-instruct`: calls `17`, max 60s `7` / limit `140`, within `True`

## Sample Questions

- Unit 01: In a Supervisor-pattern agent system, why is it insufficient to rely solely on a Critic agent for decision-making and error correction, and how does integrating HITL improve control over cost and reliability? Cite specific design components and their source pages. (pages: [39, 41, 46, 48, 49, 43, 45])
- Unit 01: A team deploys an AI Interview Agent that uses LLM-as-Judge for evaluating answers. After deployment, they observe high variance in evaluation scores despite identical inputs. Explain why this occurs and propose two concrete design changes to improve evaluation consistency, citing relevant concepts and source pages. (pages: [61, 96, 111, 112, 114])
- Unit 01: Compare the use of Snapshots versus Traces for debugging a failed multi-agent workflow. When would you prefer one over the other, and what specific information does each provide that the other lacks? Support your answer with source node references and page numbers. (pages: [62, 63, 69, 91, 93])

## Graphify Query Smoke Test

```text
NODE Unit 02 LLMOps 개념 이해 [src= loc= community=]
NODE p121 [src= loc= community=]
NODE p35 [src= loc= community=]
NODE p11 [src= loc= community=]
NODE p10 [src= loc= community=]
NODE p34 [src= loc= community=]
NODE p26 [src= loc= community=]
NODE p24 [src= loc= community=]
NODE p124 [src= loc= community=]
NODE p91 [src= loc= community=]
NODE p93 [src= loc= community=]
NODE p20 [src= loc= community=]
NODE p31 [src= loc= community=]
NODE p131 [src= loc= community=]
NODE p30 [src= loc= community=]
NODE p32 [src= loc= community=]
NODE p21 [src= loc= community=]
NODE p29 [src= loc= community=]
NODE p27 [src= loc= community=]
NODE p23 [src= loc= community=]
NODE p126 [src= loc= community=]
NODE p25 [src= loc= community=]
NODE p28 [src= loc= community=]
NODE p39 [src= loc= community=]
NODE p9 [src= loc= community=]
NODE State Management [src= loc= community=]
NODE p97 [src= loc= community=]
NODE p134 [src= loc= community=]
NODE p138 [src= loc= community=]
NODE p136 [src= loc= community=]
NODE p37 [src= loc= community=]
NODE p139 [src= loc= community=]
NODE p72 [src= loc= community=]
NODE p74 [src= loc= community=]
NODE p92 [src= loc= community=]
NODE p38 [src= loc= community=]
NODE Role-Based Separation [src= loc= community=]
NODE Operational Use Cases [src= loc= community=]
NODE Reproducibility Difference [src= loc= community=]
NODE Snapshot vs Trace [src= loc= community=]
NODE p122 [src= loc= community=]
NODE p127 [src= loc= community=]
NODE Network Pattern Lab [src= loc= community=]
NODE p96 [src= loc= community=]
NODE LangSmith Purpose [src= loc= community=]
NODE LangSmith [src= loc= community=]
NODE API Key Setup [src= loc= community=]
NODE Prompt Specification [src= loc= community=]
NODE AI Document Analysis Agent [src= loc= community=]
NODE p5 [src= loc= community=]
NODE p8 [src= loc= community=]
NODE Multi-Agent Analysis Focus [src= loc= community=]
NODE Technical Debt [src= loc= community=]
NODE p19 [src= loc= community=]
NODE p130 [src= loc= community=]
NODE LLMOps Cycle [src= loc= community=]
NODE POC Scope: Contract Analysis [src= loc= community=]
NODE State Definition [src= loc= community=]
NODE Decision Policy [src= loc= community=]
NODE Design Documentation for AI Agents [src= loc= community=]
NODE Supervisor Pattern [src= loc= community=]
NODE Snapshot [src= loc= community=]
NODE Prompt Specification [src= loc= community=]
NODE Decision Policy [src=
... (truncated to ~800 token budget)
```
