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

  function renderInput(container) {
    container.innerHTML = `
      <div class="input-panel">
        <h3>인터뷰 대상 finding</h3>
        <p style="color:var(--ink-faint); font-size:0.78rem;">P02 실행 결과 JSON(findings 배열)을 붙여넣거나 파일로 올리세요.</p>
        <textarea id="p03-findings-input" placeholder='[{"id": "architecture-diffusion:App.js", "file": "App.js", "finding": "...", "priority": "질문 대상"}]' style="width:100%; min-height:80px; font-family:var(--mono); font-size:0.76rem; padding:8px; border-radius:4px; border:1px solid var(--line-strong); background:var(--bg-panel); color:var(--ink);"></textarea>
        <div class="input-row">
          <button class="secondary" id="p03-load-findings">findings 불러오기</button>
          <select id="p03-finding-select" style="font-family:var(--mono); font-size:0.78rem; padding:7px; border-radius:4px; border:1px solid var(--line-strong); background:var(--bg-panel); color:var(--ink); flex:1; min-width:220px;">
            <option value="">— finding을 먼저 불러오세요 —</option>
          </select>
        </div>
      </div>
      <div class="input-panel" id="p03-interview-panel" style="display:none;">
        <h3>인터뷰</h3>
        <div id="p03-transcript"></div>
        <div id="p03-answer-row" style="display:none;">
          <textarea id="p03-answer-input" placeholder="답변을 입력하세요..." style="width:100%; min-height:70px; font-family:var(--sans); font-size:0.84rem; padding:10px; border-radius:4px; border:1px solid var(--line-strong); background:var(--bg-panel); color:var(--ink);"></textarea>
          <button class="primary" id="p03-submit-answer" style="margin-top:8px;">답변 제출</button>
        </div>
      </div>`;

    container.querySelector("#p03-load-findings").addEventListener("click", () => {
      const raw = container.querySelector("#p03-findings-input").value;
      try {
        findings = JSON.parse(raw);
        if (!Array.isArray(findings)) throw new Error("배열이어야 함");
        const select = container.querySelector("#p03-finding-select");
        select.innerHTML = findings.map((f, i) => `<option value="${i}">${LabApp.escapeHtml(f.id || `finding ${i}`)}</option>`).join("");
        LabApp.log("p03", `finding ${findings.length}건 로드됨`);
      } catch (err) {
        LabApp.log("p03", `findings JSON 파싱 실패: ${err.message}`);
      }
    });
    container.querySelector("#p03-finding-select").addEventListener("change", (e) => {
      selectedFinding = findings[parseInt(e.target.value, 10)] || null;
    });
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

  function appendTranscriptEntry(level, question, answer, verdict) {
    const el = document.getElementById("p03-transcript");
    const div = document.createElement("div");
    div.className = "finding-card";
    div.innerHTML = `<div class="fid">[${LabApp.escapeHtml(level.toUpperCase())}]${verdict ? " · verdict: " + LabApp.escapeHtml(verdict) : ""}</div>
      <div><b>질문:</b> ${LabApp.escapeHtml(question)}</div>
      ${answer ? `<div style="margin-top:6px;"><b>답변:</b> ${LabApp.escapeHtml(answer)}</div>` : ""}`;
    el.appendChild(div);
  }

  function waitForAnswer() {
    const row = document.getElementById("p03-answer-row");
    const input = document.getElementById("p03-answer-input");
    row.style.display = "block";
    input.value = "";
    input.focus();
    return new Promise((resolve) => { pendingAnswerResolve = resolve; });
  }

  function wireAnswerSubmit() {
    document.getElementById("p03-submit-answer").addEventListener("click", () => {
      const input = document.getElementById("p03-answer-input");
      const val = input.value.trim();
      if (!val || !pendingAnswerResolve) return;
      document.getElementById("p03-answer-row").style.display = "none";
      const resolve = pendingAnswerResolve;
      pendingAnswerResolve = null;
      resolve(val);
    });
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
    document.getElementById("p03-interview-panel").style.display = "block";
    document.getElementById("p03-transcript").innerHTML = "";
    wireAnswerSubmit();
    LabApp.setStatus(pipelineId, "진행 중...", "running");
    try {
      await ensureClassifiers((msg) => LabApp.log(pipelineId, msg));
      const category = findingCategory(selectedFinding.id);
      const transcript = [];
      let verdict = "exhausted_at_cap";
      const maxTurns = LabApp.resolveParam("p03", "p03-6", "max_turns") || 4;

      for (let i = 0; i < Math.min(LEVELS.length, maxTurns); i++) {
        const level = LEVELS[i];
        const prevClassification = transcript.length ? transcript[transcript.length - 1].classification : null;
        LabApp.log(pipelineId, `${level.toUpperCase()} 질문 생성 중...`);
        const question = await generateQuestion(level, selectedFinding, null, transcript, prevClassification);
        appendTranscriptEntry(level, question, null, null);
        LabApp.log(pipelineId, "답변 대기 중...");
        const answer = await waitForAnswer();
        LabApp.log(pipelineId, "답변 분류 중 (결정론적 분류기, LLM 아님)...");
        const classification = await classifyAnswer(category, answer, level);
        transcript.push({ level, question, answer, classification });
        appendTranscriptEntry(level, question, answer, classification.verdict);
        if (classification.verdict === "defended") { verdict = "defended"; break; }
      }

      LabApp.log(pipelineId, "5축 채점 중...");
      const last = transcript[transcript.length - 1];
      const { grades, rubric_overridden } = await gradeAnswer(selectedFinding, last.question, last.answer);

      LabApp.setStatus(pipelineId, "완료", "done");
      const result = { finding: selectedFinding, verdict, turns: transcript.length, transcript, grades, rubric_overridden };
      renderResults(result);
      await maybeSaveRun(result);
    } catch (err) {
      console.error(err);
      LabApp.setStatus(pipelineId, `오류: ${err.message}`, "error");
      LabApp.log(pipelineId, `오류: ${err.message}`);
    }
  }

  function renderResults(result) {
    let html = `<p>verdict: <b>${LabApp.escapeHtml(result.verdict)}</b> · ${result.turns}턴${result.rubric_overridden ? ' · <span style="color:var(--before);">rubric_overridden</span>' : ""}</p>`;
    html += `<div class="param-grid">`;
    for (const [axis, g] of Object.entries(result.grades)) {
      html += `<div class="finding-card"><div class="fid">${LabApp.escapeHtml(axis)}: ${LabApp.escapeHtml(String(g.score))}점</div><div>${LabApp.escapeHtml(g.evidence || "")}</div></div>`;
    }
    html += `</div>`;
    html += `<p class="field-label" style="margin-top:14px;">원본 JSON</p><pre>${LabApp.escapeHtml(JSON.stringify(result, null, 2)).slice(0, 20000)}</pre>`;
    LabApp.showResults(html);
  }

  async function maybeSaveRun(result) {
    if (!window.LabDB || !LabDB.isConfigured()) {
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
      });
      LabApp.log("p03", "결과가 팀 DB에 저장됨");
    } catch (err) {
      LabApp.log("p03", `DB 저장 실패(결과는 화면에 남아있음): ${err.message}`);
    }
  }

  return { renderInput, run };
})();

document.addEventListener("DOMContentLoaded", () => {
  if (window.LabApp) LabApp.registerRunner("p03", P03Runner);
});
