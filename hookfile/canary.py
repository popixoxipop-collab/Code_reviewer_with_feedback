"""D123 layer 1+4 -- canary token issue/scan utility for Hook File contamination detection.

D96 계보: QUOTA_EXHAUSTED_MARKERS의 "명시적 마커 가드" 패턴을 재사용. 모든 Hook File에
고유 canary_uuid를 심고, 측정 경로(질문생성/채점/스캔 입력 조립)가 페이로드 전송 직전
canary 존재를 스캔한다 -- 발견 즉시 abort. 실험 종료 후에는 전체 프롬프트 스냅샷 로그에
대해 같은 스캔을 다시 돌려 "오염 0건"을 사후 증명할 수 있다(layer 4, D96/D97 전수조사 계보).

Usage:
  python3 hookfile/canary.py issue <student_id> <version>
  python3 hookfile/canary.py scan <text_or_-_for_stdin>
"""
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO / "hookfile" / "_canary_registry.jsonl"
CANARY_RE = re.compile(r"HOOKFILE-CANARY-[0-9a-f-]{36}")


class ContaminationError(RuntimeError):
    """Raised by measurement call sites when a canary is found in an about-to-send payload."""


def issue_canary(student_id, version):
    """새 Hook File 버전 생성 시 1회 호출 -- 전역 유일 토큰 발급+레지스트리 기록."""
    token = f"HOOKFILE-CANARY-{uuid.uuid4()}"
    entry = {
        "canary_uuid": token, "student_id": student_id, "version": version,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return token


def all_issued_canaries():
    """지금까지 발급된 모든 canary -- 스캔 시 대조 대상."""
    if not REGISTRY_PATH.exists():
        return set()
    tokens = set()
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                tokens.add(json.loads(line)["canary_uuid"])
    return tokens


def scan_for_contamination(payload_text):
    """측정 페이로드(전송 직전)를 스캔. 반환: (contaminated, matched_tokens).

    발급된 canary와 일치하는 경우뿐 아니라, canary 형태이지만 레지스트리에 없는
    문자열(비정상 상태 -- 발급 안 된 토큰이 어떻게 페이로드에 들어갔는지 자체가
    의심스러움)도 함께 오염으로 취급한다.
    """
    found = set(CANARY_RE.findall(payload_text))
    if not found:
        return False, []
    issued = all_issued_canaries()
    matched = sorted(found & issued)
    unregistered = sorted(found - issued)
    return True, matched + unregistered


def assert_clean(payload_text, context=""):
    """측정 콜 사이트(질문생성/채점/스캔 프롬프트 조립 함수)가 전송 직전 호출.
    D123 측정기 불변식의 코드 레벨 강제 지점 -- 이 함수를 호출하지 않는 측정 경로는
    불변식이 지켜지지 않는다(코드 리뷰 시 확인 대상)."""
    contaminated, tokens = scan_for_contamination(payload_text)
    if contaminated:
        raise ContaminationError(
            f"canary found in measurement payload{f' ({context})' if context else ''}: {tokens}"
        )


def full_corpus_audit(prompt_log_paths):
    """D123 layer 4 -- 실험 종료 후 전체 프롬프트 스냅샷 로그(D96/D97 전수조사 계보)에
    대해 사후 전수 스캔. 발급된 canary가 단 하나라도 로그에서 발견되면 오염 확정."""
    issued = all_issued_canaries()
    hits = []
    for path in prompt_log_paths:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        found = set(CANARY_RE.findall(text)) & issued
        if found:
            hits.append({"path": str(path), "canaries": sorted(found)})
    return {"clean": not hits, "n_logs_scanned": len(prompt_log_paths), "contaminated_logs": hits}


def main():
    if len(sys.argv) < 2:
        print("usage: canary.py issue <student_id> <version> | canary.py scan <text|->", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "issue":
        student_id, version = sys.argv[2], int(sys.argv[3])
        token = issue_canary(student_id, version)
        print(json.dumps({"canary_uuid": token}, ensure_ascii=False))
    elif cmd == "scan":
        text = sys.stdin.read() if sys.argv[2] == "-" else sys.argv[2]
        contaminated, tokens = scan_for_contamination(text)
        print(json.dumps({"contaminated": contaminated, "tokens": tokens}, ensure_ascii=False))
        sys.exit(1 if contaminated else 0)
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
