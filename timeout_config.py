# D98: single source of truth for benchmark timeouts (user request -- centralize
#   instead of scattering LLAMA_TIMEOUT_S/NEMOTRON_TIMEOUT_S/SONNET_TIMEOUT_S as
#   separate hardcoded constants per script, which is how D94b's timeout tuning
#   ended up inconsistent across files).
#   WHY: llama-3.3-70b-instruct's worker-queue overload (D94, HTTP 503 "153/16")
#        showed real single-call latency well past NVIDIA's default 120s under
#        load, confirmed again by a controlled 7-key concurrent test (4/7 timed
#        out at 120s even with each request on a fully distinct API key --
#        ruling out per-key contention, D98). One generous number avoids
#        re-litigating "what should the timeout be" per script.
#   COST: a single global value can't express "this call is usually fast, time
#        it out aggressively" -- if a script needs a genuinely short timeout
#        for a different reason (e.g. a liveness probe), it should use its own
#        local constant instead of importing this one, not lower this value.
#   EXIT: change DEFAULT_TIMEOUT_S here; every importer picks it up. No other
#        file should hardcode a timeout number for NVIDIA/claude -p calls.
DEFAULT_TIMEOUT_S = 600.0
