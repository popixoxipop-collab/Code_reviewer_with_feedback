// D-C (PLAN.md): integrate.api.nvidia.com has no Access-Control-Allow-Origin header
// (verified 2026-07-14) -- direct browser calls are impossible, so every LLM call in
// this tool goes through a proxy the user configures (worker/nvidia-proxy.js is the
// reference implementation, deployable by anyone on the team). This file never talks
// to NVIDIA directly and never persists the key past the in-memory config object.
const LabLLM = (() => {
  async function chatJSON({ model, messages, maxTokens, temperature = 0.0, jsonMode = true }) {
    const proxyUrl = LabConfig.get("proxy-url");
    const apiKey = LabConfig.get("nvidia-key");
    if (!proxyUrl || !apiKey) {
      throw new Error("NVIDIA API 키와 프록시 URL을 먼저 입력하세요 (상단 연결 설정).");
    }
    const body = { model, messages, max_tokens: maxTokens, temperature };
    if (jsonMode) body.response_format = { type: "json_object" };
    const res = await fetch(proxyUrl, {
      method: "POST",
      headers: { "content-type": "application/json", "x-nvidia-api-key": apiKey },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`프록시/NVIDIA 호출 실패 (HTTP ${res.status}): ${text.slice(0, 300)}`);
    }
    const data = await res.json();
    const choice = data.choices && data.choices[0] && data.choices[0].message;
    if (!choice) throw new Error(`예상치 못한 응답 형태: ${JSON.stringify(data).slice(0, 300)}`);
    return choice;
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
    const res = await fetch(proxyUrl, {
      method: "POST",
      headers: { "content-type": "application/json", "x-nvidia-api-key": apiKey },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`프록시/NVIDIA 호출 실패 (HTTP ${res.status}): ${text.slice(0, 300)}`);
    }
    const data = await res.json();
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

  return { chatJSON, chatTool, extractJsonObject };
})();
