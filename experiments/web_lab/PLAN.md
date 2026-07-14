# Implementation Plan — Team Pipeline Lab (GitHub Pages 파이프라인 테스트 도구)

> **상태: 계획 단계, 사용자 승인 대기 — 구현 시작 전.** Fable 모델(Agent, `subagent_type: Plan`)이 작성.
> 사용자 지시: "github.io로 실제로 다른 팀원들이 각 파이프라인을 점검하고 내 DB에 정보를 쌓도록 인터페이스 제작... api키는 각자 입력... 3가지 파이프라인 각각에 대해 어떤 프롬프트를 주입하는지 각 플로우 단계별로 개입 가능하도록 편집 가능한 형태"

A static web tool at `docs/lab/` on the existing GitHub Pages site where team members pick P01/P02/P03, see each pipeline's stages, edit the exact prompt (or, for P02, the exact parameters) injected at each stage, run it with their own NVIDIA API key, and have every run recorded with attribution in the owner's hosted database.

## 0. Ground truth (verified by reading source, not assumed)

**P01 — `scripts/java_curriculum_nvidia_pipeline.py`.** Three LLM prompt sites plus one hidden shared prompt:

| Stage | Function (lines) | System prompt | User-template variables |
|---|---|---|---|
| Chunk analysis | `analyse_chunk()` 286–329 | "You are a precise curriculum-analysis extractor. Output strict JSON only." | `course_label`, `chunk.range`, `chunk.start`, `chunk.end`, `chunk.text[:18000]` |
| Refine loop | `refine_once()` 401–448 | "You are a strict graph/refinement auditor. Output strict JSON only." | `course_label`, `iteration`, `unit_map` JSON `[:24000]` |
| Question gen | `generate_questions()` 510–564 | "You design graph-grounded diagnostic questions. Output strict JSON only." | `course_label`, compact graph nodes JSON `[:24000]` |
| (hidden, shared) | JSON-repair prompt inside `chat_json()` 250–270 | "You repair malformed JSON. Output strict JSON only." | malformed content `[:14000]` |

All calls: `temperature=0.0`, `response_format={"type":"json_object"}`. Non-LLM stages: PDF extraction shells out to `pdfinfo`/`pdftotext -layout` (166–189 — cannot run in a browser). `make_unit_map()`, `build_graph()`, `attach_questions_to_graph()` are pure dict transforms. `course_label` (D131) is the existing prior art for per-stage prompt parameterization. Tunables already exposed as CLI args: `chunk_size=10`, `max_chunks`, `refine_iters=2`, `max_workers=3`, `max_tokens_{chunk,refine,questions}`, `capacity_per_minute`.

**P02 — `cognition/two_tier_scan.py` + `judgment/score_findings.py`.** Zero LLM calls, confirmed line by line — there is no prompt anywhere in this pipeline. The UI for P02 must therefore be a **parameter/threshold editor, not a prompt editor**, and must say so explicitly. Actual editable constants found:

- `two_tier_scan.py`: `SRC_EXTS`, `SKIP_DIRS`, `LOCAL_IMPORT_PREFIXES` (line 101), risk regexes `AUTH_KEYWORDS`, `STRINGIFY_RE`, `THROW_RE`, `EVAL_RE`, `SECRET_RE` (62–81), per-language import regexes (57–60).
- `score_findings.py`: `ENTRY_POINT_HINTS` (39), `REPEATED_PATTERN_MIN_FILES=2` / `REPEATED_PATTERN_MIN_HITS=2` (60–61), `DUPLICATE_DEFINITION_MIN_NAME_LEN=5` (90), `DEFINITION_RE_BY_EXT` (80–87), the repeated-pattern string dict `{"onSnapshot": …}` (420), diffusion threshold `v >= 2` (191).
- Data-file-driven behavior: `judgment/isolation_categories/*/patterns.json`, `judgment/tier_b_suppressions/suppressions.json`, `judgment/subrubric_weights/*/weights.json`, idiom patterns — all in-repo JSON.

**P03 — `feedback/turn_engine.py` + `feedback/llm_interview_grader.py` + `feedback/interview_rubric.py`.** Two LLM call sites, five editable text blocks plus the rubric:

