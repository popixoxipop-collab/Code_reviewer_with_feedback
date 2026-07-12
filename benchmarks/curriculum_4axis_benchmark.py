"""D120 -- Pipeline 01 (curriculum analysis) 4-axis benchmark.

Reuses scripts/java_curriculum_nvidia_pipeline.py's functions directly (analyse_chunk,
generate_questions, etc.) rather than shelling out to the whole CLI per repeat --
isolating one stage's reproducibility shouldn't pay for refine+graph+questions every time.

PDF is password-protected (JAVA_CURRICULUM_PDF_PASSWORD in .env, not printed/logged
anywhere in this file's output -- only passed through to pdftotext/pdfinfo).

Corpus: 26 chunks (10p each, 251 pages total). Stratified 5-chunk sample for
reproducibility/T1 picked from a 0-cost local code-density scan across all 26 chunks
(no LLM calls) -- see D120 note for the scan output that produced this selection.

Usage:
  python3 benchmarks/curriculum_4axis_benchmark.py --pilot        # REPEATS=10, ~60 calls, ~1h
  python3 benchmarks/curriculum_4axis_benchmark.py --stability    # 3x full 26-chunk pipeline runs, ~87 calls
  python3 benchmarks/curriculum_4axis_benchmark.py --reproducibility  # REPEATS=100 (chunk) / 50 (qgen), ~550 calls
  python3 benchmarks/curriculum_4axis_benchmark.py --precision    # 2-tier provenance audit on a full unit_map
  python3 benchmarks/curriculum_4axis_benchmark.py --t1           # P01-T1 model-comparison mini-track, ~100 calls
  python3 benchmarks/curriculum_4axis_benchmark.py --aggregate-only
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO / "feedback"))
sys.path.insert(0, str(REPO))

from java_curriculum_nvidia_pipeline import (  # noqa: E402
    Chunk, build_chunks, analyse_chunk, make_unit_map, refine_once,
    build_graph, generate_questions, normalize_pages, CountingNvidiaKeyPool,
)
from nvidia_client import NvidiaRotatingClient  # noqa: E402
from timeout_config import DEFAULT_TIMEOUT_S, DEFAULT_MAX_TOKENS  # noqa: E402

PDF = Path(os.environ.get("JAVA_CURRICULUM_PDF", "/Users/xox/Downloads/AI_JAVA_교안.pdf"))
PDF_PASSWORD = os.environ.get("JAVA_CURRICULUM_PDF_PASSWORD")
MODEL = "qwen/qwen3-next-80b-a3b-instruct"  # 팀 Locked
# D120 T1 실패(root-caused): bare "step-3.5-flash"/"mistral-medium-3.5" -> HTTP 404
#   (NVIDIA Build는 provider prefix 필수). benchmark_4axis_regrade.py의
#   RELIABLE_MODELS에서 실제 검증된 정확한 ID로 교체.
COMPARE_MODELS = ["stepfun-ai/step-3.5-flash", "mistralai/mistral-medium-3.5-128b", "qwen/qwen3-next-80b-a3b-instruct"]
CHUNK_SIZE = 10
TOTAL_PAGES = 251

# D120: stratified 5-chunk sample (앞/중-저밀도/중-고밀도/후반-고밀도/후반) picked from a
#   0-cost local code-density scan (regex hit count for public class/void/import java/{}/
#   등) across all 26 chunks -- this curriculum's code density rises monotonically toward
#   the back (intro chapters are conceptual, later chapters are code-heavy), so "뒤"와
#   "코드예제 밀집"이 자연히 겹침 -- 겹침을 인위적으로 피하기보다 실측 분포를 그대로 반영.
#   scan: p1-10 code_hits=0/chars=3995, p61-70=71/6028, p131-140=50/4542,
#         p191-200=123/11159, p241-250=102/13518 (p251-251은 18자뿐인 tail 조각이라 제외)
SAMPLE_CHUNK_STARTS = [1, 61, 131, 191, 241]
REPEATS_CHUNK = 100
REPEATS_QGEN = 50
REPEATS_PILOT = 10
CAPACITY_PER_MINUTE = 20  # D120 2절: qwen 단일모델 장시간 실행이므로 보수적 기본
MAX_WORKERS = 4
MAX_TOKENS_CHUNK = 1800  # matches the pipeline script's own CLI default
# D120 pilot failure (root-caused): MAX_TOKENS_QGEN=1800 (matching the pipeline
#   script's own --max-tokens-questions CLI default) truncated mid-generation --
#   5/10 pilot qgen calls failed, and a follow-up 3-call diagnostic with full
#   exception visibility showed the truncated JSON was legitimate, well-formed
#   Korean pedagogical content (question+rationale+good_answer_signal+common_gap,
#   4 verbose text fields per question, potentially many questions across a
#   342-node graph) cut off mid-string ("Unterminated string", char 3597) -- the
#   same output-cap-truncation pattern this project already hit at D95/D103/D108b,
#   reproduced here in a new stage. This also means the PRODUCTION pipeline's own
#   1800 default likely has the same problem, not just this benchmark -- worth
#   flagging to the team separately from this harness fix.
#   Second attempt at 8192 made things WORSE (3/3 retest calls -> HTTP 400 Bad
#   Request, up from 1/3 at 1800) -- this model/endpoint appears to reject
#   max_tokens above some ceiling between 1800 and 8192 outright, rather than
#   truncating past it. Falling back to DEFAULT_MAX_TOKENS(4096) -- this
#   project's own established central value, already validated working for this
#   exact model (qwen3-next-80b) via P02-T2's 14/14 successful calls at that
#   same setting.
MAX_TOKENS_QGEN = DEFAULT_MAX_TOKENS

BENCH_DIR = REPO / "benchmarks"
RAW_STABILITY = BENCH_DIR / "curriculum_4axis_raw_stability.json"
RAW_REPRO_CHUNK = BENCH_DIR / "curriculum_4axis_raw_repro_chunk.json"
RAW_REPRO_QGEN = BENCH_DIR / "curriculum_4axis_raw_repro_qgen.json"
RAW_T1 = BENCH_DIR / "curriculum_4axis_raw_t1.json"
PROVENANCE_AUDIT = BENCH_DIR / "curriculum_provenance_audit.json"
SUMMARY = BENCH_DIR / "curriculum_4axis_summary.json"


def log(msg):
    print(f"[curriculum_4axis] {msg}", file=sys.stderr, flush=True)


def get_client():
    pool = CountingNvidiaKeyPool.from_env(capacity_per_minute=CAPACITY_PER_MINUTE)
    return NvidiaRotatingClient(pool=pool, timeout_s=DEFAULT_TIMEOUT_S)


def load_chunks_for(starts):
    """Extract only the requested chunk page-ranges (pdftotext, 0 LLM cost)."""
    chunks = []
    for start in starts:
        end = min(start + CHUNK_SIZE - 1, TOTAL_PAGES)
        cmd = ["pdftotext", "-layout"]
        if PDF_PASSWORD:
            cmd.extend(["-upw", PDF_PASSWORD])
        cmd.extend(["-f", str(start), "-l", str(end), str(PDF), "-"])
        result = subprocess.run(cmd, check=True, text=True, capture_output=True, timeout=60)  # timeout-guard: allow (local pdftotext, not NVIDIA)
        chunks.append(Chunk(start=start, end=end, text=result.stdout.strip()))
    return chunks


def normalize_chunk_signature(result):
    """Structural signature for chunk-layer reproducibility: unit boundaries +
    sorted concept-label set + sorted source_pages set (D120 4.1 -- raw JSON byte
    match degenerates toward 0 for long-form generation, so this normalizes).
    """
    units = sorted(
        (u.get("unit_id", ""), u.get("unit_title", ""), tuple(sorted(set(int(p) for p in (u.get("source_pages") or []) if str(p).lstrip("-").isdigit()))))
        for u in (result.get("units") or [])
    )
    concepts = sorted(
        (c.get("name", ""), c.get("kind", "concept"), tuple(sorted(set(int(p) for p in (c.get("source_pages") or []) if str(p).lstrip("-").isdigit()))))
        for c in (result.get("concepts") or [])
    )
    return json.dumps({"units": units, "concepts": concepts}, sort_keys=True, ensure_ascii=False)


def normalize_qgen_signature(result):
    """질문생성 층 시그니처: 질문 수 + 정렬된 (unit, source_pages) 시그니처 집합."""
    sigs = sorted(
        (q.get("unit", ""), tuple(sorted(set(int(p) for p in (q.get("source_pages") or []) if str(p).lstrip("-").isdigit()))))
        for q in (result.get("questions") or [])
    )
    return json.dumps({"n_questions": len(result.get("questions") or []), "sigs": sigs}, sort_keys=True, ensure_ascii=False)


def cmd_stability(n_runs=3):
    """Full CLI pipeline, n_runs times, using the script's own subprocess entrypoint
    (exercises the real error-handling/fallback paths, not just the raw functions)."""
    results = []
    for run_idx in range(1, n_runs + 1):
        out_dir = BENCH_DIR / f"_curriculum_stability_run{run_idx}"
        t0 = time.time()
        cmd = [
            sys.executable, str(SCRIPTS / "java_curriculum_nvidia_pipeline.py"),
            "--pdf", str(PDF), "--out-dir", str(out_dir), "--model", MODEL,
            "--capacity-per-minute", str(CAPACITY_PER_MINUTE), "--max-workers", str(MAX_WORKERS),
            "--timeout-s", str(DEFAULT_TIMEOUT_S),
            "--max-tokens-questions", str(MAX_TOKENS_QGEN),  # D120: script's own 1800 default truncates (see MAX_TOKENS_QGEN comment above)
        ]
        env = dict(os.environ)
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=1800)  # timeout-guard: allow (30min ceiling for one full 26-chunk pipeline run, not a single NVIDIA call)
        elapsed = time.time() - t0
        ok = r.returncode == 0 and (out_dir / "questions.json").exists()
        stage_stats = {}
        if ok:
            chunks_data = json.loads((out_dir / "chunks.json").read_text())
            refine_data = json.loads((out_dir / "refine_audit.json").read_text())
            questions_data = json.loads((out_dir / "questions.json").read_text())
            stage_stats = {
                "chunk_ok": sum(1 for c in chunks_data if not c.get("error")),
                "chunk_total": len(chunks_data),
                "refine_ok": sum(1 for a in refine_data if a.get("status") in ("pass", "needs_refine") and "error" not in str(a.get("coverage_summary", ""))),
                "refine_total": len(refine_data),
                "questions_ok": len(questions_data.get("questions") or []) > 0 and "error" not in questions_data,
                "n_questions": len(questions_data.get("questions") or []),
            }
        results.append({
            "run": run_idx, "ok": ok, "elapsed_s": round(elapsed, 1),
            "returncode": r.returncode, "stderr_tail": r.stderr[-800:] if not ok else None,
            **stage_stats,
        })
        log(f"[stability {run_idx}/{n_runs}] ok={ok} elapsed={elapsed:.1f}s stages={stage_stats}")
    RAW_STABILITY.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    log(f"wrote {RAW_STABILITY}")
    return results


def cmd_reproducibility_chunk(repeats):
    chunks = load_chunks_for(SAMPLE_CHUNK_STARTS)
    client = get_client()
    results = []
    for i, chunk in enumerate(chunks, 1):
        signatures, errors, error_types = [], 0, {}
        t0 = time.time()

        def call_once(rep):
            try:
                r = _retry_transient(analyse_chunk, client, MODEL, chunk, MAX_TOKENS_CHUNK)
                return normalize_chunk_signature(r), None
            except Exception as e:
                return None, f"{type(e).__name__}: {str(e)[:200]}"

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = [ex.submit(call_once, r) for r in range(repeats)]
            for done_i, fut in enumerate(as_completed(futures), 1):
                sig, err = fut.result()
                if err:
                    errors += 1
                    error_types[err] = error_types.get(err, 0) + 1
                else:
                    signatures.append(sig)
                log(f"[repro-chunk {i}/{len(chunks)} p{chunk.start}-{chunk.end}] {done_i}/{repeats} done ({errors} err)")
        elapsed = time.time() - t0
        unique = set(signatures)
        identical_rate = None
        if signatures:
            mode_sig = max(unique, key=signatures.count)
            identical_rate = signatures.count(mode_sig) / len(signatures)
        results.append({
            "chunk_range": f"p{chunk.start}-{chunk.end}", "reps": repeats, "ok_reps": len(signatures),
            "errors": errors, "error_types": error_types, "unique_signatures": len(unique), "identical_rate": identical_rate,
            "elapsed_s": round(elapsed, 1),
        })
        log(f"[repro-chunk {i}/{len(chunks)}] p{chunk.start}-{chunk.end}: {len(unique)} unique sig(s)/{len(signatures)} ok, identical_rate={identical_rate}")
    RAW_REPRO_CHUNK.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    log(f"wrote {RAW_REPRO_CHUNK}")
    return results


UNIT_MAP_CACHE = BENCH_DIR / "_curriculum_fixed_unit_map_cache.json"


TRANSIENT_ERROR_MARKERS = ("HTTP Error 400", "HTTP Error 500", "HTTP Error 502", "HTTP Error 503", "KeyPoolExhausted", "timeout")


def _retry_transient(fn, *args, attempts=3, backoff_s=8.0, **kwargs):
    """D120: retry ONLY infra-level failures (400/500/502/503/key-pool-exhausted/
    timeout) up to `attempts` times -- NOT JSON-parse/ValueError failures, which
    reflect genuine model output behavior worth measuring honestly (reproducibility
    should see real malformed-output events, not have them silently retried away).
    Root cause of the 400 burst is still uncertain (isolated + 4-concurrent probes
    both came back clean after the full run finished, consistent with a transient
    NVIDIA-side window rather than a persistent concurrency ceiling in this code) --
    retry is a resilience measure, not a fix for an identified bug in this script."""
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e)
            if not any(marker in msg for marker in TRANSIENT_ERROR_MARKERS):
                raise
            last_exc = e
            if attempt < attempts:
                time.sleep(backoff_s)
    raise last_exc


def _call_with_retry(fn, *args, attempts=3, backoff_s=5.0, **kwargs):
    """D120 실패 교훈: refine_once 등 단발 콜은 원본 analyse_chunk 루프와 달리
    try/except가 없어 HTTP 500 1건에 파일럿 전체(qgen 26콜 포함)가 죽음 -- 429뿐
    아니라 500류 일시적 서버 오류도 재시도 대상으로 다뤄야 함(D102/D109 계보:
    인프라 원인은 즉시 포기가 아니라 재시도 후 annotation)."""
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            log(f"[retry] {fn.__name__} attempt {attempt}/{attempts} failed: {type(e).__name__}: {e}")
            if attempt < attempts:
                time.sleep(backoff_s)
    raise last_exc


def build_fixed_graph_for_qgen(client):
    """One real chunk+refine pass over the full 26-chunk corpus to build a single
    FIXED graph input that every question-gen repeat is measured against.
    Caches chunk_results/unit_map to disk right after the expensive 26-call loop
    so a later refine failure doesn't force re-spending those calls on retry."""
    if UNIT_MAP_CACHE.exists():
        log(f"[qgen-setup] reusing cached unit_map from {UNIT_MAP_CACHE}")
        unit_map = json.loads(UNIT_MAP_CACHE.read_text())
    else:
        chunks = build_chunks(PDF, CHUNK_SIZE, TOTAL_PAGES, None, password=PDF_PASSWORD)
        log(f"[qgen-setup] built {len(chunks)} chunks, analysing all (one pass, real cost)...")
        chunk_results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(analyse_chunk, client, MODEL, c, MAX_TOKENS_CHUNK): c for c in chunks}
            for done_i, fut in enumerate(as_completed(futures), 1):
                chunk = futures[fut]
                try:
                    r = fut.result()
                    r["chunk_range"] = r.get("chunk_range") or chunk.range
                    chunk_results.append(r)
                except Exception as e:
                    chunk_results.append({"chunk_range": chunk.range, "units": [], "concepts": [], "error": str(e)})
                log(f"[qgen-setup] {done_i}/{len(chunks)} chunks analysed")
        unit_map = make_unit_map([c for c in chunk_results if not c.get("error")])
        UNIT_MAP_CACHE.write_text(json.dumps(unit_map, ensure_ascii=False))
        log(f"[qgen-setup] cached unit_map -> {UNIT_MAP_CACHE} (survives a later refine failure)")
    audit = _call_with_retry(refine_once, client, MODEL, unit_map, 1, 1600)
    graph = build_graph(unit_map, [audit])
    log(f"[qgen-setup] fixed graph ready: {len(graph['nodes'])} nodes, {len(graph['links'])} links")
    return graph


