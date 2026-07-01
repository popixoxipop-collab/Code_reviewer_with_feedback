# POC 테스트 — 인지·판단·피드백 3블록 파이프라인

## 이 시스템은 A안/B안 중 어디에 해당하는가

팀에서 이미 정리한 A안(Viva 인터뷰, LLM 롤플레잉)/B안(연구용, Evidence 중심) 구분에 그대로 대입하면,
이 저장소(`Code_reviewer_with_feedback`)에서 만든 것은 **B안 그 자체**다.

| 항목 | A안 (Viva 인터뷰 POC) | B안 — 이 저장소 |
| --- | --- | --- |
| 목적 | 학생 평가 | 이해 신호 분석 |
| 결과 | 100점 + 피드백 | 상/중/하 + 신호 로그(JSON) |
| 철학 | Rubric 중심 | Evidence 중심(fan_in, matched_text, pattern_key) |
| 출력 | 사람이 읽는 평가 보고서 | 연구용 JSON(`judgment_output.json`, `ledger.jsonl`) |
| 평가 방식 | LLM이 종합적으로 판단 | 규칙 기반 + 재귀 hook 재검증 |
| 설명 가능성 | 보통 | 매우 높음(모든 판정에 근거 필드 존재) |
| 재현성 | 상대적으로 낮음(대화형이라 매번 다름) | 높음(같은 repo → 같은 결과, 커밋으로 버전관리) |

```
        GitHub Repository
               │
               ▼
    Cognition (Tier A/B 스캔)
               │
               ▼
    Judgment (규칙 채점 + 재귀 hook)
               │
       ┌───────┴───────┐
       ▼               ▼
  idiom_hook       tier_b_hook
  (관용패턴 억제)   (오탐 억제)
       │               │
       └───────┬───────┘
               ▼
     ledger.jsonl (누적 원장)
               │
               ▼
   compare_methodologies.py (즉시 조회)
               │
               ▼
      Feedback (Depth Ladder 7단계, LLM 미검증)
```

---

## 방법: 입력한 명령/설정 전문

A안이 "프롬프트 전문"을 롤플레잉 스킬로 등록했듯, 이 시스템은 재현 가능한 스크립트+설정 파일이 그 역할을 한다.

```bash
# 인지 → 판단 실행
python3 cognition/two_tier_scan.py <repo>/src > scan.json
python3 judgment/score_findings.py scan.json <repo>/src

# 재귀 hook 순차 주입 + 즉시 비교표
python3 pipeline/run_pipeline.py <repo>/src <injections.json> result.md

# 지금까지 축적된 모든 방법론 비교표 조회
python3 pipeline/compare_methodologies.py
```

`injections.json`은 A안의 "질문 선정 우선순위"에 대응한다 — 사람이 실제 코드를 읽고
"이건 관용패턴/오탐이다"라고 판단한 근거(`note`)를 강제로 채워야만 주입이 성립한다(D22).

---

## 실행 로그 — 실제 공개 repo 4개

### Repo 1: Study-Match- (React+Firebase, 10파일)
```
[baseline] 4건
cognition-isolation:Competitions.tsx      | 상 | 최우선
architecture-diffusion:App.tsx            | 상 → 하 (idiom_hook 주입 후)
tier-b-risk:firebase.ts                   | 중 | Important(🔴)
repeated-pattern:onSnapshot                | 상 | 질문 대상
```
발견: fan-in 이중계산 버그(7→8), `sk-` secret 오탐(URL 문자열 부분일치) — 둘 다 코드로 직접 수정.

### Repo 2: RunPod_Deploy_Agent (Python+JS 혼합, 10파일)
```
flagged_files (수정 전): {'large-model-loader-guard.py': ['eval_or_dangerous_html'], ...}
flagged_files (수정 후): {}
```
발견: `model.eval()`(PyTorch 표준 API)이 위험한 전역 `eval()`로 오탐 → 정규식에 부정 후방탐색 추가.