- Question generation: `_build_level_prompt()` (turn_engine 133–178) = one shared header + four level-specific blocks (`l1`, `l2`, `l3`, `reflection`), Korean. Variables: `finding.finding`, `finding.file`, `code_context` (capped `MAX_FILE_CHARS=4000`), transcript, `verdict_note`. Forced tool call `SINGLE_QUESTION_TOOL`, `temperature=0.0`, `max_tokens=DEFAULT_MAX_TOKENS` (2048, `timeout_config.py`, D104).
- Answer classification between turns is **deterministic regex** (`classify_answer()` → `isolation_classifier.classify_justification` / `reflection_signal.evaluate_reflection` + pattern JSONs), not an LLM — the swimlane's "표면/부분/방어 분류" stage is parameter-flavored, like P02.
- Grading: `build_grading_prompt()` (grader 104–116) = editable preamble + `_rubric_block()` rendered from `interview_rubric.RUBRIC` (5 axes × 5 hardcoded Korean level texts) + `GRADING_TOOL` schema (5 axes × {score, evidence}, FR-04-01 names).
- Personas (`experiments/hook_loop/_lab/personas/*.txt`): instruction text + `{context}`/`{question}` placeholders — AI-answerer mode, v2.

**Hook File** (`hookfile/generate_hook_file.py`, `audit_checklist.py`): out of scope for v1 per the user; its D123 temporal-firewall invariant (never inject into question-gen/grading) is respected and noted as the natural v2 extension.

**Empirical constraint checks run today (2026-07-14):**
1. `OPTIONS https://integrate.api.nvidia.com/v1/chat/completions` with a Pages `Origin` returns 200 with **no `Access-Control-Allow-Origin` header** → browsers WILL block direct frontend→NVIDIA calls. A proxy is not optional; it is forced.
2. `raw.githubusercontent.com` and `api.github.com` both return `access-control-allow-origin: *` → the browser CAN fetch this repo's pipeline source files and public repos-to-scan directly.

---

## 1. Architecture (resolving the static-hosting constraint)

**Chosen: Option A — static GitHub Pages frontend that executes pipelines client-side, plus exactly two thin cloud pieces: (1) Supabase (Postgres + Auth + Row-Level Security) as "my DB", (2) a ~30-line CORS pass-through proxy for NVIDIA calls.** Deterministic pipeline logic runs as the *original, unmodified Python files* in-browser via Pyodide (WASM); LLM-calling orchestration is reimplemented in JS from a prompt manifest.

Compared options:

- **Option B — real Python backend (Render/Fly/HF Space) running the scripts as jobs.** Highest fidelity (includes `pdftotext`), but the owner then operates a server that receives every teammate's API key AND executes long flaky jobs (P01 full-run is already marked "실험적 · 부분 차단" in the swimlane, D95); cold starts, concurrency, and cost land on the owner; GitHub Pages reduces to a shell. Rejected for v1; it is the EXIT path if client-side fidelity proves insufficient.
- **Option C — GitHub Actions as executor** (workflow_dispatch, results committed back). Rejected outright: P03 is an *interactive* 4-turn human interview — a batch job model cannot hold a conversation; also per-member secrets don't fit Actions, and dispatch inputs leak into logs.
- **P03 interactivity is the decisive argument for client-side orchestration**: `run_decision_point()`'s `answer_fn` seam (turn_engine 216) maps naturally onto "human types answer in the browser between turns."

### Data flow (text diagram)

