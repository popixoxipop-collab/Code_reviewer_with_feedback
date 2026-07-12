"""D119 -- Pipeline 02 (cognition/judgment) 4-axis benchmark.

Zero NVIDIA calls: cognition/two_tier_scan.py and judgment/score_findings.py are
pure local regex/rule pipelines (see judgment/score_findings.py D3). P02-T2 (static
vs pure-LLM MEAS-02) is a separate script (meas02_run_benchmark.py, already exists).

Corpus: examples/{c_cpp,java,javascript,python}/<repo>/PROVENANCE.json (git_url +
pinned commit). examples/ only keeps frozen scan/judgment outputs, not raw source --
this harness re-clones at the pinned commit into a local cache before running fresh.
examples/{lms,shadowbroker,study_match} have no PROVENANCE.json (team-internal
fixtures, source location not recorded) -- excluded from fresh-execution axes,
noted explicitly in the summary rather than silently dropped.

Usage:
  python3 benchmarks/judgment_4axis_benchmark.py --clone            # populate corpus cache (network, one-time)
  python3 benchmarks/judgment_4axis_benchmark.py --stability        # fresh scan+judge over full corpus (also yields speed)
  python3 benchmarks/judgment_4axis_benchmark.py --reproducibility  # (a) 100x fixed-state determinism + (b) 3-state sensitivity
  python3 benchmarks/judgment_4axis_benchmark.py --ablation         # P02-T1 structural effect of the 3 correction hooks
  python3 benchmarks/judgment_4axis_benchmark.py --all              # everything except --clone (clone runs automatically if cache is empty)
  python3 benchmarks/judgment_4axis_benchmark.py --aggregate-only   # rebuild summary.json from existing raw files, no execution
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
COGNITION = ROOT / "cognition" / "two_tier_scan.py"
JUDGMENT = ROOT / "judgment" / "score_findings.py"
BENCH_DIR = ROOT / "benchmarks"
RAW_STABILITY = BENCH_DIR / "judgment_4axis_raw_stability.json"
RAW_REPRO = BENCH_DIR / "judgment_4axis_raw_reproducibility.json"
RAW_ABLATION = BENCH_DIR / "judgment_4axis_raw_ablation.json"
SUMMARY = BENCH_DIR / "judgment_4axis_summary.json"

CACHE = Path(os.environ.get(
    "JUDGMENT_BENCH_CACHE",
    "/private/tmp/claude-501/-Users-xox/da999462-3e63-4846-b385-b4fd0a1fbc86/scratchpad/judgment_corpus_cache",
))
LANG_DIRS = ("c_cpp", "java", "javascript", "python")
NO_PROVENANCE = ("lms", "shadowbroker", "study_match")

# D119: reproducibility (a)/(b) run the full pipeline many times per repo -- capping
#   to a stratified subset (2 per language) keeps (a)'s 100x pass to a few hundred
#   local subprocess calls instead of ~3,900 (39 repos x 100), matching the plan's
#   own "로컬 CPU로 수 분" budget. Raw per-repo stability/speed still covers all 39.
#   WHY: full-corpus x 100 reps is unnecessary -- determinism is a property of the
#        pipeline code, not of any one repo, so a few repos per language is enough
#        to catch os.walk/dict-order nondeterminism if it exists (D119 3.1 EXIT).
#   COST: if determinism bugs are language- or repo-structure-specific, a 2-per-lang
#        sample could miss one.
#   EXIT: raise REPRO_SAMPLE_PER_LANG (raw data merge pattern makes this cheap to redo).
REPRO_SAMPLE_PER_LANG = 2
REPEATS_FIXED_STATE = 100

# D119: local-op timeouts, NOT NVIDIA-call timeouts -- timeout_config.DEFAULT_TIMEOUT_S
#   (600s) is tuned for LLM calls that legitimately take minutes; a local git clone or a
#   deterministic regex-based scan/judge subprocess that hangs for anywhere near that long
#   is a real bug, not normal latency, so a much shorter fail-fast value is correct here.
CLONE_TIMEOUT_S = 180  # timeout-guard: allow (local git clone, not NVIDIA)
RUN_TIMEOUT_S = 120  # timeout-guard: allow (local deterministic subprocess, not NVIDIA)
CHECKOUT_TIMEOUT_S = 60  # timeout-guard: allow (local git checkout, not NVIDIA)


def log(msg):
    print(f"[judgment_4axis] {msg}", file=sys.stderr, flush=True)


def discover_corpus():
    repos = []
    for lang_dir in LANG_DIRS:
        base = EXAMPLES / lang_dir
        if not base.is_dir():
            continue
        for sub in sorted(base.iterdir()):
            prov = sub / "PROVENANCE.json"
            if not prov.exists():
                continue
            data = json.loads(prov.read_text(encoding="utf-8"))
            repos.append({
                "label": f"{lang_dir}/{sub.name}",
                "lang_tag": data.get("lang_tag", lang_dir),
                "git_url": data["git_url"],
                "commit": data["commit"],
            })
    return repos


def clone_at_commit(repo):
    dest = CACHE / repo["label"]
    if (dest / ".git").exists():
        return dest, "cached"
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    r1 = subprocess.run(
        ["git", "clone", "--quiet", repo["git_url"], str(dest)],
        capture_output=True, text=True, timeout=CLONE_TIMEOUT_S,
    )
    if r1.returncode != 0:
        return None, f"clone failed: {r1.stderr.strip()[:300]}"
    r2 = subprocess.run(
        ["git", "-C", str(dest), "checkout", "--quiet", repo["commit"]],
        capture_output=True, text=True, timeout=CHECKOUT_TIMEOUT_S,
    )
    if r2.returncode != 0:
        return None, f"checkout failed: {r2.stderr.strip()[:300]}"
    return dest, "cloned"


def cmd_clone(repos):
    results = []
    for i, repo in enumerate(repos, 1):
        dest, status = clone_at_commit(repo)
        ok = dest is not None
        log(f"[{i}/{len(repos)}] {repo['label']}: {status}")
        results.append({"label": repo["label"], "ok": ok, "status": status})
    failed = [r for r in results if not r["ok"]]
    if failed:
        log(f"{len(failed)}/{len(repos)} clones failed: {[r['label'] for r in failed]}")
    return results


def run_scan_judge(repo_root):
    """Single fresh scan+judge pass. Returns dict with ok/elapsed_s/scan/judgment or ok=False/stage/error."""
    t0 = time.time()
    try:
        scan_res = subprocess.run(
            [sys.executable, str(COGNITION), str(repo_root)],
            capture_output=True, text=True, timeout=RUN_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "stage": "scan", "error": "timeout", "elapsed_s": time.time() - t0}
    if scan_res.returncode != 0:
        return {"ok": False, "stage": "scan", "error": scan_res.stderr.strip()[:800], "elapsed_s": time.time() - t0}
    try:
        scan = json.loads(scan_res.stdout)
    except json.JSONDecodeError as e:
        return {"ok": False, "stage": "scan", "error": f"invalid json: {e}", "elapsed_s": time.time() - t0}

    fd, scan_tmp_path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(scan, f)
        try:
            judge_res = subprocess.run(
                [sys.executable, str(JUDGMENT), scan_tmp_path, str(repo_root)],
                capture_output=True, text=True, timeout=RUN_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "stage": "judge", "error": "timeout", "elapsed_s": time.time() - t0}
    finally:
        os.unlink(scan_tmp_path)

    elapsed = time.time() - t0
    if judge_res.returncode != 0:
        return {"ok": False, "stage": "judge", "error": judge_res.stderr.strip()[:800], "elapsed_s": elapsed}
    try:
        judgment = json.loads(judge_res.stdout)
    except json.JSONDecodeError as e:
        return {"ok": False, "stage": "judge", "error": f"invalid json: {e}", "elapsed_s": elapsed}

    if "findings" not in judgment or not isinstance(judgment["findings"], list):
        return {"ok": False, "stage": "schema", "error": "missing/invalid findings list", "elapsed_s": elapsed}
    for f in judgment["findings"]:
        for req in ("id", "design_intent", "question_value", "risk"):
            if f.get(req) in (None, ""):
                return {"ok": False, "stage": "schema", "error": f"finding {f.get('id')} missing {req}", "elapsed_s": elapsed}

    return {"ok": True, "elapsed_s": elapsed, "scan": scan, "judgment": judgment}


def normalize_judgment(judgment):
    """Order-independent signature for byte/structural comparison across repeats."""
    findings = sorted(
        (
            {k: v for k, v in f.items() if k != "subrubric"}
            for f in judgment.get("findings", [])
        ),
        key=lambda f: f.get("id", ""),
    )
    return json.dumps({"hub": judgment.get("hub"), "findings": findings}, sort_keys=True, ensure_ascii=False)


def cmd_stability(repos):
    results = []
    for i, repo in enumerate(repos, 1):
        dest = CACHE / repo["label"]
        if not (dest / ".git").exists():
            results.append({"label": repo["label"], "ok": False, "stage": "clone", "error": "not cloned"})
            log(f"[{i}/{len(repos)}] {repo['label']}: SKIP (not cloned)")
            continue
        r = run_scan_judge(dest)
        r["label"] = repo["label"]
        r["lang_tag"] = repo["lang_tag"]
        if r["ok"]:
            r["n_findings"] = len(r["judgment"]["findings"])
            r["cost_saved_ratio"] = r["scan"]["tier_b_risk_triggered"]["cost_saved_ratio"]
            del r["scan"], r["judgment"]  # keep raw file lean; full judgment saved separately if needed
        results.append(r)
        status = "OK" if r["ok"] else f"FAIL({r.get('stage')}: {r.get('error', '')[:80]})"
        log(f"[{i}/{len(repos)}] {repo['label']}: {status} ({r.get('elapsed_s', 0):.2f}s)")
    return results


def sample_for_reproducibility(repos):
    by_lang = {}
    for r in repos:
        by_lang.setdefault(r["lang_tag"], []).append(r)
    sample = []
    for lang, rs in by_lang.items():
        sample.extend(rs[:REPRO_SAMPLE_PER_LANG])
    return sample


def cmd_reproducibility_a(repos):
    """(a) Fixed real state, same repo, REPEATS_FIXED_STATE reps -- byte-identical rate."""
    sample = sample_for_reproducibility(repos)
    results = []
    for i, repo in enumerate(sample, 1):
        dest = CACHE / repo["label"]
        if not (dest / ".git").exists():
            log(f"[{i}/{len(sample)}] {repo['label']}: SKIP (not cloned)")
            continue
        signatures = []
        errors = 0
        t0 = time.time()
        for rep in range(REPEATS_FIXED_STATE):
            r = run_scan_judge(dest)
            if not r["ok"]:
                errors += 1
                continue
            signatures.append(normalize_judgment(r["judgment"]))
        elapsed = time.time() - t0
        unique = set(signatures)
        identical_rate = None
        if signatures:
            mode_sig = max(unique, key=signatures.count)
            identical_rate = signatures.count(mode_sig) / len(signatures)
        results.append({
            "label": repo["label"], "reps": REPEATS_FIXED_STATE, "ok_reps": len(signatures),
            "errors": errors, "unique_signatures": len(unique), "identical_rate": identical_rate,
            "elapsed_s": round(elapsed, 1),
        })
        log(f"[{i}/{len(sample)}] {repo['label']}: {len(unique)} unique sig(s) over {len(signatures)}/{REPEATS_FIXED_STATE} ok reps, identical_rate={identical_rate}")
    return results


def _state_dirs():
    return {
        "idioms": ROOT / "judgment" / "idioms",
        "tier_b_suppressions": ROOT / "judgment" / "tier_b_suppressions",
        "subrubric_weights": ROOT / "judgment" / "subrubric_weights",
    }


def _backup_state(backup_root):
    backup_root.mkdir(parents=True, exist_ok=True)
    saved = {}
    for name, path in _state_dirs().items():
        if path.exists():
            dst = backup_root / name
            shutil.copytree(path, dst)
            saved[name] = dst
    return saved


def _restore_state(saved):
    for name, path in _state_dirs().items():
        if path.exists():
            shutil.rmtree(path)
        if name in saved:
            shutil.copytree(saved[name], path)


def _clear_state():
    for path in _state_dirs().values():
        if path.exists():
            shutil.rmtree(path)


def cmd_reproducibility_b(repos):
    """(b) 2 state snapshots (empty vs current-accumulated-real) x same sample --
    bucket-distribution sensitivity. Mutates real state dirs temporarily under
    try/finally with a full backup; restores unconditionally.
    """
    sample = sample_for_reproducibility(repos)
    backup_root = CACHE / "_state_backup_D119"
    if backup_root.exists():
        shutil.rmtree(backup_root)
    saved = _backup_state(backup_root)
    results = {"empty_state": [], "current_state": []}
    try:
        for snapshot_name in ("empty_state", "current_state"):
            if snapshot_name == "empty_state":
                _clear_state()
            else:
                _restore_state(saved)
            for i, repo in enumerate(sample, 1):
                dest = CACHE / repo["label"]
                if not (dest / ".git").exists():
                    continue
                r = run_scan_judge(dest)
                if r["ok"]:
                    buckets = {"design_intent": {}, "question_value": {}, "risk": {}}
                    for f in r["judgment"]["findings"]:
                        for axis in buckets:
                            buckets[axis][f[axis]] = buckets[axis].get(f[axis], 0) + 1
                    results[snapshot_name].append({
                        "label": repo["label"], "n_findings": len(r["judgment"]["findings"]), "buckets": buckets,
                    })
                else:
                    results[snapshot_name].append({"label": repo["label"], "ok": False, "error": r.get("error")})
                log(f"[{snapshot_name} {i}/{len(sample)}] {repo['label']}: {'ok' if r['ok'] else 'FAIL'}")
    finally:
        _restore_state(saved)
        log("state dirs restored from backup")
    return results


def cmd_ablation(repos):
    """P02-T1 -- structural effect of idiom_filter / tier_b_suppression / subrubric weights.
    Descriptive only: quantifies HOW MUCH each toggle changes finding count/bucket
    distribution. A true precision-weighted ranking needs the human-labeling sprint
    (D119 3.1) -- not yet available, so this reports structural deltas, not a verdict.
    """
    sample = sample_for_reproducibility(repos)  # reuse the same stratified sample
    backup_root = CACHE / "_state_backup_D119_ablation"
    if backup_root.exists():
        shutil.rmtree(backup_root)
    saved = _backup_state(backup_root)
    configs = {
        "all_on_current_state": None,   # real accumulated state, all filters active
        "idiom_filter_off": "idioms",   # clear only idioms/ -> idiom_status always "none"
        "tier_b_suppression_off": "tier_b_suppressions",  # clear only suppressions -> nothing suppressed
        "subrubric_weights_default": "subrubric_weights",  # clear only weights -> all 1.0
    }
    results = {}
    try:
        for cfg_name, clear_which in configs.items():
            _restore_state(saved)
            if clear_which:
                path = _state_dirs()[clear_which]
                if path.exists():
                    shutil.rmtree(path)
            cfg_results = []
            for i, repo in enumerate(sample, 1):
                dest = CACHE / repo["label"]
                if not (dest / ".git").exists():
                    continue
                r = run_scan_judge(dest)
                if r["ok"]:
                    cfg_results.append({
                        "label": repo["label"], "n_findings": len(r["judgment"]["findings"]),
                        "finding_ids": sorted(f["id"] for f in r["judgment"]["findings"]),
                    })
                else:
                    cfg_results.append({"label": repo["label"], "ok": False, "error": r.get("error")})
                log(f"[ablation:{cfg_name} {i}/{len(sample)}] {repo['label']}: {'ok' if r['ok'] else 'FAIL'}")
            results[cfg_name] = cfg_results
    finally:
        _restore_state(saved)
        log("state dirs restored from backup (ablation)")
    return results


def aggregate(stability, repro_a, repro_b, ablation):
    n_total = len(stability) if stability else 0
    n_ok = sum(1 for r in (stability or []) if r.get("ok"))
    stability_rate = round(n_ok / n_total, 3) if n_total else None
    speeds = [r["elapsed_s"] for r in (stability or []) if r.get("ok")]
    mean_speed = round(sum(speeds) / len(speeds), 3) if speeds else None
    cost_saved = [r["cost_saved_ratio"] for r in (stability or []) if r.get("ok")]
    mean_cost_saved = round(sum(cost_saved) / len(cost_saved), 3) if cost_saved else None

    repro_a_rates = [r["identical_rate"] for r in (repro_a or []) if r.get("identical_rate") is not None]
    mean_identical_rate = round(sum(repro_a_rates) / len(repro_a_rates), 4) if repro_a_rates else None

    summary = {
        "note": "P02 4-axis (D119). Zero NVIDIA calls. Stability=scan+judge crash-free+schema-valid rate over freshly-cloned examples/ corpus (39 repos, lms/shadowbroker/study_match excluded -- no PROVENANCE.json to reclone from). Reproducibility(a)=fixed-state 100x identical-signature rate on a 2-per-language stratified sample. Reproducibility(b)=bucket sensitivity between empty vs current-accumulated correction-hook state. Precision axis intentionally absent here -- pending human-labeling sprint (D119 3.1), see judgment_precision_labels.jsonl. Speed=mean scan+judge wall-clock.",
        "stability": {
            "n_total": n_total, "n_ok": n_ok, "rate": stability_rate,
            "failures_by_stage": _count_by(stability, "stage"),
        },
        "speed": {"mean_elapsed_s": mean_speed, "mean_cost_saved_ratio": mean_cost_saved, "n": len(speeds)},
        "reproducibility": {
            "a_fixed_state_100x": {"per_repo": repro_a, "mean_identical_rate": mean_identical_rate, "repeats": REPEATS_FIXED_STATE},
            "b_state_sensitivity": _summarize_state_sensitivity(repro_b) if repro_b else None,
        },
        "precision": {"status": "pending_human_labeling_sprint", "auto_reference_set_coverage": None},
        "ablation_P02_T1": _summarize_ablation(ablation) if ablation else None,
    }
    return summary


def _count_by(results, key):
    counts = {}
    for r in results or []:
        if not r.get("ok"):
            counts[r.get(key, "unknown")] = counts.get(r.get(key, "unknown"), 0) + 1
    return counts


def _summarize_state_sensitivity(repro_b):
    out = {}
    for snap, items in repro_b.items():
        ok_items = [i for i in items if i.get("n_findings") is not None]
        out[snap] = {
            "n_repos": len(ok_items),
            "mean_findings": round(sum(i["n_findings"] for i in ok_items) / len(ok_items), 2) if ok_items else None,
        }
    empty_n = {i["label"]: i.get("n_findings") for i in repro_b.get("empty_state", []) if i.get("n_findings") is not None}
    current_n = {i["label"]: i.get("n_findings") for i in repro_b.get("current_state", []) if i.get("n_findings") is not None}
    deltas = {label: current_n[label] - empty_n[label] for label in empty_n if label in current_n}
    out["per_repo_finding_count_delta_current_minus_empty"] = deltas
    return out


def _summarize_ablation(ablation):
    out = {}
    for cfg, items in ablation.items():
        ok_items = [i for i in items if i.get("n_findings") is not None]
        out[cfg] = {
            "n_repos": len(ok_items),
            "mean_findings": round(sum(i["n_findings"] for i in ok_items) / len(ok_items), 2) if ok_items else None,
            "total_findings": sum(i["n_findings"] for i in ok_items) if ok_items else None,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clone", action="store_true")
    ap.add_argument("--stability", action="store_true")
    ap.add_argument("--reproducibility", action="store_true")
    ap.add_argument("--ablation", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--aggregate-only", action="store_true")
    args = ap.parse_args()

    BENCH_DIR.mkdir(exist_ok=True)
    repos = discover_corpus()
    log(f"corpus: {len(repos)} repos with PROVENANCE.json ({', '.join(NO_PROVENANCE)} excluded -- no recorded source)")

    if args.aggregate_only:
        stability = json.loads(RAW_STABILITY.read_text()) if RAW_STABILITY.exists() else None
        repro = json.loads(RAW_REPRO.read_text()) if RAW_REPRO.exists() else {}
        ablation = json.loads(RAW_ABLATION.read_text()) if RAW_ABLATION.exists() else None
        summary = aggregate(stability, repro.get("a"), repro.get("b"), ablation)
        SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        log(f"wrote {SUMMARY}")
        return

    if args.clone or args.all:
        cmd_clone(repos)

    stability = None
    if args.stability or args.all:
        if not any((CACHE / r["label"] / ".git").exists() for r in repos):
            log("cache empty, cloning first")
            cmd_clone(repos)
        stability = cmd_stability(repos)
        RAW_STABILITY.write_text(json.dumps(stability, ensure_ascii=False, indent=2))
        log(f"wrote {RAW_STABILITY}")

    repro_a = repro_b = None
    if args.reproducibility or args.all:
        repro_a = cmd_reproducibility_a(repos)
        repro_b = cmd_reproducibility_b(repos)
        RAW_REPRO.write_text(json.dumps({"a": repro_a, "b": repro_b}, ensure_ascii=False, indent=2))
        log(f"wrote {RAW_REPRO}")

    ablation = None
    if args.ablation or args.all:
        ablation = cmd_ablation(repos)
        RAW_ABLATION.write_text(json.dumps(ablation, ensure_ascii=False, indent=2))
        log(f"wrote {RAW_ABLATION}")

    if args.all:
        summary = aggregate(stability, repro_a, repro_b, ablation)
        SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        log(f"wrote {SUMMARY}")


if __name__ == "__main__":
    main()
