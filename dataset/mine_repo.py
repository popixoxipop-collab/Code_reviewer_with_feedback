"""D70: 언어별 finding corpus 확장 — 외부 GitHub repo를 scan+score 파이프라인에 통과시켜
examples/<lang>/<repo_slug>/ 에 기존 fixture(lms, study_match)와 동일한 형식으로 저장한다.

WHY: full_survey.py:36-47의 FIXTURES가 study_match/lms(둘 다 JS/TS) 두 개뿐이라 finding
     다양성이 12개로 고정돼 있었음. 스캐너 자체(two_tier_scan.py/score_findings.py)는
     JS/TS/Python/Java/C-C++ 4개 언어군을 이미 지원하는데 실제로 JS/TS 외 언어로 돌려본
     적이 없어서 "다른 언어에서도 의미 있는 finding이 나오는가"가 검증되지 않은 상태였음.
COST: shallow clone(--depth 1)이라 git history 기반 신호(예: 커밋 빈도)는 애초에 못 씀 —
     scan/score 둘 다 git history를 안 쓰므로 이 pass엔 영향 없음.
EXIT: 언어당 repo를 늘리고 싶으면 REPOS 딕셔너리에 추가만 하면 됨. clone 방식을
     `git clone`에서 `gh repo clone`으로 바꾸고 싶으면 _clone()만 교체.

usage: python3 dataset/mine_repo.py <git_url> <lang_tag> [repo_slug]
"""
import json
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES_DIR = os.path.join(REPO_ROOT, "examples")


def _clone(git_url, dest):
    subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", git_url, dest],
        check=True,
    )


def _run_scan(repo_dir):
    out = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "cognition", "two_tier_scan.py"), repo_dir],
        check=True, capture_output=True, text=True,
    )
    return json.loads(out.stdout)


def _run_score(scan_result_path, repo_dir):
    out = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "judgment", "score_findings.py"), scan_result_path, repo_dir],
        check=True, capture_output=True, text=True,
    )
    return json.loads(out.stdout)


def mine(git_url, lang_tag, repo_slug=None):
    repo_slug = repo_slug or git_url.rstrip("/").split("/")[-1].replace(".git", "")
    out_dir = os.path.join(EXAMPLES_DIR, lang_tag, repo_slug)
    os.makedirs(out_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = os.path.join(tmp, repo_slug)
        print(f"[clone] {git_url} -> {clone_dir}", flush=True)
        _clone(git_url, clone_dir)

        scan_result = _run_scan(clone_dir)
        n_files = scan_result["total_source_files"]
        print(f"[scan] total_source_files={n_files}", flush=True)
        if n_files == 0:
            print("[abort] 0 source files matched SRC_EXTS -- pick a different repo", flush=True)
            return None

        scan_path = os.path.join(out_dir, "scan_output.json")
        with open(scan_path, "w", encoding="utf-8") as f:
            json.dump(scan_result, f, ensure_ascii=False, indent=2)

        judgment_result = _run_score(scan_path, clone_dir)
        judgment_path = os.path.join(out_dir, "judgment_output.json")
        with open(judgment_path, "w", encoding="utf-8") as f:
            json.dump(judgment_result, f, ensure_ascii=False, indent=2)

        # D70: 소스가 임시디렉토리라 clone 자체는 재현 안 됨 -- git_url/커밋 없이 결과만
        #   남으면 나중에 "이 finding이 어디서 왔는지" 추적이 끊긴다는 게 D4/D18 계보와
        #   같은 문제라 provenance를 함께 저장한다.
        head = subprocess.run(
            ["git", "-C", clone_dir, "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        with open(os.path.join(out_dir, "PROVENANCE.json"), "w", encoding="utf-8") as f:
            json.dump({"git_url": git_url, "commit": head, "lang_tag": lang_tag}, f, indent=2)

        n_findings = len(judgment_result["findings"])
        print(f"[score] {n_findings} findings -> {judgment_path}", flush=True)
        return judgment_path


def main():
    if len(sys.argv) < 3:
        print("usage: mine_repo.py <git_url> <lang_tag> [repo_slug]", file=sys.stderr)
        sys.exit(1)
    git_url = sys.argv[1]
    lang_tag = sys.argv[2]
    repo_slug = sys.argv[3] if len(sys.argv) > 3 else None
    mine(git_url, lang_tag, repo_slug)


if __name__ == "__main__":
    main()