```
                    GitHub Pages (docs/lab/, static)
                    ├─ prompt_manifest.json (default templates+params, versioned)
                    ├─ app JS (orchestration, editors, run recorder)
                    └─ Pyodide (WASM Python)
                         ▲ fetch .py + patterns.json (CORS: * verified)
                         │
              raw.githubusercontent.com  ← the repo's own pipeline source at HEAD

P02 run:  teammate browser ──(folder upload or api.github.com fetch)── target repo files
          → Pyodide: two_tier_scan.scan() + score_findings.score()   [original code,
             constants overridden from the param editor via a tiny driver shim]
          → findings JSON → supabase-js INSERT (runs, stage_events, artifacts)

P03 run:  finding (from a stored P02 run, pasted JSON, or bundled example)
          → JS renders L1 template → proxy → NVIDIA → question
          → human answers in UI → Pyodide: classify_answer() [original regex code]
          → defended? stop : next level template (L2→L3→reflection, max 4 turns)
          → per-turn grading: grading template + rubric block → proxy → NVIDIA
          → transcript + 5-axis grades → Supabase

P01 run:  PDF file input → pdf.js text extraction per page → chunks
          → per-chunk analyse template → proxy → NVIDIA (client-side rate-limited)
          → Pyodide: make_unit_map() → refine template ×N → build_graph()
          → questions template → attach_questions_to_graph() → Supabase

LLM path: browser ──HTTPS, key in header──► owner's proxy (Cloudflare Worker or
          Supabase Edge Function; source published in repo; adds CORS; never
          stores/logs the key) ──► integrate.api.nvidia.com/v1/chat/completions

DB path:  browser ──supabase-js (anon key + user JWT)──► Supabase Postgres
          RLS: authenticated team members only; INSERT with member_id = auth.uid()
Owner:    Supabase dashboard / SQL + an "all runs" review page in the tool
```

### Fidelity strategy — why Pyodide for the deterministic parts

Porting P02 faithfully means re-implementing ~1,500 lines of tuned regex logic across 6+ modules (`two_tier_scan`, `score_findings`, `idiom_filter`, `subrubric`, `tier_b_suppression_filter`, hooks) — every D12/D17/D18/D122-style fix would have to be duplicated and would silently drift. Instead: all these modules are pure stdlib (`re/os/json/sys` — verified imports across all of them), so Pyodide runs them **unchanged**, fetched from `raw.githubusercontent.com` at runtime (always matching repo HEAD, zero drift), with target-repo files and pattern JSONs written into Pyodide's virtual FS. A new tiny driver (`webtool` shim, the only new Python) applies UI parameter overrides by setting module attributes (`two_tier_scan.SECRET_RE = re.compile(...)` etc.) before calling `scan()`/`score()` — original files untouched. The same Pyodide instance runs P03's `classify_answer()` chain and P01's `make_unit_map`/`build_graph` transforms. LLM-calling functions are NOT run in Pyodide (no sockets; and GitHub Pages can't set the COOP/COEP headers a sync JS↔Python bridge would need) — that's why the loops around them are JS.

**P01 caveat flagged now:** browser PDF extraction uses pdf.js, not `pdftotext -layout`; whitespace/layout differences mean web-tool P01 runs are not byte-comparable with CLI runs. Every run records `extractor: "pdfjs"`, and the UI offers "pre-extracted chunks.json upload" for exact-comparability experiments.

---

## 2. Per-stage editable-injection-point design

The UI presents each pipeline as its 4-stage flow (the coarse grouping of the 7/6/8 fine-grained steps already on `docs/pipelines.html`):

**P01:** ① PDF→chunks (params: `chunk_size`, `max_chunks` — default ON in "smoke mode" to protect quotas, `pdf_password`) → ② 청크 분석 (prompt) → ③ Refine 루프 (prompt + `refine_iters`) → ④ 질문 생성 (prompt). Plus an "advanced" card for the shared JSON-repair prompt.

**P02:** ① 파일 탐색 (`SRC_EXTS`, `SKIP_DIRS`, `LOCAL_IMPORT_PREFIXES`) → ② Tier A 구조 스캔 (import regexes, display-mostly) → ③ Tier B 위험 스캔 (three risk regexes) → ④ 판단 채점 (thresholds, `ENTRY_POINT_HINTS`, repeated-pattern strings, duplicate-definition knobs). Banner text: "이 파이프라인은 LLM을 호출하지 않습니다 — 편집 대상은 프롬프트가 아니라 스캔 파라미터입니다."