### Repo 3: jxxnixx/LMS (JS/TS, 51파일, `@/` 별칭 다수 사용)
```
[baseline] 32건 → 8건 (버그 수정 후)
architecture-diffusion:useBooksQueries.ts | 상 → 하 (idiom_hook: react-query-custom-hook 주입)
tier-b-risk:Bookshelf.jsx:dangerous-html  | 중 | Important (진짜 XSS 위험, 주입 안 함)
cognition-isolation:* (6건)                | 상 | 여전히 노이즈 있음(미해결)
```
발견 3건: `@/` alias import 99건 누락, 고립판정 오탐 폭발(51개 중 30개), `dangerouslySetInnerHTML`
finding화 규칙 누락 — 전부 코드로 직접 수정.

### Repo 4: Shadowbroker (Python+TS monorepo, 726파일)
```
tier-b-risk:test_api_settings.py:secret   | 하 → (제거됨) (tier_b_hook: 테스트 픽스처 오탐 주입)
cognition-isolation:* (90건 이상)          | 상 | 대형 monorepo에서 다시 노이즈 폭발(다중 진입점 미대응)
```
발견: `auth_info_leak_via_thrown_error`가 근접성 검사 없이 대형 파일(1500줄+)에서 오탐 —
매치 텍스트가 너무 일반적("email")이라 hook 억제 대신 미수정으로 기록(D26).

---

## 종합 보고서

**축적 원장 기준 방법론 비교표** (재실행 없이 `compare_methodologies.py`로 즉시 조회):

| 방법론 | 키 | 적용 repo 수 | 총 주입 횟수 | 변경된 finding 누적 | 최근 예시 |
|---|---|---|---|---|---|
| idiom | `react-context-global-state` | 1 | 2 | 1 | `Study-Match-`: 상→하 |
| idiom | `react-query-custom-hook` | 1 | 2 | 1 | `LMS`: 상→하 |
| tier_b | `hardcoded_secret_pattern` | 1 | 1 | 1 | `Shadowbroker`: 하→(제거됨) |

**발견→수정 사이클 누적**: D12~D26, 총 15개 결정. 그중 9개는 실제 버그를 실측으로 발견해 코드로
직접 고친 것(fan-in 이중계산, secret/eval 오탐 2건, `.h` 언어판별, hub tie-break, alias 누락,
고립판정 범위, eval_or_dangerous_html 누락규칙, react-query 패턴), 나머지는 아키텍처 재배치(D14)와
설계 결정(D5~D7, D22~D25)이다.

---

## 프롬프트/실행에 대한 자체 평가

### 전체 평가

기대했던 흐름은
```
Repo 스캔 → 판정 → 사람이 오탐/관용패턴 확인 → hook 주입 → 재판정 → 축적 → 비교
```
이었는데, 4개 repo를 돌려본 결과 거의 이 흐름을 그대로 따라갔다. **POC는 성공했다고 본다.**

### 좋은 점

**① 재귀 hook의 폐루프가 실제로 닫히는 걸 실측으로 증명했다.**
idiom_hook(관용패턴)과 tier_b_hook(오탐 억제) 둘 다 "피드백 3회 누적 → confirmed 승격 → 재판정
시 자동 반영"까지 4개 repo에 걸쳐 재현됐다. 한 번 학습하면 다른 repo에도 전이된다는 것도
확인됐다(같은 javascript 언어 저장소를 Study-Match-와 LMS가 공유).

**② 발견→수정 사이클이 이론이 아니라 실측 기반이었다.**
새 repo를 돌릴 때마다 예외 없이 새 버그가 나왔고(D12, D17, D18, D19, D20, D26), 전부 "왜 이게
문제인지"를 코드 주석(WHY/COST/EXIT)으로 남기고 재검증한 뒤에만 다음으로 넘어갔다.

**③ 오케스트레이터가 진짜 위험까지 오탐으로 뭉개지 않았다.**
LMS의 `dangerouslySetInnerHTML`(네이버 API 응답을 그대로 렌더링, 진짜 XSS 위험)을 자동으로
억제하지 않고 그대로 노출시킨 것 — A안 문서의 "Leading Question" 문제와 정반대로, 오히려
"판단을 유보해야 할 때 유보하는" 방향으로 설계됐다.

