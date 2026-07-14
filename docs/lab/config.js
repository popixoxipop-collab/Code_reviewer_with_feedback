// D-D (PLAN.md): API keys/PAT live in memory only, optionally sessionStorage -- never
// localStorage, never sent to Supabase, never written into any run record. This file is
// the single place that reads/writes them so that guarantee has one enforcement point.
//
// Supabase URL/anon key are the one exception: this is the team's single shared DB, not a
// per-teammate secret, so they're hardcoded below instead of typed in every session. This
// is safe specifically because Supabase's RLS policies (supabase_schema.sql) -- not anon
// key secrecy -- are what actually protects the data; the anon key is meant to ship in
// client code. Teammates still enter their own NVIDIA key/PAT and sign in with their own
// email for per-member attribution.
const LabConfig = (() => {
  const TEAM_SUPABASE_URL = "https://oziaeqcvrkrqkhwrybfj.supabase.co";
  const TEAM_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im96aWFlcWN2cmtycWtod3J5YmZqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQwMDA4MTksImV4cCI6MjA5OTU3NjgxOX0.hBgzs0V7Nw3WLB8_zNuPDfluYrqOH2_Dto1weQF5iKo";

  // Owner-deployed proxy (worker/nvidia-proxy.js), pre-filled as a default -- unlike the
  // Supabase values above this is NOT force-hardcoded: it's just a starting value in an
  // editable field, since SETUP.md's team-sharing note explicitly means for teammates to
  // be able to deploy and swap in their own proxy instead (a URL, not a credential, so
  // there's no reason to also lock this one down).
  const DEFAULT_PROXY_URL = "https://nvidia-proxy.popixoxipop.workers.dev";

  const FIELDS = ["nvidia-key", "proxy-url", "github-pat"];
  const SESSION_PREFIX = "lab_cfg_";
  let state = { "nvidia-key": "", "proxy-url": DEFAULT_PROXY_URL, "github-pat": "" };

  function loadFromSession() {
    if (!sessionStorage.getItem(SESSION_PREFIX + "remember")) return;
    for (const f of FIELDS) {
      const v = sessionStorage.getItem(SESSION_PREFIX + f);
      if (v) {
        state[f] = v;
        const el = document.getElementById(f);
        if (el) el.value = v;
      }
    }
    const rememberBox = document.getElementById("remember-session");
    if (rememberBox) rememberBox.checked = true;
  }

  function wireInputs() {
    for (const f of FIELDS) {
      const el = document.getElementById(f);
      if (!el) continue;
      el.addEventListener("input", () => {
        state[f] = el.value.trim();
        persistIfRemembered();
        renderStatus();
      });
    }
    const rememberBox = document.getElementById("remember-session");
    if (rememberBox) {
      rememberBox.addEventListener("change", () => {
        if (rememberBox.checked) {
          sessionStorage.setItem(SESSION_PREFIX + "remember", "1");
          persistIfRemembered();
        } else {
          sessionStorage.removeItem(SESSION_PREFIX + "remember");
          for (const f of FIELDS) sessionStorage.removeItem(SESSION_PREFIX + f);
        }
      });
    }
  }

  function persistIfRemembered() {
    if (!sessionStorage.getItem(SESSION_PREFIX + "remember")) return;
    for (const f of FIELDS) sessionStorage.setItem(SESSION_PREFIX + f, state[f] || "");
  }

  function renderStatus() {
    const el = document.getElementById("auth-status");
    if (!el) return;
    const parts = [];
    parts.push(state["nvidia-key"] && state["proxy-url"] ? "P01/P03 실행 가능" : "P01/P03: NVIDIA 키 + 프록시 URL 필요");
    parts.push("DB 저장 켜짐(팀 공용) — 로그인해야 실제로 저장됨");
    el.textContent = parts.join(" · ");
    el.className = "auth-status" + (state["nvidia-key"] && state["proxy-url"] ? " ok" : "");
  }

  function get(field) {
    if (field === "supabase-url") return TEAM_SUPABASE_URL;
    if (field === "supabase-anon-key") return TEAM_SUPABASE_ANON_KEY;
    return state[field] || "";
  }
  function has(field) {
    if (field === "supabase-url" || field === "supabase-anon-key") return true;
    return Boolean(state[field]);
  }

  function wireLogin() {
    const btn = document.getElementById("login-btn");
    const emailEl = document.getElementById("login-email");
    const statusEl = document.getElementById("login-status");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      const email = (emailEl.value || "").trim();
      if (!email) { statusEl.textContent = "이메일을 입력하세요"; return; }
      statusEl.textContent = "전송 중...";
      try {
        await LabDB.signInWithEmail(email);
        statusEl.textContent = `${email}로 매직 링크 전송됨 — 메일함에서 링크를 클릭하면 이 탭이 로그인됨`;
      } catch (err) {
        statusEl.textContent = `실패: ${err.message}`;
      }
    });
  }

  function applyDefaults() {
    for (const f of FIELDS) {
      const el = document.getElementById(f);
      if (el && state[f]) el.value = state[f];
    }
  }

  function init() {
    wireInputs();
    applyDefaults();
    loadFromSession();
    renderStatus();
    wireLogin();
  }

  return { init, get, has, FIELDS };
})();

document.addEventListener("DOMContentLoaded", LabConfig.init);
