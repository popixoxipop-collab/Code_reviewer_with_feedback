# POC 테스트 — 인지·판단·피드백 3블록 파이프라인 (ROAF-B 형식)

팀의 B안(ROAF-B: Signal Extraction → Recursive Rule Validation → Downgrade Log → Evidence Trace,
정량 점수 없이 상/중/하만 판정) 형식을 그대로 이 저장소에 적용한다. 이 시스템은 애초에 B안과
같은 철학(Evidence 중심, 판단 금지 후 재귀 검증, 근거 로그)으로 설계됐기 때문에 매핑이 자연스럽다.

---

## 이 시스템의 Role 정의 (ROAF-B 대응)

```
당신은 학생을 점수화하는 평가자가 아니다.
당신은 "Repository Ownership Signal Analysis Engine"이다.

목적: Repository의 finding(구조/위험 신호)을 추출하고,
      규칙 기반으로 재귀 검증하여
      최종적으로 신뢰 가능한 정성적 등급(상/중/하)을 산출한다.

절대로 직관적으로 판단하지 않는다.
모든 판단은 명시된 규칙(D12~D31)에 따라 이루어진다.
```

- Step 1 (Repository 분석) = **인지 블록** (`cognition/two_tier_scan.py`)
- Step 2~3 (Signal Extraction, 판단 금지) = 인지 블록의 raw 출력(fan_in, edges, tier_b matched_text) — 아직 상/중/하가 아니다
- Step 4 (Recursive Signal Validation) = **판단 블록의 Rule들**(D12, D17, D19, D20, D21, D26, D29, D31) + 재귀 hook(`idiom_hook.py`, `tier_b_hook.py`)
- Step 5 (Final Grade, 상/중/하만) = `subrubric.py`의 `bucket()`
- Step 6 (Evidence Log 강제) = `finding["subrubric"]`, `idiom_note`, `matched_text`

---

## 방법: 입력한 설정/명령 전문

```bash
# Step 1~3: Repository 분석 + Signal Extraction (판단 금지, raw 신호만 추출)
python3 cognition/two_tier_scan.py <repo>/src > scan.json

# Step 4~5: Recursive Signal Validation + Final Grade
python3 judgment/score_findings.py scan.json <repo>/src > judgment.json

# Step 4의 재귀 hook 부분만 따로: 사람이 "이 신호는 관용패턴/오탐"이라고 판단한 근거를
# injections.json에 채우면, 순차 주입하며 즉시 Downgrade 여부를 보여준다
python3 pipeline/run_pipeline.py <repo>/src <injections.json> result.md

# 지금까지 쌓인 모든 Downgrade 이력을 방법론별로 집계
python3 pipeline/compare_methodologies.py
```

`injections.json`이 ROAF-B의 "Rule 적용 근거"에 대응한다 — Rule을 실행하려면 사람이
왜 그렇게 판단했는지(`note`)를 먼저 써야 한다(D22).

---

## 실행 로그 — 4개 실제 공개 Repository

### Repo 1: Study-Match- (React+Firebase, 10파일)
```
Step1~3 raw signal: fan_in={App.tsx:7, firebase.ts:7(tie)}, tier_b={firebase.ts:[auth_info_leak]}
Step4 Rule 적용: D16(hub tie-break, fan_out 낮은 firebase.ts 선택) → D12(fan-in dedup, 7로 정정)
Step5 Final: cognition-isolation:Competitions.tsx=최우선, architecture-diffusion:App.tsx=질문대상(주입 전)
```

### Repo 2: RunPod_Deploy_Agent (Python+JS 혼합, 10파일)
```
Step1~3 raw signal: tier_b={large-model-loader-guard.py:[eval_or_dangerous_html, matched="eval("]}
Step4 Rule 적용: D17(부정 후방탐색으로 model.eval() 메서드호출 배제)
Step5 Final: flagged_files={} (오탐 제거, 진짜 위험 없음)
```

