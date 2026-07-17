"""No-network structural check that the D195 scan-exclusion constants stay in sync.

SKIP_DIRS / SKIP_DIR_PREFIXES / SKIP_DIR_SUFFIXES are intentionally duplicated across
cognition/two_tier_scan.py, judgment/score_findings.py, and judgment/idiom_filter.py
(idiom_filter.py can't import them from score_findings.py -- circular import, both files
already import from each other). docs/lab/prompt_manifest.json's p02-1 stage duplicates
them a fourth time as the web lab's editable defaults. Nothing enforced any of these four
copies staying equal, and they drifted once already: D195 introduced 16 new SKIP_DIRS
entries into the three Python files but the browser-side download filter in
docs/lab/p02-engine.js / docs/lab/p02-runner.js kept a separate, un-synced fifth copy
hardcoded at the old 10-entry value (caught by an independent Fable review, not by any
test -- this file exists so the next drift is caught by CI instead).

Also exercises docs/lab/webtool_driver.py's apply_overrides() broadcast: an override sent
under the "two_tier_scan" bucket (the only bucket the UI ever uses for these, since p02-1
maps only to two_tier_scan) must reach score_findings and idiom_filter too, or a trainee's
SKIP_DIRS edit silently produces an internally-inconsistent scan.

Run: python3 judgment/smoke_test_scan_constants_sync.py
"""
import importlib.util
import json
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(THIS_DIR)
sys.path.insert(0, THIS_DIR)  # judgment/ -- score_findings, idiom_filter, importance_rank
sys.path.insert(0, os.path.join(REPO_ROOT, "cognition"))  # two_tier_scan
sys.path.insert(0, os.path.join(REPO_ROOT, "docs", "lab"))  # webtool_driver

import idiom_filter  # noqa: E402
import score_findings  # noqa: E402


