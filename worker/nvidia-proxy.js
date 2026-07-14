/**
 * D-C (PLAN.md): integrate.api.nvidia.com has no Access-Control-Allow-Origin header
 * (verified 2026-07-14), so browser calls from docs/lab/ must go through a proxy.
 * This is that proxy -- deployable by anyone on the team as their own Cloudflare
 * Worker, then pasted into the tool's "LLM 프록시 URL" field. The whole point of
 * publishing this file in the repo is that anyone can read exactly what it does with
 * the API key they paste into it: forwards one header, forwards one POST body,
 * returns the response. Nothing is logged, nothing is persisted, nothing else is read.
 *
 * Deploy: `npx wrangler deploy worker/nvidia-proxy.js` (needs a free Cloudflare
 * account + `wrangler login` once). See experiments/web_lab/SETUP.md.
 *
 * D-D (PLAN.md): the API key travels in a request header from the browser, through
 * this worker, to NVIDIA -- it is read from the incoming request and placed on the
 * outgoing request, and that's the only thing this code does with it. It is never
 * written to KV/D1/any storage, never included in a response, never logged (no
 * console.log of headers/body anywhere in this file -- keep it that way if you edit it).
 */

const NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions";

// Restrict to your GitHub Pages origin once you know it -- "*" works but means any
// website could relay calls through your worker using a visitor's own pasted key
// (that key is still theirs, but it's needless exposure of your worker as an open relay).
const ALLOWED_ORIGIN = "*"; // e.g. "https://popixoxipop-collab.github.io"

function corsHeaders(origin) {
  return {
    "access-control-allow-origin": ALLOWED_ORIGIN === "*" ? "*" : ALLOWED_ORIGIN,
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-allow-headers": "content-type, x-nvidia-api-key",
    "access-control-max-age": "86400",
  };
}

export default {
  async fetch(request) {
    const origin = request.headers.get("origin") || "";

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }

    if (request.method !== "POST") {
      return new Response(JSON.stringify({ error: "POST only" }), {
        status: 405,
        headers: { "content-type": "application/json", ...corsHeaders(origin) },
      });
    }

    const apiKey = request.headers.get("x-nvidia-api-key");
    if (!apiKey) {
      return new Response(JSON.stringify({ error: "missing x-nvidia-api-key header" }), {
        status: 401,
        headers: { "content-type": "application/json", ...corsHeaders(origin) },
      });
    }

    let body;
    try {
      body = await request.text();
    } catch (e) {
      return new Response(JSON.stringify({ error: "could not read request body" }), {
        status: 400,
        headers: { "content-type": "application/json", ...corsHeaders(origin) },
      });
    }

    let upstream;
    try {
      upstream = await fetch(NVIDIA_URL, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: `Bearer ${apiKey}`,
        },
        body,
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: `upstream fetch failed: ${e.message}` }), {
        status: 502,
        headers: { "content-type": "application/json", ...corsHeaders(origin) },
      });
    }

    const responseBody = await upstream.text();
    return new Response(responseBody, {
      status: upstream.status,
      headers: { "content-type": "application/json", ...corsHeaders(origin) },
    });
  },
};