def cmd_reproducibility_qgen(repeats):
    client = get_client()
    try:
        graph = build_fixed_graph_for_qgen(client)
    except Exception as e:
        log(f"[qgen-setup] FAILED after retries: {type(e).__name__}: {e} -- qgen-layer reproducibility skipped, chunk-layer data already saved")
        result = {"reps": repeats, "ok_reps": 0, "errors": repeats, "unique_signatures": 0, "identical_rate": None, "setup_error": str(e)}
        RAW_REPRO_QGEN.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    (BENCH_DIR / "_curriculum_fixed_graph_for_qgen_repro.json").write_text(json.dumps(graph, ensure_ascii=False))

    signatures, errors, error_types = [], 0, {}

    def call_once(rep):
        try:
            r = _retry_transient(generate_questions, client, MODEL, graph, MAX_TOKENS_QGEN)
            return normalize_qgen_signature(r), None
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:200]}"

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(call_once, r) for r in range(repeats)]
        for done_i, fut in enumerate(as_completed(futures), 1):
            sig, err = fut.result()
            if err:
                errors += 1
                error_types[err] = error_types.get(err, 0) + 1
            else:
                signatures.append(sig)
            log(f"[repro-qgen] {done_i}/{repeats} done ({errors} err)")
    elapsed = time.time() - t0
    unique = set(signatures)
    identical_rate = None
    mode_agreement_rate = None
    if signatures:
        mode_sig = max(unique, key=signatures.count)
        identical_rate = signatures.count(mode_sig) / len(signatures)
        mode_agreement_rate = identical_rate  # single sample point -- same value, kept as separate field for schema parity with P03/P02
    result = {
        "reps": repeats, "ok_reps": len(signatures), "errors": errors, "error_types": error_types,
        "unique_signatures": len(unique), "identical_rate": identical_rate,
        "reproducibility_mode_agreement_rate": mode_agreement_rate, "elapsed_s": round(elapsed, 1),
    }
    RAW_REPRO_QGEN.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    log(f"wrote {RAW_REPRO_QGEN}: {result}")
    return result


