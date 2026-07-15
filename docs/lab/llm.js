// D-C (PLAN.md): integrate.api.nvidia.com has no Access-Control-Allow-Origin header
// (verified 2026-07-14) -- direct browser calls are impossible, so every LLM call in
// this tool goes through a proxy the user configures (worker/nvidia-proxy.js is the
// reference implementation, deployable by anyone on the team). This file never talks
// to NVIDIA directly and never persists the key past the in-memory config object.
//
// D-H (2026-07-14, README D143): submits a job and polls for it instead of holding one
// HTTP request open. D-E's streaming attempt only helped once NVIDIA started sending
// bytes -- it couldn't help when NVIDIA was slow to send the FIRST byte, which turned out
// to be the actual failure mode (confirmed live: qwen3-next-80b took 92s on one call and
// didn't answer at all within 150s on another -- normal variance for this tier per
// feedback/nvidia_client.py's own 600s timeout and D98 history, not an outage). No
// client-facing request can survive that wait, streamed or not. So this doesn't try to --
// worker/nvidia-proxy.js now answers the POST almost instantly with a job_id and does the
// real call in a Cloudflare Queue consumer (up to 15 minutes, no client watching), and
// this file polls GET ?job=<id> until it's done. callPromptStage()/generateQuestion() etc.
// still just get back a plain complete string or parsed object -- this file is the only
// place that knows the transport is submit-and-poll now, same as it was the only place
// that knew about streaming before that.
//
// D-I (2026-07-14, worker/nvidia-proxy.js): the consumer now retries a failed attempt
// (up to MAX_ATTEMPTS=3, each with its own fresh 600s-per-attempt / 15min-per-invocation
// budget) instead of failing after one bad response -- see that file for why. MAX_POLL_MS
// below has to cover that whole worst case, not just one invocation, or this file gives up
// and shows an error while the job is still legitimately retrying server-side.
const LabLLM = (() => {
  const POLL_INTERVAL_MS = 3000;
  // Worst case on the server: 3 attempts * 600s + 2 retry delays * 5s =~ 1810s (~30min),
  // spread across separate queue-consumer invocations (see worker/nvidia-proxy.js D-I).
  // 35min gives headroom for Cloudflare's own redelivery scheduling latency on top of that.
  const MAX_POLL_MS = 35 * 60 * 1000;

  // D159 (2026-07-15): request timestamps for the debug traffic graph (docs/lab/
  // debug-traffic.js) -- "did this tab's own burst momentarily exceed NVIDIA's ~40rpm
  // free-tier ceiling" (nvidia-keypool-guard.py's own documented figure). Deliberately
  // just an in-memory array, capped and trimmed below -- this is a debugging aid, not a
  // metrics store, and it only sees requests THIS tab initiated (D156's parallel chunk
  // calls are the actual client-visible submissions; server-side retries inside
  // worker/nvidia-proxy.js's queue() happen invisibly to the browser and aren't counted
  // here -- a real limitation, not an oversight, noted so this graph isn't over-trusted
  // as the complete picture of load on the key).
  const requestLog = [];
  const REQUEST_LOG_MAX_AGE_MS = 15 * 60 * 1000; // trim anything older than the chart ever shows

  function recordRequest() {
    const now = Date.now();
    requestLog.push(now);
    const cutoff = now - REQUEST_LOG_MAX_AGE_MS;
    while (requestLog.length && requestLog[0] < cutoff) requestLog.shift();
  }

  function getRequestLog() {
    return requestLog.slice();
  }

  async function submitAndPoll(proxyUrl, apiKey, body) {
    recordRequest();
    const submitRes = await fetch(proxyUrl, {
      method: "POST",
      headers: { "content-type": "application/json", "x-nvidia-api-key": apiKey },
      body: JSON.stringify(body),
    });
    if (!submitRes.ok) {
      const text = await submitRes.text().catch(() => "");
      throw new Error(`작업 제출 실패 (HTTP ${submitRes.status}): ${text.slice(0, 300)}`);
    }
    const submitData = await submitRes.json();
    const jobId = submitData.job_id;
    if (!jobId) throw new Error(`작업 제출 응답에 job_id가 없음: ${JSON.stringify(submitData).slice(0, 200)}`);

    const base = proxyUrl.split("?")[0];
    const pollUrl = `${base}?job=${encodeURIComponent(jobId)}`;
    const startedAt = Date.now();
    while (Date.now() - startedAt < MAX_POLL_MS) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      let job;
      try {
        const pollRes = await fetch(pollUrl);
        if (!pollRes.ok) continue; // transient poll hiccup -- just try again next tick
        job = await pollRes.json();
      } catch (e) {
        continue; // network blip on the poll itself -- keep polling, don't fail the job for it
      }
      if (job.status === "pending") continue;
      if (job.status === "done") return JSON.parse(job.result);
      if (job.status === "error") throw new Error(`NVIDIA 호출 실패: ${job.error || "알 수 없는 오류"}`);
      throw new Error(`알 수 없는 작업 상태: ${JSON.stringify(job).slice(0, 200)}`);
    }
    throw new Error(`작업이 ${Math.round(MAX_POLL_MS / 60000)}분 안에 끝나지 않음 (job_id=${jobId})`);
  }

  async function chatJSON({ model, messages, maxTokens, temperature = 0.0, jsonMode = true }) {
    const proxyUrl = LabConfig.get("proxy-url");
    const apiKey = LabConfig.get("nvidia-key");
    if (!proxyUrl || !apiKey) {
      throw new Error("NVIDIA API 키와 프록시 URL을 먼저 입력하세요 (상단 연결 설정).");
    }
    const body = { model, messages, max_tokens: maxTokens, temperature };
    if (jsonMode) body.response_format = { type: "json_object" };
    const data = await submitAndPoll(proxyUrl, apiKey, body);
    const choice = data.choices && data.choices[0] && data.choices[0].message;
    if (!choice) throw new Error(`예상치 못한 응답 형태: ${JSON.stringify(data).slice(0, 300)}`);
    // D131/D142's fallback chain, ported from the real pipeline -- some models (step-3.5-flash)
    // put their actual JSON-mode answer in reasoning_content, leaving content null/empty.
    const resolved = choice.content || choice.reasoning_content;
    const finishReason = data.choices[0].finish_reason;
    if (!resolved) {
      throw new Error(`빈 응답 (content 없음, finish_reason=${finishReason})`);
    }
    // D158 (2026-07-15): finishReason now always returned, not just logged on the empty-
    // content path -- a real 251-page run had 2/26 chunks fail JSON parsing with "Expected
    // ',' or ']' after array element", the textbook signature of a response cut off
    // mid-array. Without finish_reason, that was a guess; callers can now check
    // finishReason === "length" and know for certain rather than infer from parse errors.
    return { role: "assistant", content: resolved, finishReason };
  }

  async function chatTool({ model, messages, tool, maxTokens, temperature = 0.0 }) {
    const proxyUrl = LabConfig.get("proxy-url");
    const apiKey = LabConfig.get("nvidia-key");
    if (!proxyUrl || !apiKey) {
      throw new Error("NVIDIA API 키와 프록시 URL을 먼저 입력하세요 (상단 연결 설정).");
    }
    const body = {
      model, messages, max_tokens: maxTokens, temperature,
      tools: [{ type: "function", function: { name: tool.name, description: tool.description, parameters: tool.input_schema } }],
      tool_choice: { type: "function", function: { name: tool.name } },
    };
    const data = await submitAndPoll(proxyUrl, apiKey, body);
    const choice = data.choices && data.choices[0] && data.choices[0].message;
    const call = choice && choice.tool_calls && choice.tool_calls.find((c) => c.function.name === tool.name);
    if (!call) throw new Error(`tool_calls에서 ${tool.name}을 찾지 못함: ${JSON.stringify(data).slice(0, 300)}`);
    return JSON.parse(call.function.arguments);
  }

  function extractJsonObject(text) {
    let cleaned = (text || "").trim();
    cleaned = cleaned.replace(/^```(?:json)?\s*/, "").replace(/\s*```$/, "");
    try {
      return JSON.parse(cleaned);
    } catch (e) {
      const m = cleaned.match(/\{[\s\S]*\}/);
      if (!m) throw e;
      return JSON.parse(m[0]);
    }
  }

  return { chatJSON, chatTool, extractJsonObject, getRequestLog };
})();