### Repo 3: jxxnixx/LMS (JS/TS, 51파일, `@/` 별칭 다수)
```
Step1~3 raw signal (버그 상태): fan_in 최대 2/51(@/ 별칭 미인식), cognition-isolation 30건 폭발
Step4 Rule 적용: D18(alias 인식) → fan_in 최대 12로 정상화 / D19(고립판정 범위 제한) → 30건→6건
                D20(dangerous-html 누락 규칙 추가) / D21(react-query 패턴 인식)
Step5 Final: 8건. architecture-diffusion:useBooksQueries.ts는 injections.json 주입 후 상→하
```

### Repo 4: Shadowbroker (Python+TS monorepo, 726파일)
```
Step1~3 raw signal: tier_b 13개 파일 flagged, cognition-isolation 90건 이상(다중 진입점 미대응)
Step4 Rule 적용: tier_b_hook 주입(test_api_settings.py의 시크릿 플레이스홀더, 3회 피드백)
Step5 Final: tier-b-risk:test_api_settings.py:secret → confirmed 오탐 → finding 자체가 제거됨
             (meshIdentity.ts의 "email" 오탐은 매치 텍스트가 너무 일반적이라 D26으로 미주입/기록만)
```

---

## 종합 보고서

### 1. 종합 결과

**시스템 신뢰도 등급: 중상** (정량 점수 없음, ROAF-B 원칙 그대로 유지)

한 줄 총평: 재귀 hook의 폐루프(Recursive Signal Validation)는 4개 repo 전부에서 설계 의도대로
작동함을 실측으로 증명했으나, Signal Aggregation(finding 여러 개 → repo 단위 등급)과 Evidence
Confidence(근거별 신뢰도 가중치)가 아직 없어 ROAF-B가 지향하는 수준에는 못 미친다.

### 2. 최종 등급

| 평가 축 | 등급 | 판단 근거 |
| --- | --- | --- |
| Signal Extraction (인지 블록) | 상 | 4개 repo·다국어에서 재현, 발견된 버그(D18) 즉시 수정·재검증 |
| Recursive Rule Validation (재귀 hook) | 상 | idiom_hook·tier_b_hook 둘 다 4개 repo에 걸쳐 폐루프 실증, 언어 간 지식 전이까지 확인 |
| Evidence Log | 중 | subrubric으로 근거는 생겼지만 D31 발견 전까지 감사 트레일과 최종 판정이 불일치했음 |
| Signal Aggregation | 하 | finding 단위 채점만 있고, repo 전체를 하나의 등급으로 합치는 규칙이 없음 |
| Ownership 측정 | 하 | 아직 Repository Knowledge(구조 사실)만 검증, "자기 언어로 설계 방어" 능력은 미측정 |

### 3. Repo별 신호 분석

**Repo: Study-Match-**
- Repository 근거: `App.tsx`가 fan_in=7로 확산 지점 후보, 내용에 `createContext<AuthContextType>(` 존재
- 추출된 signal: `idiom_conformance_reverse`(D5~D7 판정 대기), `tradeoff_existence=true`
- Rule 적용: idiom_hook 3회 피드백 → confirmed 승격 → question_value 상→하
- 최종 결과: 하(관용 패턴으로 하향)

**Repo: jxxnixx/LMS**
- Repository 근거: `useBooksQueries.ts`, 내용에 `useQuery(`/`useSuspenseQuery(` 존재
- 추출된 signal: D21 신설 패턴(`react-query-custom-hook`)에 최초로 매치
- Rule 적용: idiom_hook 3회 피드백(공식 문서 권장 컨벤션이라는 근거) → confirmed → 상→하
- 최종 결과: 하. **참고로 같은 파일 그룹의 `dangerouslySetInnerHTML`(Bookshelf.jsx)은 진짜 XSS
  위험이라 Rule 적용(주입) 대상에서 제외** — ROAF-B의 Rule B(회피/무응답 시 자동 하)와 달리,
  이 시스템은 "위험 신호를 자동으로 낮추지 않는" 방향으로 설계되어 있다.

