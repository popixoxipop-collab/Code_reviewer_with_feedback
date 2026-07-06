# Re-run only the (model, finding) pairs that errored in full_survey_results.json,
# now that D11 fixes the pool's false per-key (instead of per-model) throttling.
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

prior = json.load(open(os.path.join(REPO, "full_survey_results.json"), encoding="utf-8"))
failed_keys = {(r["model"], r["finding_id"]) for r in prior if not r["ok"]}
print(f"{len(failed_keys)} (model, finding) pairs failed previously -- re-running those only", flush=True)

findings_by_id = {}
for fx in FIXTURES:
    data = json.load(open(os.path.join(REPO, fx), encoding="utf-8"))
    for f in data["findings"]:
        findings_by_id[f["id"]] = {**f, "_fixture": fx}

pool = NvidiaKeyPool.from_env()
client = NvidiaRotatingClient(pool=pool)


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


jobs = [(m, findings_by_id[fid]) for (m, fid) in failed_keys]
results = []
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = {executor.submit(call_one, m, f): (m, f["id"]) for m, f in jobs}
    done = 0
    for fut in as_completed(futures):
        r = fut.result()
        results.append(r)
        done += 1
        tag = "OK " if r["ok"] else "ERR"
        print(f"[{done}/{len(jobs)}] {tag} {r['model']:45s} {r['finding_id']:45s} {r['elapsed_s']:>6.1f}s", flush=True)

# merge: replace the old failed entries with the new results
by_key = {(r["model"], r["finding_id"]): r for r in prior}
for r in results:
    by_key[(r["model"], r["finding_id"])] = r

merged = list(by_key.values())
json.dump(merged, open(os.path.join(REPO, "full_survey_results.json"), "w"), ensure_ascii=False, indent=2)
print(f"merged and saved -> full_survey_results.json ({len(merged)} total)", flush=True)
