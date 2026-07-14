// D-D (PLAN.md): API keys/PAT live in memory only, optionally sessionStorage -- never
// localStorage, never sent to Supabase, never written into any run record. This file is
// the single place that reads/writes them so that guarantee has one enforcement point.
const LabConfig = (() => {
  const FIELDS = ["nvidia-key", "proxy-url", "github-pat", "supabase-url", "supabase-anon-key"];
  const SESSION_PREFIX = "lab_cfg_";
  let state = { "nvidia-key": "", "proxy-url": "", "github-pat": "", "supabase-url": "", "supabase-anon-key": "" };

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
    parts.push(state["supabase-url"] && state["supabase-anon-key"] ? "DB 저장 켜짐" : "DB 저장 꺼짐(결과는 화면에만 표시)");
    el.textContent = parts.join(" · ");
    el.className = "auth-status" + (state["nvidia-key"] && state["proxy-url"] ? " ok" : "");
  }

  function get(field) { return state[field] || ""; }
  function has(field) { return Boolean(state[field]); }

  function wireLogin() {
    const btn = document.getElementById("login-btn");
    const emailEl = document.getElementById("login-email");
    const statusEl = document.getElementById("login-status");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      if (!LabDB.isConfigured()) {
        statusEl.textContent = "먼저 Supabase URL/anon key를 입력하세요";
        return;
      }
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

  function init() {
    wireInputs();
    loadFromSession();
    renderStatus();
    wireLogin();
  }

  return { init, get, has, FIELDS };
})();

document.addEventListener("DOMContentLoaded", LabConfig.init);
