// D-B (PLAN.md): Supabase Postgres+Auth+RLS as the team DB. Optional -- if not
// configured, pipelines still run fully, results just aren't persisted (console-only).
// Loaded lazily (supabase-js only fetched if the user actually filled in the two fields)
// so the common "just testing locally" path never pulls in a third-party script at all.
const LabDB = (() => {
  let client = null;
  let loadingPromise = null;

  function isConfigured() {
    return Boolean(LabConfig.get("supabase-url") && LabConfig.get("supabase-anon-key"));
  }

  async function ensureClient() {
    if (client) return client;
    if (!isConfigured()) throw new Error("Supabase가 설정되지 않음");
    if (!loadingPromise) {
      loadingPromise = (async () => {
        if (!window.supabase) {
          await loadScript(
            "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js",
            "sha384-GFr3yTh5lJznCbZfpTtXnwboFsxqtTQoeTZCRHhE0579KrRmlCzen5AA8ohaB5ug"
          );
        }
        client = window.supabase.createClient(LabConfig.get("supabase-url"), LabConfig.get("supabase-anon-key"));
      })();
    }
    await loadingPromise;
    return client;
  }

  function loadScript(src, integrity) {
    return new Promise((resolve, reject) => {
      const el = document.createElement("script");
      el.src = src;
      if (integrity) {
        el.integrity = integrity;
        el.crossOrigin = "anonymous";
      }
      el.onload = resolve;
      el.onerror = () => reject(new Error(`스크립트 로드 실패: ${src}`));
      document.head.appendChild(el);
    });
  }

  async function currentMember() {
    const c = await ensureClient();
    const { data, error } = await c.auth.getUser();
    if (error || !data.user) throw new Error("로그인이 필요합니다 (Supabase magic link)");
    return data.user;
  }

  async function saveRun({ pipeline, model, input_meta, overrides, rubric_overridden, artifacts }) {
    const c = await ensureClient();
    const user = await currentMember();
    const { data: run, error: runErr } = await c
      .from("runs")
      .insert({
        member_id: user.id, pipeline, model, status: "done",
        started_at: new Date().toISOString(), finished_at: new Date().toISOString(),
        input_meta: input_meta || {}, overrides: overrides || {}, rubric_overridden: Boolean(rubric_overridden),
        manifest_version: (LabApp.getManifest() || {}).manifest_version || null,
      })
      .select()
      .single();
    if (runErr) throw runErr;

    for (const a of artifacts || []) {
      const content = JSON.stringify(a.content);
      const truncated = content.length > 100000;
      const { error: artErr } = await c.from("artifacts").insert({
        run_id: run.id, kind: a.kind,
        content: JSON.parse(truncated ? content.slice(0, 100000) : content === "" ? "{}" : content || "{}"),
        truncated,
      });
      if (artErr) throw artErr;
    }
    return run;
  }

  async function signInWithEmail(email) {
    const c = await ensureClient();
    const { error } = await c.auth.signInWithOtp({ email });
    if (error) throw error;
  }

  return { isConfigured, ensureClient, currentMember, saveRun, signInWithEmail };
})();
