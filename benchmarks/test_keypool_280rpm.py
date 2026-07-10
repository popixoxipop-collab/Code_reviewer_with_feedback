"""NvidiaKeyPool 280/min 검증 (오프라인, HTTP 0건) -- 가짜 시계로 윈도우 로직을 직접 시험.

검증 항목:
  A. 7키 x 40 = 280 grant가 한 윈도우(60s) 안에서 블로킹 없이 전부 발급되는가
  B. 281번째는 블로킹되고, 윈도우가 슬라이드되면(60s 경과) 즉시 발급되는가
  C. 키 분배가 공정한가 (키당 정확히 40)
  D. 모델별 예산 격리 -- 모델A 포화가 모델B에 영향 없는가
  E. 실시계 스모크 -- 280 acquire가 인위적 직렬화 없이 즉시(<1s) 끝나는가
"""
import os
import sys
import time as real_time

sys.path.insert(0, os.path.expanduser("~/Desktop/Code_reviewer_with_feedback/feedback"))
import nvidia_key_pool as nkp


class FakeClock:
    def __init__(self):
        self.now = 1000.0
    def time(self):
        return self.now
    def monotonic(self):
        return self.now
    def sleep(self, s):
        self.now += s


def make_pool(n=7):
    return nkp.NvidiaKeyPool([f"key_{i}" for i in range(1, n + 1)], capacity_per_minute=40)


results = []

# --- A+C: 280 grants in one window, fair distribution ---
clock = FakeClock()
nkp.time = clock  # module-level `import time` swap
pool = make_pool()
grants = [pool.acquire("model/x") for _ in range(280)]
elapsed_fake = clock.now - 1000.0
from collections import Counter
dist = Counter(grants)
ok_a = elapsed_fake == 0.0 and len(grants) == 280
ok_c = set(dist.values()) == {40}
results.append(("A: 280 grants no-block in one window", ok_a, f"fake-elapsed={elapsed_fake}s"))
results.append(("C: fair distribution 40/key", ok_c, dict(dist)))

# --- B: 281st blocks until window slides ---
blocked_at = clock.now
key281 = pool.acquire("model/x", max_wait_s=120.0)
waited = clock.now - blocked_at
ok_b = 59.0 <= waited <= 61.5 and key281 in dist
results.append(("B: 281st waits ~60s for window slide", ok_b, f"waited={waited:.2f}s"))

# --- D: per-model isolation ---
t0 = clock.now
key_b = pool.acquire("model/y")
ok_d = (clock.now - t0) == 0.0
results.append(("D: model-B unaffected by model-A saturation", ok_d, f"grant={key_b}"))

# --- E: real-clock smoke, no artificial serialization ---
nkp.time = real_time
pool2 = make_pool()
t0 = real_time.time()
for _ in range(280):
    pool2.acquire("model/z")
wall = real_time.time() - t0
ok_e = wall < 1.0
results.append(("E: 280 real acquires < 1s wall", ok_e, f"wall={wall:.3f}s"))

print(f"pool.theoretical_max_rpm = {make_pool().theoretical_max_rpm}")
all_ok = True
for name, ok, detail in results:
    all_ok &= ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})")
print(f"\n{'ALL PASS' if all_ok else 'FAILURES PRESENT'}")
sys.exit(0 if all_ok else 1)
