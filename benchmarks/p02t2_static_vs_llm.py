"""D119 3.2 (P02-T2) -- static determinism (P02) vs pure-LLM MEAS-02 extractor, re-verified.

D65 redesigned Phase 2 around the spec-literal pure-LLM MEAS-02 extractor
(judgment/meas02_decision_point_extractor.py); D69 benchmarked it once and found it
covers single-file findings well but structurally misses cross-file signals (the
Study-Match-/Competitions.tsx isolation case). That benchmark's CASES pointed at a
prior session's scratch clones which no longer exist -- this script is NOT an edit
of benchmarks/meas02_run_benchmark.py (D65-D69's historical artifact stays as-is);
it is a new comparison using the current judgment_4axis_benchmark.py corpus cache
(examples/ repos, freshly cloned at pinned commits) so the D69 finding can be
re-checked under the same standardized methodology as P01/P02/P03.

Difference from D69: those 4 cases had team-authored requirements.txt per project.
These 7 cases are arbitrary third-party OSS repos with no curated requirements doc,
so a single generic requirements string is used for all cases -- noted explicitly
in the output, not silently treated as equivalent to D69's design.

Cost: 7 cases x run1/run2 x 1 model (qwen3-next-80b, team Locked) = 14 NVIDIA calls.

Usage: python3 benchmarks/p02t2_static_vs_llm.py
"""
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# D119 3.2: nvidia_client.py/nvidia_key_pool.py only exist under feedback/ (verified --
#   meas02_run_benchmark.py's judgment/+benchmarks/-only sys.path insert doesn't actually
#   reach them; that file's import would currently fail if run as-is, a separate latent
#   bug in the D65-D69 artifact this script deliberately doesn't touch).
sys.path.insert(0, os.path.join(REPO, "feedback"))
sys.path.insert(0, os.path.join(REPO, "judgment"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)  # timeout_config.py lives at repo root

import meas02_decision_point_extractor as extractor  # noqa: E402
from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402
from harness import run_concurrent, print_progress  # noqa: E402
from timeout_config import DEFAULT_TIMEOUT_S, DEFAULT_MAX_TOKENS  # noqa: E402

MODEL = "qwen/qwen3-next-80b-a3b-instruct"  # 팀 Locked -- 3.2 Q4 확정: 비교는 재논쟁이 아니라 재검증
CACHE = os.environ.get(
    "JUDGMENT_BENCH_CACHE",
    "/private/tmp/claude-501/-Users-xox/da999462-3e63-4846-b385-b4fd0a1fbc86/scratchpad/judgment_corpus_cache",
)
GENERIC_REQUIREMENTS = (
    "이 파일이 속한 오픈소스 프로젝트의 일반적인 코드 품질/설계/보안 기준. "
    "이 케이스는 팀 자체 프로젝트(D69의 Study-Match-/LMS)와 달리 임의 서드파티 OSS repo라 "
    "프로젝트별 요구사항 문서가 없어 이 공통 문구를 사용함 -- D69와 완전히 동일 조건은 아님."
)

# D119 3.2: P02(cognition/judgment)이 이미 찾은 finding을 참고 세트로 삼아, 같은 파일을
#   순수 LLM 추출기에 넣었을 때 겹치는지 본다(D66 명명: coverage이지 recall 아님).
CASES = [
    {
        "label": "c_cpp/EasyQtSql:navtree.js",
        "file": f"{CACHE}/c_cpp/EasyQtSql/docs/navtree.js",
        "reference_keywords": ["eval", "동적 실행", "html 삽입", "xss"],  # substring-match keywords only, not a call
        "reference_note": "P02: tier-b-risk:navtree.js:dangerous-html (eval( 패턴)",
    },
    {
        "label": "c_cpp/libinotify-kqueue:utils.h",
        "file": f"{CACHE}/c_cpp/libinotify-kqueue/utils.h",
        "reference_keywords": ["공유", "여러", "허브", "fan_in", "재사용", "header"],
        "reference_note": "P02: architecture-diffusion:utils.h (fan_in=8, 여러 컴포넌트 공유)",
    },
    {
        "label": "c_cpp/EasyQtSql:ParamDirectionWrapper.h",
        "file": f"{CACHE}/c_cpp/EasyQtSql/EasyQtSql/EasyQtSql_ParamDirectionWrapper.h",
        "reference_keywords": ["고립", "연결", "허브", "isolat", "wrapper", "미사용"],
        "reference_note": "P02: cognition-isolation:EasyQtSql_ParamDirectionWrapper.h (허브 미연결, cross-file 신호 -- "
                           "D69가 이 종류 신호를 단일파일 추출기가 원천적으로 못 잡는다고 실측한 바로 그 패턴)",
    },
    {
        "label": "java/Modern-API...:Auth.js",
        "file": f"{CACHE}/java/Modern-API-Development-with-Spring-6-and-Spring-Boot-3/Chapter07/ecomm-ui/src/api/Auth.js",
        "reference_keywords": ["uid", "email", "stringify", "인증", "throw", "authinfo"],
        "reference_note": "P02: tier-b-risk:Auth.js (인증정보 JSON.stringify 유출) -- 단일 파일 신호, 커버 가능해야 함",
    },
    {
        "label": "java/springboot_security...:BaseEntity.java",
        "file": f"{CACHE}/java/springboot_security_restful_api/src/main/java/com/mingzuozhibi/commons/base/BaseEntity.java",
        "reference_keywords": ["공유", "여러", "허브", "fan_in", "재사용", "base", "상속"],
        "reference_note": "P02: architecture-diffusion:BaseEntity.java (fan_in=3, 여러 컴포넌트 공유)",
    },
    {
        "label": "javascript/FarmAssist:AppImage.jsx",
        "file": f"{CACHE}/javascript/FarmAssist/src/components/AppImage.jsx",
        "reference_keywords": ["고립", "연결", "허브", "isolat", "미사용", "이미지"],
        "reference_note": "P02: cognition-isolation:AppImage.jsx (허브 AppIcon.jsx로 가는 edge 없음, cross-file 신호)",
    },
    {
        "label": "python/whoogle-search:cse_client.py",
        "file": f"{CACHE}/python/whoogle-search/app/services/cse_client.py",
        "reference_keywords": ["api_key", "시크릿", "secret", "하드코딩", "credential"],
        "reference_note": "P02: tier-b-risk:cse_client.py:secret (시크릿 패턴 매치, 오탐 가능성 자체가 P02의 flag)",
    },
]


def _load_case_inputs(case):
    with open(case["file"], encoding="utf-8", errors="ignore") as f:
        code_snippet = f.read()
    return os.path.basename(case["file"]), code_snippet, GENERIC_REQUIREMENTS


def coverage(decision_points, keywords):
    haystack = " ".join(f"{p.get('judgment_type', '')} {p.get('evidence', '')}" for p in decision_points).lower()
    return any(kw.lower() in haystack for kw in keywords)


def call_one(job):
    case, run_tag = job
    file_name, code_snippet, requirements = _load_case_inputs(case)
    t0 = time.time()
    try:
        response = CLIENT.chat(
            model=MODEL,
            messages=[{"role": "user", "content": extractor.build_extraction_prompt(file_name, code_snippet, requirements, None)}],
            tools=[extractor._as_openai_tool(extractor.DECISION_POINT_TOOL)],
            tool_choice={"type": "function", "function": {"name": "extract_decision_points"}},
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=0.0,
        )
        elapsed = time.time() - t0
        result = extractor.parse_nvidia_tool_response(response)
        return {
            "model": MODEL, "label": case["label"], "run": run_tag, "ok": True,
            "elapsed_s": round(elapsed, 1), "decision_points": result["decision_points"],
            "n_points": len(result["decision_points"]),
            "covers_p02_reference": coverage(result["decision_points"], case["reference_keywords"]),
            "p02_reference_note": case["reference_note"],
        }
    except Exception as e:
        return {
            "model": MODEL, "label": case["label"], "run": run_tag, "ok": False,
            "elapsed_s": round(time.time() - t0, 1), "error": str(e),
        }


def summarize(results):
    by_label = {}
    for r in results:
        by_label.setdefault(r["label"], []).append(r)
    summary = {}
    for label, rs in by_label.items():
        ok = [r for r in rs if r["ok"]]
        summary[label] = {
            "runs": len(rs), "ok_runs": len(ok),
            "reference_note": rs[0].get("p02_reference_note") if rs else None,
            "covers_p02_reference": [r["covers_p02_reference"] for r in ok],
            "n_points_mean": round(sum(r["n_points"] for r in ok) / len(ok), 1) if ok else None,
            "mean_elapsed_s": round(sum(r["elapsed_s"] for r in ok) / len(ok), 1) if ok else None,
            "is_cross_file_signal": "cognition-isolation" in (rs[0].get("p02_reference_note") or "") or "architecture-diffusion" in (rs[0].get("p02_reference_note") or ""),
        }
    n_single_file = sum(1 for s in summary.values() if not s["is_cross_file_signal"])
    n_single_file_covered = sum(1 for s in summary.values() if not s["is_cross_file_signal"] and any(s["covers_p02_reference"]))
    n_cross_file = sum(1 for s in summary.values() if s["is_cross_file_signal"])
    n_cross_file_covered = sum(1 for s in summary.values() if s["is_cross_file_signal"] and any(s["covers_p02_reference"]))
    return {
        "per_case": summary,
        "single_file_signal_coverage": f"{n_single_file_covered}/{n_single_file}",
        "cross_file_signal_coverage": f"{n_cross_file_covered}/{n_cross_file}",
        "d69_finding_reproduced": n_cross_file_covered < n_cross_file,
    }


def main():
    global CLIENT
    pool = NvidiaKeyPool.from_env()
    CLIENT = NvidiaRotatingClient(pool=pool, timeout_s=DEFAULT_TIMEOUT_S)

    jobs = [(c, "run1") for c in CASES] + [(c, "run2") for c in CASES]
    print(f"=== {MODEL}: {len(jobs)} calls (7 cases x 2 runs) ===", flush=True)
    results = run_concurrent(jobs, call_one, max_workers=4, progress=print_progress)

    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "p02t2_raw.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    summary = summarize(results)
    with open(os.path.join(out_dir, "p02t2_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