**P03:** ① 질문 생성 (header + L1/L2/L3/reflection templates — 5 text blocks) → ② 답변 분류 (deterministic; shows the surface/partial/defended thresholds read-only in v1) → ③ 에스컬레이션 (`max_turns`) → ④ 5축 채점 (grading preamble + rubric level texts, editable but flagged `rubric_overridden` in the run record so cross-member comparisons never silently mix rubrics — same discipline as the Hook File's fixed-measurement-instrument rule).

**"Editable" concretely — raw template textarea with guarded placeholders, not a structured form.** Reasoning: the templates embed JSON shape specs and rule lists whose *wording* is exactly what the team wants to experiment with; a field-per-sentence form would forbid the experiment the tool exists for. Each stage card shows: system prompt textarea + user-template textarea with `{placeholder}` tokens highlighted; a live "resolved preview" with real values substituted once inputs are loaded; diff-vs-default; reset button. Validation: data-payload placeholders (`{chunk_text}`, `{unit_map_json}`, `{graph_nodes_json}`, `{code_context}`, `{transcript}`, `{finding}`, `{question}`, `{answer}`, `{rubric_block}`) are hard-required — run blocked if deleted; framing placeholders (`{course_label}`, `{iteration}`) warn-only. Per-stage param fields alongside: model picker (default the team-Locked `qwen/qwen3-next-80b-a3b-instruct`, others behind an "실험" toggle), `max_tokens`, `temperature`. P02 gets type-aware widgets instead: numbers, string-list chips, and (advanced toggle, v1.5) regex fields with an inline compile check + sample-text match tester. Edited templates can be saved as named, shareable presets.

**Prompt manifest + drift test (keeps measurement instruments untouched).** Default templates live in `docs/lab/prompt_manifest.json`. Because P01/P03 prompt texts are f-strings inside function bodies, they get duplicated into the manifest **once**, and a new pytest golden test calls each real function with a stub client that records `messages`, renders the manifest template with the same fixture inputs, and asserts equality — any future edit to the pipeline prompts fails CI until the manifest is regenerated. Module-level objects (`interview_rubric.RUBRIC`, `GRADING_TOOL`, `SINGLE_QUESTION_TOOL`, `FR_AXES`, all P02 constants) are exported by import, no duplication. EXIT: if drift-test churn annoys, hoist prompts to module constants (behavior-identical refactor) later.

---

## 3. API key security model

- Entry: password-type field per session; held in a JS closure; optional "이 탭에서 유지" checkbox → `sessionStorage` (never `localStorage`); never written to Supabase, never in run records, scrubbed from error objects before persistence.
- Transit: browser → owner's proxy → NVIDIA, key in a header, HTTPS both hops. **The key does transit owner-controlled infrastructure — state this to the team honestly.** Mitigations: proxy source lives in the repo (`worker/nvidia-proxy.js`), does no persistence and no header logging, CORS-restricted to the Pages origin, deployed via a repo GitHub Action so deployed code matches published code; teammates who want zero owner-trust can deploy the same worker file themselves and paste their own proxy URL (supported input field — the escape hatch is designed in, not hypothetical).
- Blast radius if leaked: NVIDIA Build keys are free-credit keys (the repo's whole benchmark infra runs on a pool of them) — quota theft, not billing damage; advise rotation after the testing campaign. XSS hardening because in-memory keys are exfiltratable: no third-party JS beyond pinned pdf.js/Pyodide/supabase-js (SRI or vendored), CSP meta tag, all model/user text rendered via `textContent`.
- Timeout note: D98 documented single NVIDIA calls up to ~300s under load. Supabase Edge Functions cap around 150s on free tier; Cloudflare Workers tolerate long upstream waits on the free plan → proxy default is a Cloudflare Worker, with Supabase Edge Function as the one-platform alternative if the team accepts a 120–150s web-tool timeout (interactive P03 calls are normally seconds).

## 4. DB + attribution ("my DB")

`hookfile/db/personal.db` stays what it is — a local, single-writer SQLite for the Hook File loop (and it's gitignored/private by design, D126). For concurrent multi-member web writes the plan is a **Supabase Postgres project owned by the project owner** (free tier: 500MB, ap-northeast-2): real DB the owner can query/export, built-in auth, and RLS means the static site's public anon key cannot be abused for writes.

Attribution: **Supabase magic-link email auth + members table**, not a free-text name field (spoofable, and the public anon key would let anyone who finds the URL pollute the DB). First sign-in requires a team invite code (or email allowlist) → row in `members`. Every write carries `member_id = auth.uid()`, enforced by RLS policy, so "who ran which stage with what edited prompt and what result" is structural, not honor-system.

Schema sketch:

```sql
members(id uuid PK = auth.uid(), display_name text, email text, created_at timestamptz)
runs(id uuid PK, member_id uuid FK, pipeline text CHECK IN ('p01','p02','p03'),
     model text, status text, started_at, finished_at,
     input_meta jsonb,        -- {pdf_name,pages,extractor} | {repo_url,file_count} | {finding_id,source_run_id}
     overrides jsonb,         -- every edited template/param, keyed by stage_id
     overrides_hash text, rubric_overridden bool, manifest_version text, client_commit text, error text)
stage_events(id bigserial, run_id FK, stage_id text, seq int,
     resolved_prompt text, output jsonb, latency_ms int, error text, created_at)
     -- P01: one per chunk call/refine iter/questions call; P03: one per turn + per grading; P02: one per stage
artifacts(id, run_id FK, kind text,  -- unit_map|graph|questions|findings|transcript|grades
     content jsonb, truncated bool)  -- size-capped; raw chunk text NOT stored by default (copyright, see open Q5)
presets(id, member_id FK, pipeline text, stage_id text, name text, body jsonb, created_at)
```

RLS: authenticated members insert own rows; all members can read all runs (it's a comparison tool — confirm, open Q2). Incremental `stage_events` writes make half-finished P01 runs visible to the owner even if a teammate closes the tab mid-run.

## 5. Phased rollout

- **Phase 0 — spikes (about a day):** Pyodide loads `two_tier_scan`+`score_findings`+pattern JSONs from raw.githubusercontent and scans a sample repo in-browser; proxy round-trip with one real member key; Supabase project + RLS + magic link. (CORS facts already verified above.)
- **Phase 1 — MVP = P02 only (2–3 days):** exactly as the brief suggests — no API key, no prompts, no proxy; validates the entire chassis (auth → stage cards → param editor → client-side run → results view → DB write with attribution → owner review page). Inputs: folder upload + public GitHub URL fetch.
- **Phase 2 — P03 (2–4 days):** key entry + proxy; 5 editable templates + rubric editor with `rubric_overridden` flag; finding source = stored P02 run / pasted JSON / bundled `examples/`; live 4-turn interview UI; per-turn grading; transcript+grades persisted.
- **Phase 3 — P01 (2–4 days):** pdf.js extraction (password support), smoke-mode default (`max_chunks=3`), 3 editable prompts + repair prompt, client-side 40rpm/concurrency-3 limiter (single-key simplification of `NvidiaKeyPool`), unit_map/graph/questions views.
- **v2 (explicitly out of scope now):** persona-answerer mode (personas format already compatible: `{context}`/`{question}`), Hook File cross-round loop (respecting the D123 firewall), A/B prompt comparison dashboard, CSV export.

## 6. Decision log entries (draft — real D-numbers assigned on approval, currently D134 is the highest in README)

- **D-A Client-side execution + BaaS, not a Python job server.** WHY: GitHub Pages is static (hard constraint); P03 is an interactive human-in-the-loop conversation that a job backend fits badly; per-member keys+browsers scale naturally with zero owner compute. COST: P01 loses `pdftotext` fidelity (pdf.js differences recorded per-run); a tab must stay open during runs (mitigated by incremental stage_events). EXIT: stand up the FastAPI job backend (Option B) reusing the same DB schema; frontend swaps "run locally" for "submit job".
- **D-B Supabase Postgres+Auth+RLS as "my DB".** WHY: `personal.db` (SQLite) is single-writer/local by design (D126); the tool needs concurrent remote writes, owner-queryable storage, and auth in one free-tier service. COST: external SaaS dependency; 500MB cap forces artifact size discipline. EXIT: schema is plain SQL — `pg_dump` to any Postgres, or swap supabase-js writes for a thin API later.
- **D-C Owner-run CORS proxy for NVIDIA calls.** WHY: verified 2026-07-14 that `integrate.api.nvidia.com` returns no `Access-Control-Allow-Origin` → direct browser calls are impossible, so *some* proxy is forced, and one shared audited-in-repo worker beats N ad-hoc ones. COST: teammates must trust the owner's proxy with key transit (mitigations above). EXIT: per-member self-deployed worker URL field already supported; or NVIDIA someday enables CORS and the proxy URL is set to the API itself.
- **D-D Keys in memory/sessionStorage only, never persisted server-side.** WHY: minimizes owner liability and leak surface; the DB never becomes a key vault. COST: re-entry per browser session. EXIT: none needed — loosening this would be a regression.
- **D-E Pyodide runs the original deterministic Python.** WHY: P02+classifiers embed dozens of measured fixes (D12, D17, D18, D122, D130…); porting would fork them permanently, and fetching source at HEAD gives zero drift. COST: ~10MB one-time WASM download; a small driver shim for constant overrides. EXIT: if load time hurts, hand-port `two_tier_scan` first (smallest, most self-contained) and keep judgment in Pyodide.
- **D-F Prompt manifest + golden drift test instead of refactoring prompts out of function bodies.** WHY: keeps the benchmarked measurement instruments byte-untouched. COST: prompt text exists twice (guarded by CI test). EXIT: hoist to module constants later; manifest then becomes generated-by-import like the P02 constants already are.
- **D-G Raw guarded-placeholder template editing, not structured forms.** WHY: free-form prompt experimentation is the tool's purpose; JSON-shape blocks inside prompts don't decompose into fields. COST: users can write broken prompts (mitigated by required-placeholder validation + resolved preview + reset). EXIT: add structured mode as a layer over the same manifest if misuse dominates.
- **D-H P02-first phasing.** WHY: no key/proxy/prompt complexity → proves hosting+DB+attribution chassis with the lowest-risk pipeline. COST: the flashiest feature (prompt editing) ships second. EXIT: none — pure sequencing.

## 7. Open questions for the user before implementation

1. **Auth**: magic-link email + invite code OK? Which emails/allowlist for the team (수도권 6반 17조)?
2. **Visibility**: may every member see everyone's runs, or owner-only for cross-member views?
3. **Supabase vs Firebase** — any existing account/preference? (Plan assumes Supabase, Seoul region.)
4. **Proxy host**: Cloudflare Worker (recommended; tolerates D98-style 300s calls; one more account) vs Supabase Edge Function (single platform; ~150s cap)?
5. **P01 copyright/privacy**: the 교안 PDF is licensed course material — confirm storing only derived outputs (unit_map/questions, truncated evidence) in the DB, never raw chunk text; PDF itself never leaves the browser.
6. **Model picker**: default locked qwen only, with the benchmark-reliable set behind an "experiment" toggle — or fully open?
7. **P02 regex editing** in v1, or numeric/list params only with regexes v1.5 (recommended)?
8. **Artifact size**: cap `stage_events.output`/`artifacts.content` at ~100KB each with truncation flags — acceptable?
9. **Where the tool lives**: `docs/lab/` with a nav link from `docs/pipelines.html` — naming preference?
10. **P03 rubric editing**: confirm it should be allowed-but-flagged (vs locked read-only to preserve the fixed measurement instrument).

### Critical Files for Implementation
- `scripts/java_curriculum_nvidia_pipeline.py` — P01's three prompt templates + params to mirror into the manifest
- `feedback/turn_engine.py` — P03 level templates, tool schema, 4-turn loop to re-orchestrate in JS
- `feedback/llm_interview_grader.py` — grading prompt, GRADING_TOOL, validation (with feedback/interview_rubric.py rubric texts)
- `cognition/two_tier_scan.py` — P02 scan constants/regexes to expose in the param editor and run via Pyodide
- `judgment/score_findings.py` — P02 judgment thresholds + sidecar pattern-JSON dependencies that must load into the browser FS
- `feedback/nvidia_client.py` — API endpoint/auth/retry semantics the proxy and JS client must reproduce