def _load_two_tier_scan():
    spec = importlib.util.spec_from_file_location(
        "two_tier_scan", os.path.join(REPO_ROOT, "cognition", "two_tier_scan.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest_p02_1_params():
    with open(os.path.join(REPO_ROOT, "docs", "lab", "prompt_manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    stage = manifest["pipelines"]["p02"]["stages"][0]
    assert stage["id"] == "p02-1", f"expected stage[0] to be p02-1, got {stage['id']!r}"
    return {p["key"]: p for p in stage["params"]}


def check(label, fn):
    try:
        fn()
    except AssertionError as e:
        print(f"FAIL: {label} -- {e}")
        sys.exit(1)
    print(f"PASS: {label}")


def test_skip_dirs_identical_across_three_modules():
    tts = _load_two_tier_scan()
    assert tts.SKIP_DIRS == score_findings.SKIP_DIRS == idiom_filter.SKIP_DIRS, (
        tts.SKIP_DIRS, score_findings.SKIP_DIRS, idiom_filter.SKIP_DIRS
    )
    assert len(score_findings.SKIP_DIRS) == 26, f"expected 26 entries, got {len(score_findings.SKIP_DIRS)}"


def test_skip_dir_prefixes_and_suffixes_identical_across_three_modules():
    tts = _load_two_tier_scan()
    assert tts.SKIP_DIR_PREFIXES == score_findings.SKIP_DIR_PREFIXES == idiom_filter.SKIP_DIR_PREFIXES
    assert tts.SKIP_DIR_SUFFIXES == score_findings.SKIP_DIR_SUFFIXES == idiom_filter.SKIP_DIR_SUFFIXES


def test_generated_filename_re_identical_where_defined():
    # idiom_filter.py deliberately has no GENERATED_FILENAME_RE (D195): every _find_file_content
    # call site resolves an already-vetted finding's filename, never a fresh scan candidate --
    # see README's D195 entry for the traced call sites.
    tts = _load_two_tier_scan()
    assert tts.GENERATED_FILENAME_RE.pattern == score_findings.GENERATED_FILENAME_RE.pattern
    assert not hasattr(idiom_filter, "GENERATED_FILENAME_RE")


def test_manifest_defaults_match_live_module_constants():
    tts = _load_two_tier_scan()
    params = _manifest_p02_1_params()
    assert set(params["SKIP_DIRS"]["default"]) == score_findings.SKIP_DIRS
    assert tuple(params["SKIP_DIR_PREFIXES"]["default"]) == score_findings.SKIP_DIR_PREFIXES
    assert tuple(params["SKIP_DIR_SUFFIXES"]["default"]) == score_findings.SKIP_DIR_SUFFIXES
    assert params["GENERATED_FILENAME_RE"]["default"] == tts.GENERATED_FILENAME_RE.pattern


def test_js_download_filters_no_longer_hardcode_a_separate_copy():
    # Regression guard for the exact bug this file exists because of: p02-engine.js and
    # p02-runner.js used to declare their own `SKIP_DIR_NAMES` Set literal instead of
    # resolving it from the manifest, so it silently missed the D195 update. This doesn't
    # exercise the browser runtime (no JS engine here) -- it only asserts the drift-prone
    # hardcoded literal is gone and the manifest-resolving call site is present.
    for rel in ("docs/lab/p02-engine.js", "docs/lab/p02-runner.js"):
        text = open(os.path.join(REPO_ROOT, rel), encoding="utf-8").read()
        assert "const SKIP_DIR_NAMES" not in text, f"{rel} still declares the old hardcoded SKIP_DIR_NAMES copy"
        assert 'LabApp.resolveParam("p02", "p02-1", "SKIP_DIRS")' in text, (
            f"{rel} should resolve SKIP_DIRS from the manifest, not a hardcoded literal"
        )


def test_apply_overrides_broadcasts_shared_constants_to_all_three_modules():
    import webtool_driver

    tts = _load_two_tier_scan()
    sys.modules["two_tier_scan"] = tts  # webtool_driver's `import two_tier_scan` must hit this instance

    overrides_json = json.dumps({"two_tier_scan": {"SKIP_DIRS": ["node_modules"], "SKIP_DIR_PREFIXES": [], "SKIP_DIR_SUFFIXES": []}})
    applied = webtool_driver.apply_overrides(overrides_json)

    assert tts.SKIP_DIRS == {"node_modules"}, tts.SKIP_DIRS
    assert score_findings.SKIP_DIRS == {"node_modules"}, "override did not reach score_findings"
    assert idiom_filter.SKIP_DIRS == {"node_modules"}, "override did not reach idiom_filter (the exact D195 bug)"
    assert isinstance(score_findings.SKIP_DIRS, set), "type parity with the original module attribute must be kept"
    assert any("idiom_filter.SKIP_DIRS" in a for a in applied), applied

    # restore defaults so this test doesn't leak mutated globals into any test run after it
    for mod in (tts, score_findings, idiom_filter):
        mod.SKIP_DIRS = {
            "node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv",
            "static", "vendor", "vendored", "target", ".pytest_cache", ".mypy_cache",
            ".tox", ".eggs", ".next", ".nuxt", ".output", ".nitro", ".svelte-kit",
            ".turbo", ".parcel-cache", "coverage", "storybook-static", ".vs", "DerivedData",
        }


if __name__ == "__main__":
    check("SKIP_DIRS identical across two_tier_scan/score_findings/idiom_filter", test_skip_dirs_identical_across_three_modules)
    check("SKIP_DIR_PREFIXES/SUFFIXES identical across the three modules", test_skip_dir_prefixes_and_suffixes_identical_across_three_modules)
    check("GENERATED_FILENAME_RE identical where defined (absent from idiom_filter by design)", test_generated_filename_re_identical_where_defined)
    check("prompt_manifest.json p02-1 defaults match live module constants", test_manifest_defaults_match_live_module_constants)
    check("JS download filters resolve from the manifest, not a separate hardcoded copy", test_js_download_filters_no_longer_hardcode_a_separate_copy)
    check("apply_overrides broadcasts SKIP_DIRS-family edits to all three modules", test_apply_overrides_broadcasts_shared_constants_to_all_three_modules)
    print("\nAll structural checks passed.")
