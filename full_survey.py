# D57: first-ever live execution of the NVIDIA depth-ladder generation path,
# across every finding in every available fixture, across EVERY chat-capable
# model NVIDIA Build offers (not just a curated shortlist).
#
# WHY: README item 18 flagged this path had never been triggered live (no
# NVIDIA_API_KEY in that session). D56 picked qwen3.5-397b-a17b as default
# based on a 3-model code-review benchmark. A broader benchmark (nvidia-build
# repo) later found other models faster/more reproducible for code review --
# but this repo's actual task (schema-forced Socratic question generation via
# tool_choice) is a different capability, so the user asked for a full census
# across the whole catalog rather than reusing the code-review shortlist.
#
# COST: reuses generate_questions.py's real prompt-building and response-
# parsing functions (build_prompt, parse_nvidia_tool_response,
# _validate_depth_ladder) for authenticity, but does not call
# generate_for_finding() directly -- that function reads the module-level
# MODEL global, which isn't safe to mutate from concurrent threads testing
# different models at once. Model is passed explicitly per call instead.
#
# EXIT: if this survey's model ranking disagrees with D56's, update
# _DEFAULT_MODEL in generate_questions.py and its D56 comment, not just this
# script.
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "feedback"))
import generate_questions as gq  # noqa: E402
from nvidia_client import NvidiaRotatingClient  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402

REPO = os.path.dirname(__file__)

FIXTURES = [
    "examples/lms/judgment_output_baseline.json",
    "examples/study_match/judgment_output.json",
]

MODELS = json.load(open(os.path.join(REPO, "chat_candidates.json"), encoding="utf-8"))

findings = []
for fx in FIXTURES:
    data = json.load(open(os.path.join(REPO, fx), encoding="utf-8"))
    for f in data["findings"]:
        findings.append({**f, "_fixture": fx})

print(f"{len(findings)} findings x {len(MODELS)} models = {len(findings) * len(MODELS)} calls", flush=True)

pool = NvidiaKeyPool.from_env()
client = NvidiaRotatingClient(pool=pool)
print(f"key pool: {len(pool)} key(s), theoretical max {pool.theoretical_max_rpm} RPM", flush=True)


def call_one(model, finding):
    prompt = gq.build_prompt(finding)
    tool = gq._as_openai_tool(gq.DEPTH_LADDER_TOOL)
    t0 = time.time()
    try:
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": "depth_ladder_questions"}},
            max_tokens=1024,
            temperature=0.0,
        )
        elapsed = time.time() - t0
        questions = gq.parse_nvidia_tool_response(response)
        return {
            "model": model, "finding_id": finding["id"], "fixture": finding["_fixture"],
            "idiom_filtered": bool(finding.get("idiom_filtered")),
            "ok": True, "elapsed_s": round(elapsed, 1), "questions": questions,
        }
    except Exception as e:
        return {
            "model": model, "finding_id": finding["id"], "fixture": finding["_fixture"],
            "idiom_filtered": bool(finding.get("idiom_filtered")),
            "ok": False, "elapsed_s": round(time.time() - t0, 1), "error": str(e),
        }


jobs = [(m, f) for m in MODELS for f in findings]
results = []
with ThreadPoolExecutor(max_workers=12) as executor:
    futures = {executor.submit(call_one, m, f): (m, f["id"]) for m, f in jobs}
    done = 0
    for fut in as_completed(futures):
        r = fut.result()
        results.append(r)
        done += 1
        tag = "OK " if r["ok"] else "ERR"
        print(f"[{done}/{len(jobs)}] {tag} {r['model']:45s} {r['finding_id']:45s} {r['elapsed_s']:>6.1f}s", flush=True)

out_path = os.path.join(REPO, "full_survey_results.json")
json.dump(results, open(out_path, "w"), ensure_ascii=False, indent=2)
print(f"saved -> {out_path}", flush=True)
