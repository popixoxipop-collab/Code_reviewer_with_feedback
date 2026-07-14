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
    let toolCallName = null;
    let toolCallArgs = "";
    let sawAnyEvent = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
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
        if (delta.content) content += delta.content;
        if (delta.tool_calls) {
          for (const tc of delta.tool_calls) {
            if (tc.function && tc.function.name) toolCallName = tc.function.name;
            if (tc.function && tc.function.arguments) toolCallArgs += tc.function.arguments;
          }
        }
      }
    }
    if (!sawAnyEvent) throw new Error("스트리밍 응답에서 delta 이벤트를 하나도 못 받음 (빈 응답이거나 형식이 다름)");
    return { content, toolCallName, toolCallArgs };
  }

  async function chatJSON({ model, messages, maxTokens, temperature = 0.0, jsonMode = true }) {
    const proxyUrl = LabConfig.get("proxy-url");
    const apiKey = LabConfig.get("nvidia-key");
    if (!proxyUrl || !apiKey) {
      throw new Error("NVIDIA API 키와 프록시 URL을 먼저 입력하세요 (상단 연결 설정).");
    }
    const body = { model, messages, max_tokens: maxTokens, temperature };
    if (jsonMode) body.response_format = { type: "json_object" };
    const { content } = await streamChatCompletion(proxyUrl, apiKey, body);
    if (!content) throw new Error("빈 응답 (content 없음)");
    return { role: "assistant", content };
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
    const { toolCallName, toolCallArgs } = await streamChatCompletion(proxyUrl, apiKey, body);
    if (toolCallName !== tool.name || !toolCallArgs) {
      throw new Error(`tool_calls에서 ${tool.name}을 찾지 못함 (받은 이름: ${toolCallName || "없음"})`);
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
