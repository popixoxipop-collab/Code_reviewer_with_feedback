"""라이브 버스트 검증: 단일 키 한도(40/min)를 넘는 ~120/min으로 84콜 실발사.

로테이션이 실제로 작동하면 키당 ~12콜(<40/min)이라 429가 없어야 하고,
로테이션이 고장났다면(한 키에 몰림) 40콜 이후 429가 나와야 한다.
대상: step-3.5-flash (오늘 하루 종일 가장 안정, 응답 ~2s).
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.expanduser("~/Desktop/Code_reviewer_with_feedback")
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "feedback"))
from timeout_config import DEFAULT_MAX_TOKENS  # noqa: E402
from nvidia_key_pool import NvidiaKeyPool  # noqa: E402

API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "stepfun-ai/step-3.5-flash"
N_CALLS = 84
SUBMIT_INTERVAL_S = 0.5  # 2/s = 120/min 발사 페이스

pool = NvidiaKeyPool.from_env()
key_alias = {}
for i in range(1, 20):
    v = os.environ.get(f"NVIDIA_API_KEY_{i}")
    if v:
        key_alias[v] = f"key_{i}"

lock = threading.Lock()
by_key = Counter()
by_status = Counter()
lat = []


def one(i):
    key = pool.acquire(MODEL)
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": f"Say OK. ({i})"}],
        "max_tokens": DEFAULT_MAX_TOKENS,
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60):  # timeout-guard: allow -- burst probe
            status = 200
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:
        status = -1
    with lock:
        by_key[key_alias.get(key, "?")] += 1
        by_status[status] += 1
        lat.append(time.time() - t0)


t_start = time.time()
with ThreadPoolExecutor(max_workers=12) as ex:
    futs = []
    for i in range(N_CALLS):
        futs.append(ex.submit(one, i))
        time.sleep(SUBMIT_INTERVAL_S)
    for f in futs:
        f.result()
wall = time.time() - t_start

rpm = N_CALLS / wall * 60
print(f"calls={N_CALLS} wall={wall:.1f}s effective={rpm:.0f}/min (단일 키 한도 40/min의 {rpm/40:.1f}배)")
print(f"status: {dict(by_status)}")
print(f"per-key: {dict(sorted(by_key.items()))}")
print(f"latency p50={sorted(lat)[len(lat)//2]:.1f}s max={max(lat):.1f}s")
ok = by_status.get(200, 0) == N_CALLS
print("VERDICT:", "PASS -- 로테이션이 라이브로 40rpm 초과 처리량을 감당함" if ok else "FAIL -- 429/에러 발생, 분포 확인 필요")
sys.exit(0 if ok else 1)