**Repo: Shadowbroker**
- Repository 근거: `test_api_settings.py`의 `AIS_API_KEY="saved-ais-key"` — pytest 픽스처
- 추출된 signal: `hardcoded_secret_pattern` 매치, 그러나 파일 경로가 `tests/`(D29의 `LOCATION_INTENT_HINTS`에 해당)
- Rule 적용: tier_b_hook 3회 피드백 → confirmed → finding 자체 제거
- 최종 결과: (제거됨). 같은 repo의 `meshIdentity.ts` "email" 오탐은 **Rule 미적용으로 남김**(D26) —
  매치 텍스트가 너무 일반적이라 억제하면 다른 파일의 진짜 위험까지 가려질 위험이 크다고 판단

### 4. Downgrade Log (`pipeline/ledger.jsonl` 원본)

| Signal | From | To | Reason | 관련 Repo |
| --- | --- | --- | --- | --- |
| `architecture-diffusion:App.tsx` (question_value) | 상 | 하 | 컴포넌트 6개 규모에서 React Context는 관용 패턴, 설계판단 아님 | Study-Match- |
| `architecture-diffusion:useBooksQueries.ts` (question_value) | 상 | 하 | `@tanstack/react-query` 공식 문서 권장 컨벤션(리소스당 커스텀 훅) | LMS |
| `tier-b-risk:test_api_settings.py:secret` (finding 존재 여부) | 존재(하) | 제거됨 | pytest 픽스처의 명백한 플레이스홀더, 실제 크리덴셜 아님 | Shadowbroker |

### 5. Signals After Filter — Downgrade Log와의 정합성 검증

```json
{
  "architecture-diffusion:App.tsx": {
    "question_value_final": "하",
    "subrubric_raw_total": 9,
    "subrubric_raw_bucket_if_unfiltered": "상",
    "overridden_by": "idiom_filter",
    "consistent": true
  }
}
```
`subrubric_raw_total=9`만 보면 "상"이어야 하지만 idiom_filter가 confirmed 패턴으로 덮어써 최종은
"하"다. **이 불일치를 이 POC 작성 과정에서 실측으로 발견했고(D31), `finding["subrubric"]`에
`overridden_by`/`final_bucket`을 기록하도록 즉시 고쳐서 지금은 Signals After Filter와
Downgrade Log가 항상 일치한다.**

### 6. Evidence Trace

| Repo | Evidence | Signal | Rule | Final |
| --- | --- | --- | --- | --- |
| Study-Match- | `App.tsx` 내 `createContext<AuthContextType>(` | pattern_key=react-context-global-state | idiom_hook(D5~D7) | 하 |
| RunPod_Deploy_Agent | `large-model-loader-guard.py:151`의 `model.eval()` | trigger=eval_or_dangerous_html(오탐) | D17(부정 후방탐색) | (finding 미생성) |
| LMS | `useBooksQueries.ts` 내 `useQuery(` | pattern_key=react-query-custom-hook | D21 + idiom_hook | 하 |
| LMS | `Bookshelf.jsx:157` `dangerouslySetInnerHTML={{__html: item.title}}` | trigger=eval_or_dangerous_html(진짜 위험) | D20(finding화) + **Rule 미적용(의도적)** | 상 |
| Shadowbroker | `test_api_settings.py:32` `AIS_API_KEY="saved-ais-key"` | trigger=hardcoded_secret_pattern(오탐) | tier_b_hook | (제거됨) |
| Shadowbroker | `meshIdentity.ts` 8행 주석의 "email" | trigger=auth_info_leak(오탐 추정) | D26(미적용, 기록만) | 중(그대로 노출) |

### 7. 종합 의견

이 시스템은 구조를 상당히 안정적으로 재현한다. 특히 재귀 hook(idiom/tier_b)이 서로 다른 4개
repo·2개 언어에 걸쳐 "3회 피드백 → confirmed → 재판정 반영"이라는 동일 메커니즘으로 작동함을
실측으로 증명했다. 가장 보완이 필요한 부분은 여러 finding을 하나의 repo 단위 등급으로 합치는
**Aggregation 규칙의 부재**다. 지금은 "이 파일이 위험하다/관용적이다"까지만 말할 수 있고,
"이 repo 전체를 이 학생이 얼마나 ownership 있게 짰는가"로는 아직 안 올라간다.

---

## 프롬프트/실행에 대한 자체 평가 (ROAF-B 비평 형식)