def cmd_t1():
    chunks = load_chunks_for(SAMPLE_CHUNK_STARTS)
    client = get_client()
    results = []
    for model in COMPARE_MODELS:
        for i, chunk in enumerate(chunks, 1):
            signatures, errors, elapsed_list, error_types = [], 0, [], {}

            def call_once(rep):
                t0 = time.time()
                try:
                    r = _retry_transient(analyse_chunk, client, model, chunk, MAX_TOKENS_CHUNK)
                    return normalize_chunk_signature(r), time.time() - t0, None
                except Exception as e:
                    return None, time.time() - t0, f"{type(e).__name__}: {str(e)[:200]}"

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                futures = [ex.submit(call_once, r) for r in range(REPEATS_PILOT)]
                for done_i, fut in enumerate(as_completed(futures), 1):
                    sig, el, err = fut.result()
                    elapsed_list.append(el)
                    if err:
                        errors += 1
                        error_types[err] = error_types.get(err, 0) + 1
                    else:
                        signatures.append(sig)
                    log(f"[t1 {model} chunk{i}/{len(chunks)}] {done_i}/{REPEATS_PILOT} done ({errors} err)")
            unique = set(signatures)
            identical_rate = (signatures.count(max(unique, key=signatures.count)) / len(signatures)) if signatures else None
            results.append({
                "model": model, "chunk_range": f"p{chunk.start}-{chunk.end}",
                "reps": REPEATS_PILOT, "ok_reps": len(signatures), "errors": errors, "error_types": error_types,
                "identical_rate": identical_rate, "mean_elapsed_s": round(sum(elapsed_list) / len(elapsed_list), 1) if elapsed_list else None,
            })
    RAW_T1.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    log(f"wrote {RAW_T1}")
    return results


TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]{2,}")


def cmd_precision():
    """2-tier provenance precision: (1) deterministic token match of concept
    name/summary against the actual pdftotext text of its cited source_pages,
    (2) for tier-1 mismatches only, judge with a DIFFERENT model than the
    generator (self-confirmation 방지)."""
    client = get_client()
    graph_path = BENCH_DIR / "_curriculum_fixed_graph_for_qgen_repro.json"
    if not graph_path.exists():
        log("[precision] no fixed graph found -- run --reproducibility (qgen) first, or run this after it")
        return None
    graph = json.loads(graph_path.read_text())

    items = [n for n in graph["nodes"] if n["type"] in ("concept", "code_example", "caution") and n.get("source_pages")]
    log(f"[precision] auditing {len(items)} concept/code/caution nodes")

    tier1_results = []
    for it in items:
        pages_text = ""
        for p in it["source_pages"]:
            cmd = ["pdftotext", "-layout"]
            if PDF_PASSWORD:
                cmd.extend(["-upw", PDF_PASSWORD])
            cmd.extend(["-f", str(p), "-l", str(p), str(PDF), "-"])
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # timeout-guard: allow (local pdftotext)
            pages_text += r.stdout.lower()
        label_tokens = set(TOKEN_RE.findall((it["label"] + " " + it.get("summary", "")).lower()))
        matched = sum(1 for t in label_tokens if t in pages_text)
        match_ratio = matched / len(label_tokens) if label_tokens else 0.0
        tier1_results.append({
            "id": it["id"], "label": it["label"], "source_pages": it["source_pages"],
            "tier1_match_ratio": round(match_ratio, 3), "tier1_pass": match_ratio >= 0.5,
        })

    mismatches = [r for r in tier1_results if not r["tier1_pass"]]
    log(f"[precision] tier1: {len(tier1_results) - len(mismatches)}/{len(tier1_results)} pass, {len(mismatches)} need tier2 judge")

    # D120: same bare-name bug as T1 (COMPARE_MODELS) -- NVIDIA Build needs the
    #   provider prefix, confirmed via benchmark_4axis_regrade.py's RELIABLE_MODELS.
    #   All 194 tier2 calls in the first precision run silently failed on this.
    JUDGE_MODEL = "mistralai/mistral-medium-3.5-128b"  # generator(qwen)와 다른 모델 -- 자기확증 방지
    tier2_results = []
    node_by_id = {n["id"]: n for n in graph["nodes"]}
    def judge_one(m):
        node = node_by_id[m["id"]]
        pages_text = ""
        for p in node["source_pages"]:
            cmd = ["pdftotext", "-layout"]
            if PDF_PASSWORD:
                cmd.extend(["-upw", PDF_PASSWORD])
            cmd.extend(["-f", str(p), "-l", str(p), str(PDF), "-"])
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # timeout-guard: allow (local pdftotext)
            pages_text += r.stdout
        prompt = (
            f"다음 개념이 인용된 페이지 원문에 실제로 근거하는지 판단하라.\n\n"
            f"개념: {node['label']}\n요약: {node.get('summary', '')}\n\n"
            f"인용 페이지 원문:\n{pages_text[:6000]}\n\n"
            f"JSON만 반환: {{\"grounded\": true|false, \"reason\": \"짧은 이유\"}}"
        )

        def _do_call():
            resp = client.chat(
                model=JUDGE_MODEL, messages=[{"role": "user", "content": prompt}],
                max_tokens=DEFAULT_MAX_TOKENS, temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = resp["choices"][0]["message"].get("content") or "{}"
            return json.loads(content)

        try:
            verdict = _retry_transient(_do_call)
            return {"id": m["id"], "grounded": verdict.get("grounded"), "reason": verdict.get("reason")}
        except Exception as e:
            return {"id": m["id"], "grounded": None, "error": str(e)}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(judge_one, m): m for m in mismatches}
        for done_i, fut in enumerate(as_completed(futures), 1):
            tier2_results.append(fut.result())
            log(f"[precision-tier2] {done_i}/{len(mismatches)} done: {tier2_results[-1]['id']} grounded={tier2_results[-1].get('grounded')}")

    n_grounded_tier2 = sum(1 for t in tier2_results if t.get("grounded") is True)
    precision_rate = (len(tier1_results) - len(mismatches) + n_grounded_tier2) / len(tier1_results) if tier1_results else None

    audit = {
        "n_items": len(tier1_results), "tier1_pass": len(tier1_results) - len(mismatches),
        "tier1_mismatch_needing_tier2": len(mismatches), "tier2_judge_model": JUDGE_MODEL,
        "tier2_grounded": n_grounded_tier2, "tier2_not_grounded": sum(1 for t in tier2_results if t.get("grounded") is False),
        "final_precision_rate": round(precision_rate, 3) if precision_rate is not None else None,
        "tier1_detail": tier1_results, "tier2_detail": tier2_results,
        "note": "tier1은 결정론 토큰매치(0콜), tier2는 mismatch만 다른 모델(judge)로 재판정. "
                "검증기 자체의 신뢰도(사람 표본 대조)는 별도 사람 감사 필요 -- 미착수, 이 필드는 그 결과 없이 자동 판정만 반영",
    }
    PROVENANCE_AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2))
    log(f"wrote {PROVENANCE_AUDIT}: precision_rate={audit['final_precision_rate']}")
    return audit