### 하지만 문제도 있다

**문제 1 — 아직 사람이 다 판단해줘야 한다(A안의 "Leading Question"과 반대 극단).**
`injections.json`을 사람이 실제 코드를 읽고 채워야만 hook이 작동한다(D22). 이건 오탐을
안전하게 막지만, 완전 자동화된 폐루프는 아니다 — Ownership 검증 시스템이 자기 자신도
완전히 자동화하지 못한 채로 있다.

**문제 2 — 구조 신호가 아직 "왜 이 아키텍처인가" 수준까지 못 간다.**
`cognition-isolation`, `architecture-diffusion` 같은 finding은 파일 단위 구조 신호이지,
A안 문서가 지적한 "Redux는 왜 고려 안 했나", "MSA로 바꾸려면 어디부터?" 같은 진짜
아키텍처 수준 질문으로는 아직 못 올라간다.

**문제 3 — 판정 근거가 여전히 얇다.**
`design_intent`/`question_value`/`risk` 3축이 규칙 기반 한 줄 판정이다. `judgment/SUBRUBRIC_DRAFT.md`
(다른 세션에서 병행 작업 중)가 이 갭을 메우려는 초안이지만 아직 코드로 구현되지 않았다.

**문제 4 — Evidence Chain이 약하다.**
finding→matched_text/fan_in까지는 연결되지만, "왜 이 판정이 나왔는가"를 사람이 읽는
문장으로 체인화하는 건 `idiom_note` 한 줄이 전부다. A안이 지적한 것과 같은 종류의 갭이다.

**문제 5 — 피드백(학습 방향 제시)이 가장 약한 고리다.**
`feedback/generate_questions.py`는 코드까지는 완성됐지만, 실제 Anthropic API 호출로 생성
품질을 검증한 적이 없다(API 키 없음, README에 명시). Depth Ladder 7단계 템플릿은 있지만
그게 실제로 이해도를 구분해내는지는 사람이 답한 적이 한 번도 없어서 전혀 모른다.

**문제 6 (가장 중요) — 아직 "Repository Knowledge"를 검증하지, "Repository Ownership"을
검증하지 못한다.**
A안 문서의 지적과 정확히 같은 문제다. 우리 시스템은 "이 파일이 고립됐다", "이 패턴이
관용적이다" 같은 **사실**은 잘 뽑지만, "이 구조를 처음부터 다시 만든다면 뭘 바꾸겠는가",
"3개월 뒤 버그가 가장 많이 날 곳은 어디인가" 같은 **자기 언어로 설계를 방어하는 능력**은
전혀 측정하지 못한다. Feedback 블록이 실제 LLM 대화로 자동화되기 전까지는 이 시스템도
Knowledge 검증기에 머문다.

### 전체 평가 (별점)

```
인지 (구조/위험 신호 추출)     ★★★★☆
판단 (규칙 기반 채점)          ★★★☆☆
재귀 학습 (hook 폐루프)        ★★★★★
Evidence 연결                  ★★★☆☆
피드백 자동화                   ★★☆☆☆
Ownership 측정                 ★★☆☆☆
```

### 오히려 놀랐던 점

새 repo를 돌릴 때마다 "이미 다 됐다"고 생각했던 부분에서 매번 새 버그가 나왔다는 것 —
Study-Match-에서 통했던 hub 판정 로직이 RunPod에서는 희소 그래프 문제로, LMS에서는
오탐 폭발로, Shadowbroker에서는 다중 진입점 monorepo 문제로 매번 다른 방식으로 깨졌다.
**"한 번 검증됐다"는 것이 "일반화됐다"는 뜻이 아니라는 걸 4번 연속으로 실측했다** — 이게
이 POC에서 가장 값진 결과다. 판단 블록(idiom/tier_b hook)만은 4개 repo 전부에서 설계
의도대로 작동해 유일하게 "일반화 검증 완료"라고 말할 수 있는 블록이다.
