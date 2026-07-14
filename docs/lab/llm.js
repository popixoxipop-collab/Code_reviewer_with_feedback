// D-C (PLAN.md): integrate.api.nvidia.com has no Access-Control-Allow-Origin header
// (verified 2026-07-14) -- direct browser calls are impossible, so every LLM call in
// this tool goes through a proxy the user configures (worker/nvidia-proxy.js is the
// reference implementation, deployable by anyone on the team). This file never talks
// to NVIDIA directly and never persists the key past the in-memory config object.
//
// D-E (2026-07-14, real P01 test): always streams (`stream: true`) and reassembles the
// SSE chunks below instead of waiting for one big JSON response -- Cloudflare's free-tier
// edge kills a connection that sends the client nothing for ~100s, which slow models
// (qwen3-next-80b on P01-length prompts) blow past routinely. Streaming means bytes reach
// the client as they're generated, so the connection never looks idle. callPromptStage()/
// generateQuestion() etc. still just get back a plain complete string or parsed object --
// this file is the only place that knows the transport is now streaming.
const LabLLM = (() => {
  // D-F (2026-07-14, real P01 test): a "빈 응답 (content 없음)" failure -- fast (1-2s),
  // HTTP-successful, but no usable content -- is a genuinely different failure from a 524
  // and needs different evidence to diagnose. Rather than just reporting "empty", collect
  // what NVIDIA's deltas actually looked like (which keys arrived, a raw sample of the SSE
  // text) so the next real run's error message tells us whether e.g. content is arriving
  // under a different field (D131 found step-3.5-flash streams its answer as
  // reasoning_content, not content, even in JSON mode -- this file doesn't read that field
  // yet) versus something else entirely, instead of guessing again from a blind rerun.
  async function streamChatCompletion(proxyUrl, apiKey, body) {
    const res = await fetch(proxyUrl, {
      method: "POST",
      headers: { "content-type": "application/json", "x-nvidia-api-key": apiKey },
      body: JSON.stringify({ ...body, stream: true }),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`프록시/NVIDIA 호출 실패 (HTTP ${res.status}): ${text.slice(0, 300)}`);
    }
    if (!res.body) throw new Error("스트리밍 응답을 읽을 수 없음 (res.body 없음)");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let content = "";
    let reasoningContent = "";
    let toolCallName = null;
    let toolCallArgs = "";
    let sawAnyEvent = false;
    let eventCount = 0;
    const deltaKeysSeen = new Set();
    let rawSample = "";
    let totalBytes = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const decoded = decoder.decode(value, { stream: true });
      totalBytes += value.length;
      if (rawSample.length < 400) rawSample += decoded;
      buffer += decoded;
      const lines = buffer.split("\n");
      buffer = lines.pop(); // last line may be incomplete -- keep for next chunk
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;
        const payload = trimmed.slice(5).trim();
        if (payload === "[DONE]") continue;
        let evt;
        try { evt = JSON.parse(payload); } catch (e) { continue; }
        const delta = evt.choices && evt.choices[0] && evt.choices[0].delta;
        if (!delta) continue;
        sawAnyEvent = true;
        eventCount++;
        Object.keys(delta).forEach((k) => deltaKeysSeen.add(k));
        if (delta.content) content += delta.content;
        if (delta.reasoning_content) reasoningContent += delta.reasoning_content;
        if (delta.tool_calls) {
          for (const tc of delta.tool_calls) {
            if (tc.function && tc.function.name) toolCallName = tc.function.name;
            if (tc.function && tc.function.arguments) toolCallArgs += tc.function.arguments;
          }
        }
      }
    }
    const diag = `(이벤트 ${eventCount}개, 바이트 ${totalBytes}, delta 키: [${[...deltaKeysSeen].join(",")}], 원본 샘플: ${rawSample.slice(0, 200).replace(/\n/g, "\\n")})`;
    if (!sawAnyEvent) throw new Error(`스트리밍 응답에서 delta 이벤트를 하나도 못 받음 ${diag}`);
    return { content, reasoningContent, toolCallName, toolCallArgs, diag };
  }

  async function chatJSON({ model, messages, maxTokens, temperature = 0.0, jsonMode = true }) {
    const proxyUrl = LabConfig.get("proxy-url");
    const apiKey = LabConfig.get("nvidia-key");
    if (!proxyUrl || !apiKey) {
      throw new Error("NVIDIA API 키와 프록시 URL을 먼저 입력하세요 (상단 연결 설정).");
    }
    const body = { model, messages, max_tokens: maxTokens, temperature };
    if (jsonMode) body.response_format = { type: "json_object" };
    const { content, reasoningContent, diag } = await streamChatCompletion(proxyUrl, apiKey, body);
    // D131's fallback chain (content -> reasoning_content), ported from the real pipeline --
    // some models (step-3.5-flash) stream their JSON-mode answer into reasoning_content.
    const resolved = content || reasoningContent;
    if (!resolved) throw new Error(`빈 응답 (content 없음) ${diag}`);
    return { role: "assistant", content: resolved };
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
    const { toolCallName, toolCallArgs, diag } = await streamChatCompletion(proxyUrl, apiKey, body);
    if (toolCallName !== tool.name || !toolCallArgs) {
      throw new Error(`tool_calls에서 ${tool.name}을 찾지 못함 (받은 이름: ${toolCallName || "없음"}) ${diag}`);
    }
    return JSON.parse(toolCallArgs);
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

  return { chatJSON, chatTool, extractJsonObject };
})();