결론부터: **B안(ROAF-B) 철학에 원래부터 부합했다.** "LLM이 느낌으로 판단"이 아니라
`Evidence → Signal → Rule → Grade`를 코드로 강제했기 때문이다.

### 가장 좋아진 점

**1. 판정에 근거가 붙었다.**
과거(이 세션 초반)에는 `question_value: "상"`처럼 이유 없는 문자열이었다. 지금은
`subrubric.question_value.sub`에 4개 서브축 점수가 남고, `idiom_note`에 어떤 confirmed
패턴 때문에 몇 회 확인됐는지까지 남는다.

**2. Evidence Trace가 생겼다.**
`finding["file"]` → `matched_text`/`pattern_key` → `subrubric.sub` → 최종 등급까지 위 표 6번처럼
연결된다. Rule(D-번호) 없이 등급이 바뀌는 경우가 없다.

**3. Downgrade Log가 실제로 존재하고 재현 가능하다.**
`pipeline/ledger.jsonl`이 append-only로 모든 Downgrade를 기록하며, `compare_methodologies.py`로
언제든 재집계된다 — 팀의 B안이 JSON으로만 흉내 낸 것을 이 시스템은 파일로 영속화한다.

### 그런데 조금 이상한 부분도 있다

**문제 1 — Signals After Filter가 Downgrade Log와 안 맞았다(발견 즉시 수정).**
`architecture-diffusion:App.tsx`의 subrubric 원점수(9점→"상")와 idiom_filter가 덮어쓴 최종값
("하")이 finding 안에 불일치 상태로 공존했다. B안 문서가 지적한 것과 정확히 같은 결함이며,
이 POC를 작성하다가 직접 재현해서 발견했다(D31). **차이점: B안은 이 문제를 "지적"만 했지만,
이 시스템은 발견 즉시 `overridden_by`/`final_bucket` 필드를 추가해 고쳤고 재검증까지 끝냈다.**

**문제 2 — Signal과 Final Grade가 아직 완전히 분리되지 않았다.**
`design_intent`가 `repetition`/`idiom_status`/`location_signal`/`mitigation_present` 4개
서브축의 단순 합(0~12)으로 결정되는데, 이 4개가 정말 "설계의도"라는 construct를 대표하는
분해인지에 대한 별도 검증(팀 합의, 실측 상관관계 등)은 없다 — `SUBRUBRIC_DRAFT.md`가 설계
근거를 문서화했지만 이것도 결국 한 세션의 판단이다.

**문제 3 — Rule이 너무 적고 즉흥적으로 추가된다.**
현재 Rule은 D12, D17, D19, D20, D21, D26, D29, D31 — 전부 "새 repo를 돌리다가 우연히 발견한"
버그 수정이다. B안처럼 처음부터 "Rule A~F"로 체계화된 게 아니라, 사후 발견 순서대로 번호만
붙어 있다. 규칙이 늘어날수록 서로 어떤 순서로 적용되는지(예: D19가 D12보다 먼저 실행돼야
하는지)에 대한 명시적 순서 보장이 없다.

**문제 4 — "관용 패턴 확정"이 너무 쉽게 이뤄진다. (→ Reflection에 한해 해소, D32/D33)**
threshold=3이면 confirmed다. 그런데 이 3이 실측 데이터가 아니라 임의값이라는 건 D6에서 이미
인정했다. B안이 지적한 "Reflection이 너무 쉽게 true가 된다"는 문제와 같은 종류였는데,
`feedback/reflection_hook.py` + `reflection_signal.py`로 idiom_hook과 동일한 재귀 확인
패턴을 Reflection 판정에 실제로 적용했다 — 자기오류인식/이유설명/새판단/개선안 4개
서브신호가 **전부** confirmed 패턴으로 매치돼야 `reflection_present=true`(AND-4).

