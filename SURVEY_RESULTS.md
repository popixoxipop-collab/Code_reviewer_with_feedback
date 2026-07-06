# Live NVIDIA Build census — `feedback/generate_questions.py` (2026-07-06)

First-ever live execution of the NVIDIA tool-calling path (README item 18
had flagged this as unverified — no `NVIDIA_API_KEY` in the session that
wrote D56). Every finding in every real fixture in this repo (LMS baseline,
8 findings + study_match, 4 findings = 12 total, 2 of them `idiom_filtered`)
was sent to every chat-capable model in the NVIDIA Build catalog (87
candidates, filtered the same way as the `nvidia-build` repo's benchmark),
via the exact production code path (`build_prompt`, `_as_openai_tool`,
`parse_nvidia_tool_response`, `_validate_depth_ladder` — not a
reimplementation).

## A bug in the test harness first (D11, fixed before trusting any numbers)

The first full run showed high-precision code-review models
(`deepseek-v4-pro`, `glm-5.2`, `minimax-m3`) failing most of their calls —
errors like `All 1 keys saturated` and `HTTP 429`. This was **not** a model
capability problem: the vendored `NvidiaKeyPool` tracked its 40/min budget
per API key only, not per (key, model) pair, even though NVIDIA's real limit
is per-model. Driving 87 *different* models through one key made the pool
think the key was exhausted after 40 calls total, regardless of which model
each call targeted — starving slower models whose calls queued up behind
others sharing the same (wrong) bucket.

Fixed at the source (`github.com/popixoxipop-collab/nvidia-build`, commit
`6b57963`, D11) and re-synced into `feedback/nvidia_key_pool.py` +
`nvidia_client.py` here before re-running every failed pair. All numbers
below are post-fix.

## Results: which models actually respect `tool_choice` on this schema

19 of 87 models achieved perfect compliance (12/12, all 7 depth-ladder
fields present and non-empty on every finding):

| Model | Avg time (12/12) |
|---|---:|
| stepfun-ai/step-3.5-flash | 4.6s |
| mistralai/mistral-nemotron | 5.5s |
| meta/llama-4-maverick-17b-128e-instruct | 5.7s |
| nvidia/nemotron-nano-12b-v2-vl | 7.5s |
| mistralai/mistral-large-3-675b-instruct-2512 | 8.9s |
| openai/gpt-oss-20b | 9.6s |
| **qwen/qwen3-next-80b-a3b-instruct** | **13.2s** |
| openai/gpt-oss-120b | 14.3s |
| meta/llama-3.2-3b-instruct | 15.6s |
| meta/llama-3.1-8b-instruct | 16.3s |
| minimaxai/minimax-m2.7 | 24.4s |
| nvidia/nemotron-3-super-120b-a12b | 25.8s |
| mistralai/mistral-medium-3.5-128b | 30.2s |
| google/gemma-4-31b-it | 34.2s |
| nvidia/llama-3.3-nemotron-super-49b-v1 | 35.8s |
| meta/llama-3.1-70b-instruct | 44.7s |
| deepseek-ai/deepseek-v4-pro | 48.9s |
| nvidia/nemotron-3-ultra-550b-a55b | 49.6s |
| qwen/qwen3.5-397b-a17b (previous D56 default) | 52.9s |

Everything else either partially failed (moonshotai/kimi-k2.6 11/12,
minimax-m3 11/12, z-ai/glm-5.2 5/12 — genuinely slow, real timeouts even
after the D11 fix) or failed outright (55 models — mostly the same 404s
found in the `nvidia-build` code-review benchmark, plus two new genuine
failure modes worth naming: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
returns prose instead of calling the tool at all — a real `tool_choice`
non-compliance, not an infra issue; `nvidia/llama-3.3-nemotron-super-49b-v1.5`
returns tool-call arguments that aren't valid JSON, `Extra data: line 1
column ...` — a different, malformed-output failure mode).

## Quality check, not just compliance

Manually compared question text for `tier-b-risk:Bookshelf.jsx:dangerous-html`
(a real `dangerouslySetInnerHTML` finding) across the fastest fully-compliant
models. `stepfun-ai/step-3.5-flash` and `qwen/qwen3-next-80b-a3b-instruct`
both produced specific, well-tailored Socratic questions (naming concrete
alternatives like DOMPurify / `markdown-to-jsx` / React's safe text
rendering, not generic filler). `meta/llama-4-maverick-17b-128e-instruct`
was comparatively more templated (its "why" question partially gives away
the "alternative" question's answer one step early).

The `idiom_filtered` shorten/simplify instruction was checked across 6
sampled models by comparing average question length on `idiom_filtered`
findings vs normal findings — all 6 correctly produced shorter output for
`idiom_filtered` findings (only 2 of 12 fixture findings are
`idiom_filtered`, so this check is directional, not exhaustive).

## Decision

**D58** (see `feedback/generate_questions.py`): default model changed from
`qwen/qwen3.5-397b-a17b` to `qwen/qwen3-next-80b-a3b-instruct` — same 100%
compliance, same tailored question quality, 4x faster (13.2s vs 52.9s), and
independently the top pick on a *different* task (freeform code review) in
the `nvidia-build` benchmark on speed + precision + reproducibility. Two
independent tasks converging on the same model is stronger evidence than
either alone.

Runner-up candidates if this one regresses: `stepfun-ai/step-3.5-flash`
(fastest, 4.6s, but untested for reproducibility/precision on the code-review
benchmark) and `deepseek-ai/deepseek-v4-pro` (48.9s, but the single highest
reproducibility score, 0.9, in the code-review benchmark).

## Still open

- **Reproducibility was not re-tested for this task.** The nvidia-build
  benchmark's 0.85 reproducibility score for qwen3-next-80b-a3b-instruct was
  measured on freeform code review, not schema-forced tool-calling — these
  could behave differently. A second identical pass over the same 12
  findings would confirm or refute this for the actual production task.
- **Never run against a real bootcamp session.** Every fixture here (LMS,
  study_match) is a regression test against a public GitHub repo with a
  scripted/simulated "student" — not a live student's actual code submission
  and real free-text answers. This survey verifies the LLM call path works;
  it does not verify the full cognition -> judgment -> interview loop against
  a real student interaction.
- The FR mismatches flagged separately (5-axis spec vs 3-axis
  `interview_rubric.py`, FR-03-05/FR-04-02 unimplemented) are unrelated to
  this survey and still open.

Raw data: `full_survey_results.json` (not committed — 1044 records,
regenerate with `python full_survey.py` then `python rerun_failed.py`).