def aggregate():
    stability = json.loads(RAW_STABILITY.read_text()) if RAW_STABILITY.exists() else None
    repro_chunk = json.loads(RAW_REPRO_CHUNK.read_text()) if RAW_REPRO_CHUNK.exists() else None
    repro_qgen = json.loads(RAW_REPRO_QGEN.read_text()) if RAW_REPRO_QGEN.exists() else None
    t1 = json.loads(RAW_T1.read_text()) if RAW_T1.exists() else None
    precision = json.loads(PROVENANCE_AUDIT.read_text()) if PROVENANCE_AUDIT.exists() else None

    stability_summary = None
    if stability:
        n = len(stability)
        n_ok = sum(1 for r in stability if r["ok"])
        chunk_rates = [r["chunk_ok"] / r["chunk_total"] for r in stability if r.get("chunk_total")]
        refine_rates = [r["refine_ok"] / r["refine_total"] for r in stability if r.get("refine_total")]
        qgen_rates = [1.0 if r.get("questions_ok") else 0.0 for r in stability if r["ok"]]
        e2e = None
        if chunk_rates and refine_rates and qgen_rates:
            e2e = round((sum(chunk_rates) / len(chunk_rates)) * (sum(refine_rates) / len(refine_rates)) * (sum(qgen_rates) / len(qgen_rates)), 3)
        stability_summary = {
            "n_runs": n, "n_full_pipeline_ok": n_ok,
            "mean_chunk_success_rate": round(sum(chunk_rates) / len(chunk_rates), 3) if chunk_rates else None,
            "mean_refine_success_rate": round(sum(refine_rates) / len(refine_rates), 3) if refine_rates else None,
            "mean_questions_success_rate": round(sum(qgen_rates) / len(qgen_rates), 3) if qgen_rates else None,
            "end_to_end_stability": e2e,
            "mean_elapsed_s": round(sum(r["elapsed_s"] for r in stability) / n, 1) if n else None,
        }

    repro_summary = None
    if repro_chunk or repro_qgen:
        chunk_rates = [r["identical_rate"] for r in (repro_chunk or []) if r.get("identical_rate") is not None]
        repro_summary = {
            "chunk_layer": {"per_chunk": repro_chunk, "mean_identical_rate": round(sum(chunk_rates) / len(chunk_rates), 4) if chunk_rates else None, "repeats": REPEATS_CHUNK},
            "qgen_layer": repro_qgen,
        }

    summary = {
        "note": "P01 4-axis (D120). Model=qwen3-next-80b (Locked). Stability=3-stage(chunk x refine x qgen) e2e product over full-corpus pipeline runs. Precision=2-tier provenance (deterministic token match + cross-model judge on mismatches only). Reproducibility=normalized structural signature identical-rate, stratified 5-chunk sample for chunk layer + 1 fixed graph for qgen layer. Speed=stability run wall-clock.",
        "stability": stability_summary,
        "reproducibility": repro_summary,
        "precision": {"status": "measured" if precision else "not_run", "summary": precision and {k: v for k, v in precision.items() if k not in ("tier1_detail", "tier2_detail")}},
        "p01_t1_model_comparison": t1,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    log(f"wrote {SUMMARY}")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--stability", action="store_true")
    ap.add_argument("--reproducibility", action="store_true")
    ap.add_argument("--precision", action="store_true")
    ap.add_argument("--t1", action="store_true")
    ap.add_argument("--aggregate-only", action="store_true")
    args = ap.parse_args()

    if not PDF_PASSWORD:
        log("WARNING: JAVA_CURRICULUM_PDF_PASSWORD not set -- PDF reads will fail")

    if args.aggregate_only:
        aggregate()
        return

    if args.pilot:
        log("=== PILOT: 5 chunks x REPEATS=10 + qgen x REPEATS=10 (~60 calls) ===")
        cmd_reproducibility_chunk(REPEATS_PILOT)
        cmd_reproducibility_qgen(REPEATS_PILOT)
        return

    if args.stability:
        cmd_stability(3)

    if args.reproducibility:
        cmd_reproducibility_chunk(REPEATS_CHUNK)
        cmd_reproducibility_qgen(REPEATS_QGEN)

    if args.precision:
        cmd_precision()

    if args.t1:
        cmd_t1()

    aggregate()


if __name__ == "__main__":
    main()