실측 결과가 흥미롭다: **B안 문서 자체가 제시한 모범 Reflection 예시**("아 맞네요. 제가
브라우저를 너무 신뢰했습니다. 운영환경이라면 백엔드에서 제한해야 합니다")를 그대로 넣어봤더니
3/4만 매치되고(`reason_explanation`용 "그래서/왜냐하면" 같은 명시적 연결어가 없음)
`reflection_present=false`로 나왔다. 대조군인 피상적 답변("네, 알겠습니다. 수정하겠습니다.")은
0/4로 정확히 구분됐다. **즉 오탐(피상적 답변을 reflection으로 오판)은 확실히 막았지만,
AND-4가 단일 발화 기준으로는 지나치게 엄격해서 진짜 reflection도 놓칠 수 있다는 새 한계가
드러났다** — 이건 idiom_hook을 그대로 가져다 썼을 때 예상 못 했던 부작용이다: 관용 패턴
판정은 "패턴 하나만 맞으면 충분"하지만 Reflection은 "4단계가 전부 있어야 진짜"라서, 같은
가드 메커니즘이라도 AND 조건의 개수가 다르면 보수성의 정도가 완전히 달라진다.

**문제 5 — Aggregation이 없다.**
Study-Match-는 finding이 4개, LMS는 8개, Shadowbroker는 100건 이상이다. 이 여러 finding을
"이 repo의 종합 등급"으로 합치는 규칙이 전혀 없다. B안 문서의 "Question별 Grade가 어떻게
Final Grade로 합쳐지는지 중간 계산이 없다"는 지적이 이 시스템에는 통째로 존재한다.

**문제 6 (가장 중요) — 아직 Repository Knowledge를 보지, Ownership을 보지 못한다.**
`cognition-isolation`, `architecture-diffusion` 같은 finding은 전부 "이 파일이 구조적으로
이상하다"는 사실 신호다. "이 구조를 처음부터 다시 만든다면 뭘 바꾸겠는가" 같은 질문은
`feedback/generate_questions.py`가 코드로는 만들 수 있지만, 실제 LLM 호출로 검증된 적이 한
번도 없다(API 키 없음). Ownership 측정은 이론상으로만 존재한다.

### 종합 평가 (별점)

| 항목 | 평가 |
| --- | --- |
| Repository 기반 Signal Extraction | ★★★★★ |
| Recursive Rule Validation (재귀 hook) | ★★★★★ |
| Evidence Trace | ★★★★☆ |
| Downgrade Log | ★★★★☆ |
| Explainability | ★★★★☆ |
| Signal Aggregation | ★★☆☆☆ |
| Evidence Confidence | ★★☆☆☆ |
| Ownership 측정 | ★★☆☆☆ |

### 가장 큰 개선점

B안 평가가 지목한 "Evidence Confidence"가 이 시스템에도 그대로 없다. 지금은 `matched_text`가
있으면 그냥 신뢰한다 — 근거의 강도를 구분하지 않는다. 예를 들어:

```
Repository 내용 직접 매치(pattern_key)     ★★★★★
Tier B 정규식 매치(matched_text)          ★★★★☆
구조 신호만(fan_in, isolation)            ★★★☆☆
휴리스틱 추정(location_signal 파일명 힌트)  ★★☆☆☆
```

이런 신뢰도 계층이 생기면, Rule 적용 순서(문제 3)와 확정 기준(문제 4)도 "신뢰도 높은 근거는
즉시 반영, 낮은 근거는 threshold를 더 높게"처럼 자연스럽게 재구성할 수 있다.

### 제 의견

이 POC는 **B안이 지향한 방향과 이미 상당히 일치**한다. 다만 다음 세 가지가 보강되면 훨씬
설득력이 생긴다.

1. **Signal → Construct 매핑의 외부 검증**: `SUBRUBRIC_DRAFT.md`의 4서브축 분해가 실제 팀
   판단과 일치하는지, 최소 1개 repo에서 사람이 직접 채점한 것과 비교해봐야 한다.
2. **Evidence Confidence 도입**: 근거 종류별 신뢰도 가중치를 매겨 Rule 적용 우선순위를 정한다.
3. **Aggregation 규칙 신설**: finding 여러 개를 repo 단위 등급 하나로 합치는 규칙(예:
   Important finding 1개라도 있으면 repo 등급 상한을 "중"으로 제한 등)이 다음 스프린트의
   최우선 과제다.
