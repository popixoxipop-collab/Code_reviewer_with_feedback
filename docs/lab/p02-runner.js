// P02 has zero LLM calls (verified against cognition/two_tier_scan.py + judgment/*.py --
// pure re/os/sys/json stdlib), so this is the only pipeline that needs no API key, no
// proxy, and no external account at all -- it's the Phase-1 MVP from PLAN.md.
//
// D-E (PLAN.md): runs the REAL, unmodified pipeline source in-browser via Pyodide,
// fetched fresh from raw.githubusercontent.com every run so it never drifts from the
// repo. The only new Python is webtool_driver.py, which just applies parameter
// overrides as module attribute writes, then calls the real scan()/score().
const P02Runner = (() => {
  const REPO_RAW_BASE = "https://raw.githubusercontent.com/popixoxipop-collab/Code_reviewer_with_feedback/main/";
  const PIPELINE_FILES = [
    "cognition/two_tier_scan.py",
    "judgment/score_findings.py",
    "judgment/idiom_filter.py",
    "judgment/tier_b_suppression_filter.py",
    "judgment/subrubric.py",
    "judgment/tier_b_hook.py",
    "judgment/subrubric_hook.py",
    "judgment/isolation_categories/role_separation/patterns.json",
    "judgment/isolation_categories/domain_irrelevance/patterns.json",
    "judgment/isolation_categories/alt_storage_or_scope/patterns.json",
    "judgment/isolation_categories/perf_optimization/patterns.json",
    "judgment/tier_b_suppressions/suppressions.json",
    "judgment/subrubric_weights/question_value/weights.json",
    "judgment/subrubric_weights/design_intent/weights.json",
    "judgment/subrubric_weights/risk/weights.json",
    "judgment/idioms/python/idiom_patterns.json",
    "judgment/idioms/java/idiom_patterns.json",
    "judgment/idioms/cpp/idiom_patterns.json",
    "judgment/idioms/swift/idiom_patterns.json",
    "judgment/idioms/javascript/idiom_patterns.json",
    "judgment/idioms/c/idiom_patterns.json",
  ];
  const SKIP_DIR_NAMES = new Set(["node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv", "static", "vendor", "vendored"]);
  const SRC_EXTS = [".ts", ".tsx", ".js", ".jsx", ".py", ".java", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".swift"];

  let pyodide = null;
  let currentMethod = "pat"; // "pat" | "zip"
  let zipFiles = null; // { relPath: content }

  function isSkippedPath(relPath) {
    const parts = relPath.split("/");
    if (parts.some((p) => SKIP_DIR_NAMES.has(p))) return true;
    const ext = "." + (relPath.split(".").pop() || "");
    if (!SRC_EXTS.includes(ext)) return true;
    return false;
  }

  function renderInput(container) {
    container.innerHTML = `
      <div class="input-panel">
        <h3>코드 입력</h3>
        <div class="input-methods">
          <button class="method-btn active" data-method="pat">GitHub (PAT)</button>
          <button class="method-btn" data-method="zip">ZIP 드래그앤드롭</button>
        </div>
        <div id="p02-method-pat">
          <div class="input-row">
            <input type="text" id="p02-repo-input" placeholder="owner/repo 또는 https://github.com/owner/repo">
            <input type="text" id="p02-branch-input" placeholder="branch (비우면 기본 브랜치)" style="max-width:180px;">
          </div>
          <p style="color:var(--ink-faint); font-size:0.72rem; margin-top:6px;">
            공개 repo는 PAT 없이도 동작(GitHub API 비인증 60회/시간 제한). 비공개 repo는 상단 연결 설정에 PAT 입력 필요.
            PAT은 api.github.com에 직접 전달되며 프록시를 거치지 않음.
          </p>
        </div>
        <div id="p02-method-zip" class="hidden">
          <div class="dropzone" id="p02-dropzone">여기로 .zip 파일을 드래그하거나 클릭해서 선택</div>
          <input type="file" id="p02-zip-input" accept=".zip" class="hidden">
          <p id="p02-zip-status" style="color:var(--ink-faint); font-size:0.72rem; margin-top:6px;"></p>
        </div>
      </div>`;

    container.querySelectorAll(".method-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        currentMethod = btn.dataset.method;
        container.querySelectorAll(".method-btn").forEach((b) => b.classList.toggle("active", b === btn));
        container.querySelector("#p02-method-pat").classList.toggle("hidden", currentMethod !== "pat");
        container.querySelector("#p02-method-zip").classList.toggle("hidden", currentMethod !== "zip");
      });
    });

    const dropzone = container.querySelector("#p02-dropzone");
    const zipInput = container.querySelector("#p02-zip-input");
    dropzone.addEventListener("click", () => zipInput.click());
    dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("drag-over"); });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
    dropzone.addEventListener("drop", async (e) => {
      e.preventDefault();
      dropzone.classList.remove("drag-over");
      const file = e.dataTransfer.files[0];
      if (file) await handleZipFile(file, container);
    });
    zipInput.addEventListener("change", async () => {
      if (zipInput.files[0]) await handleZipFile(zipInput.files[0], container);
    });
  }

  async function handleZipFile(file, container) {
    const status = container.querySelector("#p02-zip-status");
    status.textContent = `압축 해제 중: ${file.name}...`;
    try {
      const zip = await JSZip.loadAsync(file);
      const entries = Object.values(zip.files).filter((e) => !e.dir);
      const files = {};
      for (const entry of entries) {
        if (isSkippedPath(entry.name)) continue;
        try {
          files[entry.name] = await entry.async("string");
        } catch (e) { /* binary file, skip */ }
      }
      zipFiles = files;
      status.textContent = `${file.name}: 소스 파일 ${Object.keys(files).length}개 로드됨`;
    } catch (err) {
      status.textContent = `압축 해제 실패: ${err.message}`;
      zipFiles = null;
    }
  }

  function parseRepoInput(raw) {
    let s = raw.trim().replace(/^https?:\/\/github\.com\//, "").replace(/\/$/, "").replace(/\.git$/, "");
    const parts = s.split("/");
    if (parts.length < 2) throw new Error("owner/repo 형식으로 입력하세요");
    return { owner: parts[0], repo: parts[1] };
  }

  async function fetchGithubRepo(owner, repo, branch, pat, onProgress) {
    const headers = { accept: "application/vnd.github+json" };
    if (pat) headers.authorization = `Bearer ${pat}`;

    if (!branch) {
      const infoRes = await fetch(`https://api.github.com/repos/${owner}/${repo}`, { headers });
      if (!infoRes.ok) throw new Error(`repo 조회 실패 (HTTP ${infoRes.status}) — 이름/권한 확인`);
      branch = (await infoRes.json()).default_branch;
    }

    const treeRes = await fetch(`https://api.github.com/repos/${owner}/${repo}/git/trees/${encodeURIComponent(branch)}?recursive=1`, { headers });
    if (!treeRes.ok) throw new Error(`파일 목록 조회 실패 (HTTP ${treeRes.status})`);
    const tree = await treeRes.json();
    if (tree.truncated) onProgress("경고: repo가 커서 GitHub API가 파일 목록을 일부만 반환함");

    const blobs = (tree.tree || []).filter((t) => t.type === "blob" && !isSkippedPath(t.path));
    onProgress(`소스 파일 ${blobs.length}개 발견, 내용 가져오는 중...`);

    const files = {};
    const CONCURRENCY = 6;
    let done = 0;
    for (let i = 0; i < blobs.length; i += CONCURRENCY) {
      const batch = blobs.slice(i, i + CONCURRENCY);
      await Promise.all(batch.map(async (b) => {
        const blobRes = await fetch(b.url, { headers });
        if (blobRes.ok) {
          const blobData = await blobRes.json();
          if (blobData.encoding === "base64") {
            try {
              files[b.path] = decodeURIComponent(escape(atob(blobData.content.replace(/\n/g, ""))));
            } catch (e) { /* binary content, skip */ }
          }
        }
        done += 1;
        if (done % 5 === 0 || done === blobs.length) onProgress(`${done}/${blobs.length} 파일 가져옴`);
      }));
    }
    return files;
  }

  async function ensurePyodide(onProgress) {
    pyodide = await LabPyodide.get(onProgress);
    return pyodide;
  }

  async function ensurePipelineSource(onProgress) {
    if (LabPyodide.isLoaded("p02")) return;
    onProgress("파이프라인 원본 코드 로드 중 (raw.githubusercontent.com, repo 최신본)...");
    await LabPyodide.loadFiles(pyodide, REPO_RAW_BASE, PIPELINE_FILES, "/lib", null);
    const driverRes = await fetch("webtool_driver.py");
    pyodide.FS.writeFile("/lib/webtool_driver.py", await driverRes.text(), { encoding: "utf8" });
    pyodide.runPython(`
import sys
for p in ["/lib", "/lib/cognition", "/lib/judgment"]:
    if p not in sys.path:
        sys.path.insert(0, p)
`);
    LabPyodide.markLoaded("p02");
  }

  function writeTargetFiles(files) {
    if (pyodide.FS.analyzePath("/target").exists) {
      pyodide.runPython(`
import shutil
shutil.rmtree("/target", ignore_errors=True)
`);
    }
    pyodide.FS.mkdirTree("/target");
    for (const [relPath, content] of Object.entries(files)) {
      const fullPath = "/target/" + relPath;
      const dir = fullPath.substring(0, fullPath.lastIndexOf("/"));
      pyodide.FS.mkdirTree(dir);
      pyodide.FS.writeFile(fullPath, content, { encoding: "utf8" });
    }
  }

  function collectOverrides() {
    const manifest = LabApp.getManifest();
    const stages = manifest.pipelines.p02.stages;
    const overrides = { two_tier_scan: {}, score_findings: {} };
    const moduleForStage = { "p02-1": "two_tier_scan", "p02-2": "two_tier_scan", "p02-3": "two_tier_scan", "p02-4": "score_findings" };
    for (const stage of stages) {
      const ov = LabApp.getOverride("p02", stage.id);
      if (ov && ov.params) {
        const mod = moduleForStage[stage.id];
        Object.assign(overrides[mod], ov.params);
      }
    }
    return overrides;
  }

  async function run() {
    const pipelineId = "p02";
    LabApp.setStatus(pipelineId, "실행 중...", "running");
    const startedAt = new Date();
    LabApp.startTimer(pipelineId);
    try {
      let files;
      if (currentMethod === "pat") {
        const repoInput = document.getElementById("p02-repo-input").value;
        const branch = document.getElementById("p02-branch-input").value.trim() || null;
        if (!repoInput.trim()) throw new Error("repo를 입력하세요 (owner/repo)");
        const { owner, repo } = parseRepoInput(repoInput);
        const pat = LabConfig.get("github-pat");
        LabApp.log(pipelineId, `${owner}/${repo} (${branch || "기본 브랜치"}) 가져오는 중...`);
        files = await fetchGithubRepo(owner, repo, branch, pat, (msg) => LabApp.log(pipelineId, msg));
      } else {
        if (!zipFiles) throw new Error("ZIP 파일을 먼저 드롭하세요");
        files = zipFiles;
      }
      if (Object.keys(files).length === 0) throw new Error("스캔 대상 소스 파일을 찾지 못함 (확장자/디렉터리 필터 확인)");

      await ensurePyodide((msg) => LabApp.log(pipelineId, msg));
      await ensurePipelineSource((msg) => LabApp.log(pipelineId, msg));
      LabApp.log(pipelineId, `대상 파일 ${Object.keys(files).length}개를 파이썬 가상 파일시스템에 기록 중...`);
      writeTargetFiles(files);

      const overrides = collectOverrides();
      LabApp.log(pipelineId, "two_tier_scan.py + score_findings.py 실행 중 (원본 코드, 수정 없음)...");
      const py = await ensurePyodide();
      py.globals.set("overrides_json", JSON.stringify(overrides));
      py.runPython(`
import webtool_driver
_result = webtool_driver.run_scan("/target", overrides_json)
`);
      const resultJson = py.globals.get("_result");
      const result = JSON.parse(resultJson);

      const finishedAt = new Date();
      LabApp.stopTimer(pipelineId);
      LabApp.setStatus(pipelineId, "완료", "done");
      LabApp.log(pipelineId, `finding ${result.judgment.findings.length}건 산출됨`);
      renderResults(result, files);
      await maybeSaveRun(result, files, startedAt, finishedAt);
    } catch (err) {
      LabApp.stopTimer(pipelineId);
      console.error(err);
      LabApp.setStatus(pipelineId, `오류: ${err.message}`, "error");
      LabApp.log(pipelineId, `오류: ${err.message}`);
    }
  }

  function renderResults(result, files) {
    const j = result.judgment;
    let html = `<p>대상 파일 <b>${Object.keys(files).length}</b>개 · finding <b>${j.findings.length}</b>건`;
    if (j.hub) html += ` · 허브: <code>${LabApp.escapeHtml(j.hub)}</code>`;
    html += `</p>`;
    if (result.overrides_applied && result.overrides_applied.length) {
      html += `<p style="color:var(--accent); font-size:0.78rem;">적용된 파라미터 오버라이드: ${result.overrides_applied.map((s) => `<code>${LabApp.escapeHtml(s)}</code>`).join(", ")}</p>`;
    }
    if (j.findings.length === 0) {
      html += `<p style="color:var(--ink-faint);">이번 실행에서는 finding이 나오지 않았다.</p>`;
    }
    for (const f of j.findings) {
      html += `<div class="finding-card">
        <div class="fid">${LabApp.escapeHtml(f.id)} · priority: ${LabApp.escapeHtml(f.priority || "")}</div>
        <div>${LabApp.escapeHtml(f.finding || "")}</div>
      </div>`;
    }
    html += `<p class="field-label" style="margin-top:14px;">원본 scan/judgment JSON</p><pre>${LabApp.escapeHtml(JSON.stringify(result, null, 2)).slice(0, 20000)}</pre>`;
    LabApp.showResults(html);
  }

  async function maybeSaveRun(result, files, startedAt, finishedAt) {
    if (!LabDB.isConfigured()) {
      LabApp.log("p02", "Supabase 미설정 — 결과는 화면에만 표시됨(DB 저장 안 됨)");
      return;
    }
    try {
      await LabDB.saveRun({
        pipeline: "p02",
        model: null,
        input_meta: { file_count: Object.keys(files).length, method: currentMethod },
        overrides: result.overrides_applied || [],
        rubric_overridden: false,
        artifacts: [{ kind: "findings", content: result.judgment }],
        started_at: startedAt.toISOString(), finished_at: finishedAt.toISOString(),
      });
      LabApp.log("p02", `결과가 팀 DB에 저장됨 (소요시간 ${LabApp.formatElapsed(finishedAt - startedAt)})`);
    } catch (err) {
      LabApp.log("p02", `DB 저장 실패(결과는 화면에 남아있음): ${err.message}`);
    }
  }

  LabApp.registerRunner("p02", { renderInput, run });
  return { renderInput, run };
})();
