// P01 needs the NVIDIA key + proxy (unlike P02). PDF text extraction uses pdf.js instead
// of the real pipeline's `pdftotext -layout` -- every run is tagged extractor:"pdfjs" so
// results are never silently treated as byte-comparable with a CLI run (PLAN.md P01
// caveat). The prompts themselves are identical to the real pipeline (read from the
// same manifest P02/P03 use, editable the same way).
const P01Runner = (() => {
  let pdfBytes = null;
  let pdfPassword = "";
  let selectedModel = null; // initialized from manifest.shared.default_model on first render, then sticky across tab switches

  // Ranking + notes sourced from docs/pipelines.html's 11-model 4-axis table (D116). That
  // benchmark measures a DIFFERENT task (P03 question-gen x grading) -- P01-T1 (D119/D120)
  // separately found step-3.5-flash (rank #1 there) fails completely on P01's chunk-analysis
  // task (0/50) while qwen3-next-80b succeeds 96%. So "tier" below is P01-specific evidence
  // (good/bad), not a re-skin of the P03 rank -- the other 9 are honestly labeled unverified
  // for P01 rather than implying the P03 ranking transfers.
  //
  // D-G (2026-07-14): that "0/50" verdict is now suspect. scripts/java_curriculum_nvidia_
  // pipeline.py's chat_json() only ever reads choice["content"] and raises if it's empty --
  // it has no reasoning_content fallback. A live curl to NVIDIA confirmed step-3.5-flash puts
  // its actual answer in reasoning_content with content:null, exactly like D131 found for a
  // different call site. D120's P01-T1 test almost certainly hit this same bug, not a real
  // capability limit -- it may never have seen this model's real output at all. This web tool's
  // llm.js already carries the reasoning_content fallback (D-F), so a run here is actually a
  // cleaner test than D120's ever was -- downgraded from "bad" to "unverified" pending a real
  // retest, rather than continuing to assert a verdict that might just be measuring the bug.
  const MODEL_CHOICES = [
    { id: "stepfun-ai/step-3.5-flash", label: "step-3.5-flash", tier: "unverified",
      note: "P01-T1(D120)의 '0/50 완전실패'는 reasoning_content 버그로 오염됐을 가능성이 큼(D-G) -- 이 도구는 그 폴백이 있어 재검증 가치 있음." },
    { id: "mistralai/mistral-medium-3.5-128b", label: "mistral-medium-3.5", tier: "unverified",
      note: "P01 기준 미검증 · P03 종합 2위(0.749)." },
    { id: "qwen/qwen3-next-80b-a3b-instruct", label: "qwen3-next-80b", tier: "good",
      note: "팀 Locked 모델 · P01-T1 실측 96% 성공(D120) · 기본값." },
    { id: "nvidia/nemotron-3-super-120b-a12b", label: "nemotron-3-super-120b", tier: "unverified",
      note: "P01 기준 미검증 · P03에서 범위 밖 점수 출력 결함 이력." },
    { id: "qwen/qwen3.5-122b-a10b", label: "qwen3.5-122b", tier: "unverified",
      note: "P01 기준 미검증 · P03 종합 5위(0.589)." },
    { id: "nvidia/llama-3.3-nemotron-super-49b-v1.5", label: "nemotron-super-49b", tier: "unverified",
      note: "P01 기준 미검증 · P03 종합 6위(0.531)." },
    { id: "deepseek-ai/deepseek-v4-pro", label: "deepseek-v4-pro", tier: "unverified",
      note: "P01 기준 미검증 · P03에서 쿼타 소진 이력(측정 당시 몇 시간 전엔 100%)." },
    { id: "meta/llama-4-maverick-17b-128e-instruct", label: "llama-4-maverick", tier: "unverified",
      note: "P01 기준 미검증 · P03에서 NVIDIA 서빙 장애로 측정 불가 이력." },
    { id: "mistralai/mistral-large-3-675b-instruct-2512", label: "mistral-large-3", tier: "unverified",
      note: "P01 기준 미검증 · P03 채점기 역할에서 퇴행 생성 루프 결함 이력(질문생성 역할만 정상)." },
    { id: "z-ai/glm-5.2", label: "glm-5.2", tier: "unverified",
      note: "P01 기준 미검증 · P03에서 쿼타 소진 이력." },
    { id: "minimaxai/minimax-m3", label: "minimax-m3", tier: "unverified",
      note: "P01 기준 미검증 · P03에서 100회 반복 중 DEGRADED 재발 이력." },
  ];

  function renderInput(container) {
    if (!selectedModel) selectedModel = (LabApp.getManifest().shared || {}).default_model;
    container.innerHTML = `
      <div class="input-panel">
        <h3>교안 PDF 입력</h3>
        <div class="dropzone" id="p01-dropzone">여기로 PDF를 드래그하거나 클릭해서 선택</div>
        <input type="file" id="p01-pdf-input" accept=".pdf" class="hidden">
        <div class="input-row">
          <input type="password" id="p01-pdf-password" placeholder="PDF 암호 (있는 경우, 서버로 전송되지 않음)">
        </div>
        <p id="p01-pdf-status" style="color:var(--ink-faint); font-size:0.72rem; margin-top:6px;"></p>
        <p style="color:var(--status-blocked); font-size:0.72rem; margin-top:4px;">
          텍스트 추출은 pdf.js를 쓴다 — 원본 파이프라인의 pdftotext -layout과 완전히 동일한 결과는 아니다
          (모든 실행 기록에 extractor: "pdfjs"로 표시됨).
        </p>
        <div class="field-label" style="margin-top:14px;">모델 선택 (11종 — 3개 프롬프트 단계+JSON 복구 전부에 적용)</div>
        <div class="model-toggle-group" id="p01-model-group"></div>
        <p class="model-note" id="p01-model-note"></p>
      </div>`;

    const dropzone = container.querySelector("#p01-dropzone");
    const fileInput = container.querySelector("#p01-pdf-input");
    const passwordInput = container.querySelector("#p01-pdf-password");
    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("drag-over"); });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("drag-over");
      if (e.dataTransfer.files[0]) handlePdfFile(e.dataTransfer.files[0], container);
    });
    fileInput.addEventListener("change", () => {
      if (fileInput.files[0]) handlePdfFile(fileInput.files[0], container);
    });
    passwordInput.addEventListener("input", () => { pdfPassword = passwordInput.value; });
    renderModelToggle(container);
  }

  function renderModelToggle(container) {
    const group = container.querySelector("#p01-model-group");
    const note = container.querySelector("#p01-model-note");
    group.innerHTML = MODEL_CHOICES.map((m) => {
      const cls = ["model-chip"];
      if (m.id === selectedModel) cls.push("active");
      if (m.tier === "bad") cls.push("warn");
      return `<button type="button" class="${cls.join(" ")}" data-model="${LabApp.escapeHtml(m.id)}">${LabApp.escapeHtml(m.label)}</button>`;
    }).join("");
    const updateNote = () => {
      const m = MODEL_CHOICES.find((x) => x.id === selectedModel);
      note.textContent = m ? m.note : "";
      note.className = "model-note" + (m && m.tier === "bad" ? " warn" : "");
    };
    group.querySelectorAll(".model-chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedModel = btn.dataset.model;
        group.querySelectorAll(".model-chip").forEach((b) => b.classList.toggle("active", b === btn));
        updateNote();
      });
    });
    updateNote();
  }

  async function handlePdfFile(file, container) {
    const status = container.querySelector("#p01-pdf-status");
    status.textContent = `읽는 중: ${file.name}...`;
    pdfBytes = new Uint8Array(await file.arrayBuffer());
    status.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(1)}MB) 로드됨 — 실행 버튼을 누르면 페이지 수를 확인한다`;
  }

  async function waitForPdfJs() {
    if (window.pdfjsLib) return;
    if (window.pdfjsLibLoadError) throw window.pdfjsLibLoadError;
    await new Promise((resolve) => window.addEventListener("pdfjs-ready", resolve, { once: true }));
    if (window.pdfjsLibLoadError) throw window.pdfjsLibLoadError;
  }

  async function extractPages(onProgress) {
    await waitForPdfJs();
    const doc = await window.pdfjsLib.getDocument({ data: pdfBytes.slice(), password: pdfPassword || undefined }).promise;
    const pages = [];
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      const content = await page.getTextContent();
      const text = content.items.map((it) => it.str).join(" ");
      pages.push(text);
      if (i % 10 === 0 || i === doc.numPages) onProgress(`페이지 텍스트 추출 ${i}/${doc.numPages}`);
    }
    return pages;
  }

  // D155 (2026-07-15): max_chunks removed -- it used to cap this at a "smoke test" of 3
  // chunks by default, which a user could raise to null for a full run, but nothing
  // stopped it from silently staying at 3 for a real document. User asked for this to be
  // structural: chunk count is always ceil(pages/chunkSize), covering the whole PDF, with
  // no control anywhere that could leave a run silently partial.
  function buildChunks(pages, chunkSize) {
    const chunks = [];
    for (let start = 1; start <= pages.length; start += chunkSize) {
      const end = Math.min(start + chunkSize - 1, pages.length);
      const text = pages.slice(start - 1, end).join("\n");
      chunks.push({ start, end, range: `${start}-${end}`, text });
    }
    return chunks;
  }

  function makeUnitMap(chunkResults) {
    const unitMap = {};
    for (const chunk of chunkResults) {
      for (const unit of chunk.units || []) {
        const unitId = String(unit.unit_id || "unknown");
        if (!unitMap[unitId]) {
          unitMap[unitId] = { unit_id: unitId, unit_title: unit.unit_title || "", source_pages: [], concepts: [], code_examples: [], cautions: [] };
        }
        unitMap[unitId].source_pages.push(...(unit.source_pages || []));
      }
      for (const concept of chunk.concepts || []) {
        const targetUnit = (chunk.units && chunk.units[0] && String(chunk.units[0].unit_id)) || "unknown";
        if (!unitMap[targetUnit]) continue;
        const item = { name: concept.name || "unnamed", summary: concept.summary || "", evidence: concept.evidence || "", source_pages: concept.source_pages || [], chunk_range: chunk.chunk_range };
        const kind = concept.kind || "concept";
        const bucket = kind === "code_example" ? "code_examples" : kind === "caution" ? "cautions" : "concepts";
        unitMap[targetUnit][bucket].push(item);
      }
    }
    for (const u of Object.values(unitMap)) u.source_pages = [...new Set(u.source_pages)].sort((a, b) => a - b);
    return unitMap;
  }

  function buildGraphNodes(unitMap) {
    const nodes = [];
    for (const [unitId, unit] of Object.entries(unitMap)) {
      nodes.push({ id: `unit:${unitId}`, label: `Unit ${unitId} ${unit.unit_title}`.trim(), type: "unit", source_pages: unit.source_pages });
      for (const [group, relation] of [["concepts", "concept"], ["code_examples", "code_example"], ["cautions", "caution"]]) {
        (unit[group] || []).forEach((item, idx) => {
          nodes.push({ id: `${group}:${unitId}:${idx + 1}`, label: item.name, type: relation, source_pages: item.source_pages, summary: item.summary });
        });
      }
    }
    return nodes;
  }

  async function callPromptStage(stageId, values, tokensParam) {
    const system = LabApp.resolveTemplate("p01", stageId, "system");
    const template = LabApp.resolveTemplate("p01", stageId, "user_template");
    const userMsg = LabApp.fillTemplate(template, values);
    const maxTokens = LabApp.resolveParam("p01", stageId, "max_tokens") || 1800;
    const model = LabApp.resolveParam("p01", stageId, "model") || selectedModel;
    const choice = await LabLLM.chatJSON({ model, messages: [{ role: "system", content: system }, { role: "user", content: userMsg }], maxTokens });
    try {
      return LabLLM.extractJsonObject(choice.content);
    } catch (e) {
      // mirrors chat_json()'s repair-prompt fallback in the real pipeline
      const repairStage = LabApp.getStage("p01", "p01-json-repair");
      const repairMsg = LabApp.fillTemplate(repairStage.user_template, { malformed_content: (choice.content || "").slice(0, 14000) });
      const repaired = await LabLLM.chatJSON({ model, messages: [{ role: "system", content: repairStage.system }, { role: "user", content: repairMsg }], maxTokens });
      return LabLLM.extractJsonObject(repaired.content);
    }
  }

  async function run() {
    const pipelineId = "p01";
    LabApp.setStatus(pipelineId, "실행 중...", "running");
    const startedAt = new Date();
    LabApp.startTimer(pipelineId);
    try {
      if (!pdfBytes) throw new Error("PDF를 먼저 업로드하세요");
      if (!LabConfig.get("nvidia-key") || !LabConfig.get("proxy-url")) {
        throw new Error("P01은 LLM 호출이 필요합니다 — 상단 연결 설정에 NVIDIA 키와 프록시 URL을 입력하세요");
      }
      const courseLabel = LabApp.resolveParam("p01", "p01-2", "course_label") || "Java";
      const chunkSize = LabApp.resolveParam("p01", "p01-1", "chunk_size") || 10;

      LabApp.log(pipelineId, `모델: ${selectedModel}`);
      LabApp.log(pipelineId, "PDF 텍스트 추출 중 (pdf.js)...");
      const pages = await extractPages((msg) => LabApp.log(pipelineId, msg));
      const chunks = buildChunks(pages, chunkSize);
      LabApp.log(pipelineId, `${pages.length}페이지 → ${chunks.length}개 청크 (chunk_size=${chunkSize}, 전체 문서)`);

      // D156 (2026-07-15): chunks analysed in parallel instead of one-at-a-time -- they
      // don't depend on each other (makeUnitMap() below just aggregates whatever comes
      // back, order doesn't matter), and the proxy already treats each callPromptStage()
      // as its own Cloudflare Queue job with its own retry budget (D144/D145), so nothing
      // on the backend assumes these arrive sequentially. Each mapped function catches
      // its own error and always resolves (never rejects) so one failing chunk can't
      // abort the rest via Promise.all -- same fault-tolerance as the old sequential
      // loop, just concurrent. Promise.all preserves chunks' input order in the result
      // array regardless of which one actually finishes first.
      LabApp.log(pipelineId, `청크 ${chunks.length}개 동시 분석 시작: p${chunks.map((c) => c.range).join(", p")}`);
      const chunkResults = await Promise.all(chunks.map(async (chunk) => {
        try {
          const result = await callPromptStage("p01-2", {
            course_label: courseLabel, chunk_range: chunk.range, chunk_start: chunk.start, chunk_end: chunk.end,
            chunk_text: chunk.text.slice(0, 18000),
          });
          result.chunk_range = result.chunk_range || chunk.range;
          LabApp.log(pipelineId, `청크 p${chunk.range} 완료`);
          return result;
        } catch (err) {
          LabApp.log(pipelineId, `청크 p${chunk.range} 실패: ${err.message}`);
          return { chunk_range: chunk.range, units: [], concepts: [], error: String(err.message) };
        }
      }));

      const unitMap = makeUnitMap(chunkResults.filter((c) => !c.error));
      LabApp.log(pipelineId, `unit_map 생성: 유닛 ${Object.keys(unitMap).length}개`);

      const refineIters = LabApp.resolveParam("p01", "p01-3", "refine_iters") || 2;
      const audits = [];
      for (let i = 1; i <= refineIters; i++) {
        LabApp.log(pipelineId, `refine 반복 ${i}/${refineIters}...`);
        try {
          const audit = await callPromptStage("p01-3", {
            course_label: courseLabel, iteration: i, unit_map_json: JSON.stringify(unitMap).slice(0, 24000),
          });
          audits.push(audit);
        } catch (err) {
          LabApp.log(pipelineId, `refine ${i} 실패: ${err.message}`);
        }
      }

      const graphNodes = buildGraphNodes(unitMap);
      LabApp.log(pipelineId, "질문 생성 중...");
      let questions = { questions: [] };
      try {
        questions = await callPromptStage("p01-4", { course_label: courseLabel, graph_nodes_json: JSON.stringify(graphNodes).slice(0, 24000) });
      } catch (err) {
        LabApp.log(pipelineId, `질문 생성 실패: ${err.message}`);
      }

      const finishedAt = new Date();
      LabApp.stopTimer(pipelineId);
      LabApp.setStatus(pipelineId, "완료", "done");
      const result = { unit_map: unitMap, refine_audits: audits, questions, chunk_count: chunks.length, extractor: "pdfjs" };
      renderResults(result);
      await maybeSaveRun(result, startedAt, finishedAt);
    } catch (err) {
      LabApp.stopTimer(pipelineId);
      console.error(err);
      LabApp.setStatus(pipelineId, `오류: ${err.message}`, "error");
      LabApp.log(pipelineId, `오류: ${err.message}`);
    }
  }

  function renderResults(result) {
    let html = `<p>유닛 <b>${Object.keys(result.unit_map).length}</b>개 · 질문 <b>${(result.questions.questions || []).length}</b>개 · 청크 <b>${result.chunk_count}</b>개
      · <code>extractor: pdfjs</code></p>`;
    for (const q of (result.questions.questions || []).slice(0, 10)) {
      html += `<div class="finding-card">
        <div class="fid">${LabApp.escapeHtml(q.unit || "")} · pages: ${LabApp.escapeHtml(JSON.stringify(q.source_pages || []))}</div>
        <div>${LabApp.escapeHtml(q.question || "")}</div>
      </div>`;
    }
    html += `<p class="field-label" style="margin-top:14px;">원본 JSON</p><pre>${LabApp.escapeHtml(JSON.stringify(result, null, 2)).slice(0, 20000)}</pre>`;
    LabApp.showResults(html);
  }

  async function maybeSaveRun(result, startedAt, finishedAt) {
    if (!LabDB.isConfigured()) {
      LabApp.log("p01", "Supabase 미설정 — 결과는 화면에만 표시됨");
      return;
    }
    try {
      await LabDB.saveRun({
        pipeline: "p01",
        model: selectedModel,
        input_meta: { extractor: "pdfjs", chunk_count: result.chunk_count },
        overrides: {},
        rubric_overridden: false,
        artifacts: [{ kind: "unit_map", content: result.unit_map }, { kind: "questions", content: result.questions }],
        started_at: startedAt.toISOString(), finished_at: finishedAt.toISOString(),
      });
      LabApp.log("p01", `결과가 팀 DB에 저장됨 (소요시간 ${LabApp.formatElapsed(finishedAt - startedAt)})`);
    } catch (err) {
      LabApp.log("p01", `DB 저장 실패(결과는 화면에 남아있음): ${err.message}`);
    }
  }

  LabApp.registerRunner("p01", { renderInput, run });
  return { renderInput, run };
})();
