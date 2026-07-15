// P03 v1 is human-in-the-loop only (persona/AI-answerer mode is v2, PLAN.md section 5) --
// a teammate types real answers to real generated questions. Question generation +
// grading are real NVIDIA calls (same manifest prompts as P01/P02). Answer classification
// (surface/partial/defended) is NOT an LLM call in the real pipeline either -- it's the
// same deterministic regex classifiers P02 already proved run fine in Pyodide, so this
// reuses that shared instance rather than re-implementing the classifiers in JS.
const P03Runner = (() => {
  const REPO_RAW_BASE = "https://raw.githubusercontent.com/popixoxipop-collab/Code_reviewer_with_feedback/main/";
  const CLASSIFIER_FILES = [
    "judgment/isolation_classifier.py",
    "judgment/isolation_hook.py",
    "feedback/reflection_signal.py",
    "feedback/reflection_hook.py",
    "judgment/isolation_categories/role_separation/patterns.json",
    "judgment/isolation_categories/domain_irrelevance/patterns.json",
    "judgment/isolation_categories/alt_storage_or_scope/patterns.json",
    "judgment/isolation_categories/perf_optimization/patterns.json",
    "feedback/reflection_patterns/new_judgment/patterns.json",
    "feedback/reflection_patterns/concrete_improvement/patterns.json",
    "feedback/reflection_patterns/reason_explanation/patterns.json",
    "feedback/reflection_patterns/self_error_recognition/patterns.json",
  ];
  const LEVELS = ["l1", "l2", "l3", "reflection"];

  let findings = [];
  let selectedFinding = null;
  let pendingAnswerResolve = null;
  // D176: real source content for the currently-selected finding, when it came from P02's
  // "인터뷰 시작" connector (see loadFindingFromP02). null for manual JSON-paste findings,
  // which never had a `files` map to draw real code from in the first place.
  let pendingCodeContext = null;
  // D176: Team-IZ 검증세션 패턴 -- 채점 결과를 세션 중엔 숨기고, 완료 후 별도 클릭으로만 노출.
  // run()이 끝나도 renderResults()를 바로 부르지 않고 여기 보관해뒀다가 "리포트 보기"에서 사용.
  let pendingReportResult = null;
  let countdownIntervalId = null;

  function renderInput(container) {
    container.innerHTML = `
      <div class="input-panel">
        <h3>인터뷰 대상 finding</h3>
        <p style="color:var(--ink-faint); font-size:0.78rem;">P02 결과 화면의 "인터뷰 시작"을 누르면 자동으로 채워집니다. 직접 붙여넣기도 가능합니다.</p>
        <textarea id="p03-findings-input" placeholder='[{"id": "architecture-diffusion:App.js", "file": "App.js", "finding": "...", "priority": "질문 대상"}]' style="width:100%; min-height:80px; font-family:var(--mono); font-size:0.76rem; padding:8px; border-radius:4px; border:1px solid var(--line-strong); background:var(--bg-panel); color:var(--ink);"></textarea>
        <div class="input-row">
          <button class="secondary" id="p03-load-findings">findings 불러오기</button>
          <select id="p03-finding-select" style="font-family:var(--mono); font-size:0.78rem; padding:7px; border-radius:4px; border:1px solid var(--line-strong); background:var(--bg-panel); color:var(--ink); flex:1; min-width:220px;">
            <option value="">— finding을 먼저 불러오세요 —</option>
          </select>
        </div>
      </div>
      <div class="p03-session hidden" id="p03-session">
        <div class="p03-session-code">
          <div class="p03-session-code-header">📄 <span id="p03-session-filename">-</span></div>
          <pre class="p03-session-code-body" id="p03-session-code-body">(코드 컨텍스트 없음)</pre>
        </div>
        <div class="p03-session-chat">
          <div class="p03-session-status">
            <span id="p03-progress">질문 -/-</span>
            <span id="p03-countdown"></span>
          </div>
          <div id="p03-transcript"></div>
          <div id="p03-answer-row" class="hidden">
            <textarea id="p03-answer-input" placeholder="답변을 입력하세요..." style="width:100%; min-height:70px; font-family:var(--sans); font-size:0.84rem; padding:10px; border-radius:4px; border:1px solid var(--line-strong); background:var(--bg-panel); color:var(--ink);"></textarea>
            <button class="primary" id="p03-submit-answer" style="margin-top:8px;">답변 제출</button>
          </div>
        </div>
      </div>
      <div class="input-panel hidden" id="p03-report-gate">
        <p style="margin:0 0 10px;">🔒 인터뷰 완료 — Team-IZ 검증세션 패턴에 따라 채점 결과는 세션 중에는 비공개입니다.</p>
        <button class="secondary" id="p03-show-report">리포트 보기 →</button>
      </div>`;

    container.querySelector("#p03-load-findings").addEventListener("click", () => {
      const raw = container.querySelector("#p03-findings-input").value;
      try {
        findings = JSON.parse(raw);
        if (!Array.isArray(findings)) throw new Error("배열이어야 함");
        selectedFinding = null;
        pendingCodeContext = null; // D176: 수동 붙여넣기는 실제 파일 내용을 알 길이 없음
        pendingReportResult = null;
        hideReportGate();
        const select = container.querySelector("#p03-finding-select");
        select.innerHTML = findings.map((f, i) => `<option value="${i}">${LabApp.escapeHtml(f.id || `finding ${i}`)}</option>`).join("");
        LabApp.log("p03", `finding ${findings.length}건 로드됨`);
      } catch (err) {
        LabApp.log("p03", `findings JSON 파싱 실패: ${err.message}`);
      }
    });
    container.querySelector("#p03-finding-select").addEventListener("change", (e) => {
      selectedFinding = findings[parseInt(e.target.value, 10)] || null;
      pendingCodeContext = null; // D176: 드롭다운 재선택 시 이전(P02발) 코드 컨텍스트는 항상 폐기
      pendingReportResult = null;
      hideReportGate();
    });
    container.querySelector("#p03-show-report").addEventListener("click", () => {
      if (pendingReportResult) renderResults(pendingReportResult);
    });
  }

  function hideReportGate() {
    const gate = document.getElementById("p03-report-gate");
    if (gate) gate.classList.add("hidden");
  }

  // D176: entry point called from p02-runner.js's "인터뷰 시작" button. The caller switches
  // to the P03 tab BEFORE calling this (so renderPipeline("p03") has already built the DOM
  // once, synchronously -- see app.js's renderPipeline/D-K), so the direct-DOM writes below
  // are safe. This function itself never runs anything -- it only pre-fills state/DOM.
  // D178: the caller now calls P03Runner.run() immediately after this (user's explicit
  // choice over a manual-confirm step), so in practice a real LLM call fires right after
  // this returns; run()'s own NVIDIA key/proxy guard is what's left protecting an
  // unconfigured teammate from a confusing failure.
  function loadFindingFromP02(finding, codeContext) {
    findings = [finding];
    selectedFinding = finding;
    pendingCodeContext = codeContext || null;
    pendingReportResult = null;
    hideReportGate();
    const select = document.getElementById("p03-finding-select");
    if (select) {
      select.innerHTML = `<option value="0">${LabApp.escapeHtml(finding.id || "finding 0")}</option>`;
      select.value = "0";
    }
    const textarea = document.getElementById("p03-findings-input");
    if (textarea) textarea.value = JSON.stringify([finding], null, 2);
    LabApp.log("p03", `P02에서 finding 전달받음: ${finding.id}${pendingCodeContext ? ` (코드 컨텍스트 ${pendingCodeContext.length}자 포함)` : " (코드 컨텍스트 없음)"}`);
  }

  function findingCategory(findingId) {
    // mirrors feedback/evidence_bridge.py::finding_category -- id prefix before the first ':'
    return (findingId || "").split(":")[0];
  }

  async function ensureClassifiers(onProgress) {
    const pyodide = await LabPyodide.get(onProgress);
    if (!LabPyodide.isLoaded("p03")) {
      await LabPyodide.loadFiles(pyodide, REPO_RAW_BASE, CLASSIFIER_FILES, "/lib", null);
      pyodide.runPython(`
import sys
for p in ["/lib", "/lib/judgment", "/lib/feedback"]:
    if p not in sys.path:
        sys.path.insert(0, p)
`);
      LabPyodide.markLoaded("p03");
    }
    return pyodide;
  }

  async function classifyAnswer(category, answerText, level) {
    const pyodide = await ensureClassifiers();
    pyodide.globals.set("_category", category);
    pyodide.globals.set("_answer", answerText);
    pyodide.globals.set("_level", level);
    pyodide.runPython(`
import json
if _category == "cognition-isolation":
    from isolation_classifier import classify_justification
    _r = classify_justification(_answer)
    _n = len(_r["matched_categories"])
    _verdict = "surface" if _n == 0 else ("partial" if _n == 1 else "defended")
else:
    from reflection_signal import evaluate_reflection
    _r = evaluate_reflection(_answer)
    if _level == "reflection":
        if not _r["required_ok"]:
            _verdict = "surface"
        elif _r["optional_matches"] < _r["min_optional_required"]:
            _verdict = "partial"
        else:
            _verdict = "defended"
    else:
        _n = _r["optional_matches"]
        _verdict = "surface" if _n == 0 else ("partial" if _n == 1 else "defended")
_classify_result = json.dumps({"verdict": _verdict, "raw": _r})
`);
    return JSON.parse(pyodide.globals.get("_classify_result"));
  }

  // D176: Team-IZ 검증세션 패턴 -- verdict는 세션 중 화면에 절대 안 보여준다(분류 자체는
  // 여전히 내부적으로 진행 로직에 쓰임, 표시만 안 함). 최종 채점은 "리포트 보기" 클릭 후
  // renderResults()에서만 노출.
  function appendTranscriptEntry(level, question, answer) {
    const el = document.getElementById("p03-transcript");
    const div = document.createElement("div");
    div.className = "finding-card";
    div.innerHTML = `<div class="fid">[${LabApp.escapeHtml(level.toUpperCase())}]</div>
      <div><b>질문:</b> ${LabApp.escapeHtml(question)}</div>
      ${answer ? `<div style="margin-top:6px;"><b>답변:</b> ${LabApp.escapeHtml(answer)}</div>` : ""}`;
    el.appendChild(div);
  }

  function waitForAnswer() {
    const row = document.getElementById("p03-answer-row");
    const input = document.getElementById("p03-answer-input");
    row.classList.remove("hidden");
    input.value = "";
    input.focus();
    return new Promise((resolve) => { pendingAnswerResolve = resolve; });
  }

  function wireAnswerSubmit() {
    document.getElementById("p03-submit-answer").addEventListener("click", () => {
      const input = document.getElementById("p03-answer-input");
      const val = input.value.trim();
      if (!val || !pendingAnswerResolve) return;
      document.getElementById("p03-answer-row").classList.add("hidden");
      const resolve = pendingAnswerResolve;
      pendingAnswerResolve = null;
      resolve(val);
    });
  }

  // D176: display-only countdown next to the live transcript -- reuses LabApp.formatElapsed
  // (already mm:ss) rather than re-implementing the same formatting. Deliberately never
  // force-ends the session at 0 (see prompt_manifest.json p03-6 note): aborting mid-LLM-call
  // or mid-answer-typing risks losing a teammate's real answer, which this tool has
  // consistently treated as worse than an over-long session (D162's whole reason for
  // existing was "never silently lose output").
  function startCountdown(totalMinutes) {
    stopCountdown();
    const el = document.getElementById("p03-countdown");
    if (!el || !totalMinutes) return;
    const totalMs = totalMinutes * 60 * 1000;
    const startMs = Date.now();
    const tick = () => {
      const remainingMs = Math.max(0, totalMs - (Date.now() - startMs));
      el.textContent = `남은 ${LabApp.formatElapsed(remainingMs)}`;
      el.classList.toggle("p03-countdown-over", remainingMs <= 0);
    };
    tick();
    countdownIntervalId = setInterval(tick, 1000);
  }

  function stopCountdown() {
    if (countdownIntervalId) { clearInterval(countdownIntervalId); countdownIntervalId = null; }
    const el = document.getElementById("p03-countdown");
    if (el) { el.textContent = ""; el.classList.remove("p03-countdown-over"); }
  }

  function buildLevelPrompt(level, finding, codeContext, transcript, classification) {
    const codeBlock = codeContext ? `\n## 실제 코드\n\`\`\`\n${codeContext}\n\`\`\`\n` : "";
    const headerStage = LabApp.getStage("p03", "p03-1");
    const header = LabApp.fillTemplate(headerStage.shared_header, { finding_text: finding.finding || "", finding_file: finding.file || "", code_block: codeBlock });

    if (level === "l1") return header + LabApp.resolveTemplate("p03", "p03-1", "level_template");

    const transcriptText = transcript.map((t) => `[${t.level.toUpperCase()}] 질문: ${t.question}\n[${t.level.toUpperCase()}] 학생 답변: ${t.answer}`).join("\n");
    const verdictNote = { surface: "표면적(근거·구체성 부족)", partial: "부분적(일부 근거는 있으나 아직 충분히 깊지 않음)" }[classification.verdict] || classification.verdict;
    const stageId = { l2: "p03-2", l3: "p03-3", reflection: "p03-4" }[level];
    return header + LabApp.fillTemplate(LabApp.resolveTemplate("p03", stageId, "level_template"), { transcript: transcriptText, verdict_note: verdictNote });
  }

  async function generateQuestion(level, finding, codeContext, transcript, classification) {
    const model = LabApp.resolveParam("p03", "p03-1", "model") || (LabApp.getManifest().shared || {}).default_model;
    const prompt = buildLevelPrompt(level, finding, codeContext, transcript, classification);
    const tool = { name: "ask_question", description: "학생에게 던질 질문 하나를 생성한다.", input_schema: { type: "object", properties: { question: { type: "string" } }, required: ["question"] } };
    const result = await LabLLM.chatTool({ model, messages: [{ role: "user", content: prompt }], tool, maxTokens: 2048 });
    return result.question;
  }

  async function gradeAnswer(finding, question, answer) {
    const stage = LabApp.getStage("p03", "p03-7");
    const rubric = (LabApp.getOverride("p03", "p03-7") || {}).rubric || stage.rubric;
    const rubricOverridden = Boolean((LabApp.getOverride("p03", "p03-7") || {}).rubric_overridden);
    let rubricBlock = "";
    for (const [axis, levels] of Object.entries(rubric)) {
      rubricBlock += `### ${axis}\n`;
      for (const score of ["5", "4", "3", "2", "1"]) rubricBlock += `  ${score}점: ${levels[score]}\n`;
    }
    const userMsg = LabApp.fillTemplate(LabApp.resolveTemplate("p03", "p03-7", "user_template"), {
      rubric_block: rubricBlock, finding_text: finding.finding || "", finding_file: finding.file || "", question, answer,
    });
    const axes = Object.keys(rubric);
    const tool = {
      name: "grade_interview_answer",
      description: "학생 답변을 FR-04-01 5축 루브릭으로 채점한다.",
      input_schema: { type: "object", properties: Object.fromEntries(axes.map((a) => [a, { type: "object", properties: { score: { type: "integer" }, evidence: { type: "string" } }, required: ["score", "evidence"] }])), required: axes },
    };
    const model = LabApp.resolveParam("p03", "p03-7", "model") || (LabApp.getManifest().shared || {}).default_model;
    const grades = await LabLLM.chatTool({ model, messages: [{ role: "user", content: userMsg }], tool, maxTokens: 2048 });
    return { grades, rubric_overridden: rubricOverridden };
  }

  async function run() {
    const pipelineId = "p03";
    if (!selectedFinding) { LabApp.setStatus(pipelineId, "먼저 finding을 불러오고 선택하세요", "error"); return; }
    if (!LabConfig.get("nvidia-key") || !LabConfig.get("proxy-url")) {
      LabApp.setStatus(pipelineId, "NVIDIA 키 + 프록시 URL이 필요합니다", "error");
      return;
    }
    document.getElementById("p03-session").classList.remove("hidden");
    hideReportGate();
    document.getElementById("p03-transcript").innerHTML = "";
    document.getElementById("p03-progress").textContent = "질문 -/-";
    document.getElementById("p03-session-filename").textContent = selectedFinding.file || "(특정 파일 없음)";
    wireAnswerSubmit();
    LabApp.setStatus(pipelineId, "진행 중...", "running");
    const startedAt = new Date();
    LabApp.startTimer(pipelineId);
    const sessionTimeoutMinutes = LabApp.resolveParam("p03", "p03-6", "session_timeout_minutes") || 0;
    startCountdown(sessionTimeoutMinutes);
    try {
      await ensureClassifiers((msg) => LabApp.log(pipelineId, msg));
      const category = findingCategory(selectedFinding.id);

      // D176: fixes a pre-existing bug -- generateQuestion() was always called with a
      // hardcoded null codeContext, so every P03 question this tool ever generated was
      // written with zero real-code visibility no matter how the finding was loaded.
      // codeContext now flows from the real P02 file content (when the finding arrived via
      // the new "인터뷰 시작" connector) through the SAME char cap the real pipeline's own
      // manifest already specifies (p03-1.truncation.code_context) -- reusing an
      // already-established number instead of inventing one.
      const stage1 = LabApp.getStage("p03", "p03-1");
      const codeCap = stage1 && stage1.truncation && stage1.truncation.code_context;
      const codeContext = pendingCodeContext
        ? (codeCap ? pendingCodeContext.slice(0, codeCap) : pendingCodeContext)
        : null;
      document.getElementById("p03-session-code-body").textContent = codeContext || "(코드 컨텍스트 없음 -- 특정 파일에 결부되지 않은 finding이거나 수동 입력)";
      LabApp.log(pipelineId, codeContext ? `코드 컨텍스트 포함 (${codeContext.length}자)` : "코드 컨텍스트 없음 -- 질문이 파일 내용 없이 생성됨");

      const transcript = [];
      let verdict = "exhausted_at_cap";
      const maxTurns = LabApp.resolveParam("p03", "p03-6", "max_turns") || 4;
      const totalTurns = Math.min(LEVELS.length, maxTurns);

      for (let i = 0; i < totalTurns; i++) {
        const level = LEVELS[i];
        document.getElementById("p03-progress").textContent = `질문 ${i + 1}/${totalTurns}`;
        const prevClassification = transcript.length ? transcript[transcript.length - 1].classification : null;
        LabApp.log(pipelineId, `${level.toUpperCase()} 질문 생성 중...`);
        const question = await generateQuestion(level, selectedFinding, codeContext, transcript, prevClassification);
        appendTranscriptEntry(level, question, null);
        LabApp.log(pipelineId, "답변 대기 중...");
        const answer = await waitForAnswer();
        LabApp.log(pipelineId, "답변 분류 중 (결정론적 분류기, LLM 아님)...");
        const classification = await classifyAnswer(category, answer, level);
        transcript.push({ level, question, answer, classification });
        appendTranscriptEntry(level, question, answer);
        if (classification.verdict === "defended") { verdict = "defended"; break; }
      }

      LabApp.log(pipelineId, "5축 채점 중...");
      const last = transcript[transcript.length - 1];
      const { grades, rubric_overridden } = await gradeAnswer(selectedFinding, last.question, last.answer);

      const finishedAt = new Date();
      LabApp.stopTimer(pipelineId);
      stopCountdown();
      LabApp.setStatus(pipelineId, "완료 (채점은 비공개 -- 리포트 보기)", "done");
      const result = { finding: selectedFinding, verdict, turns: transcript.length, transcript, grades, rubric_overridden };
      pendingReportResult = result;
      const gate = document.getElementById("p03-report-gate");
      if (gate) gate.classList.remove("hidden");
      await maybeSaveRun(result, startedAt, finishedAt);
    } catch (err) {
      LabApp.stopTimer(pipelineId);
      stopCountdown();
      console.error(err);
      LabApp.setStatus(pipelineId, `오류: ${err.message}`, "error");
      LabApp.log(pipelineId, `오류: ${err.message}`);
      await LabApp.saveFailedRun("p03", (LabApp.getManifest().shared || {}).default_model, err, startedAt);
    }
  }

  function renderResults(result) {
    let html = `<p>verdict: <b>${LabApp.escapeHtml(result.verdict)}</b> · ${result.turns}턴${result.rubric_overridden ? ' · <span style="color:var(--status-blocked);">rubric_overridden</span>' : ""}</p>`;
    html += `<div class="param-grid">`;
    for (const [axis, g] of Object.entries(result.grades)) {
      html += `<div class="finding-card"><div class="fid">${LabApp.escapeHtml(axis)}: ${LabApp.escapeHtml(String(g.score))}점</div><div>${LabApp.escapeHtml(g.evidence || "")}</div></div>`;
    }
    html += `</div>`;
    html += LabApp.jsonResultBlock("원본 JSON", result, "p03-result.json");
    LabApp.showResults(html);
  }

  async function maybeSaveRun(result, startedAt, finishedAt) {
    if (!LabDB.isConfigured()) {
      LabApp.log("p03", "Supabase 미설정 — 결과는 화면에만 표시됨");
      return;
    }
    try {
      await LabDB.saveRun({
        pipeline: "p03",
        model: (LabApp.getManifest().shared || {}).default_model,
        input_meta: { finding_id: result.finding.id },
        overrides: {},
        rubric_overridden: result.rubric_overridden,
        artifacts: [{ kind: "transcript", content: result.transcript }, { kind: "grades", content: result.grades }],
        started_at: startedAt.toISOString(), finished_at: finishedAt.toISOString(),
      });
      LabApp.log("p03", `결과가 팀 DB에 저장됨 (소요시간 ${LabApp.formatElapsed(finishedAt - startedAt)})`);
    } catch (err) {
      LabApp.log("p03", `DB 저장 실패(결과는 화면에 남아있음): ${err.message}`);
    }
  }

  LabApp.registerRunner("p03", { renderInput, run });
  return { renderInput, run, loadFindingFromP02 };
})();
