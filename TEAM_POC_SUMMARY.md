# 노경천 — Code Ownership 검증 파이프라인 (GitHub: Code_reviewer_with_feedback)

> 팀원별 POC 테스트 요약(김만서/박진용/손진원/박종호)과 같은 형식. 다른 3명이 "대화형
> LLM 인터뷰 프롬프트"를 비교했다면, 이쪽은 **"대화 없이 코드만으로 얼마나 갈 수 있고,
> 어디서부터 대화가 반드시 필요한가"**를 실제 5개 방법론(A~E안)으로 검증했다.

## 입력 레포 및 검증 대상 결정 포인트 (실제 스캔 결과, jxxnixx/LMS)

> **입력 레포:** `https://github.com/jxxnixx/LMS` (회귀 검증용 3개 추가: Study-Match-,
> RunPod_Deploy_Agent, Shadowbroker)
>
> **검증 대상 결정 포인트 (Tier A/B 구조+위험 스캔, 총 8건):**
> - `cognition-isolation` × 6 — Auth.jsx / BookDetail.jsx / BookList.jsx / Header.jsx / LibraryScene.jsx / authToken.js (허브 모듈 GenreContext.jsx 미사용)
> - `architecture-diffusion` × 1 — useBooksQueries.ts (여러 컴포넌트가 공유하는 react-query 커스텀 훅)
> - `tier-b-risk` × 1 — Bookshelf.jsx `dangerouslySetInnerHTML` (네이버 도서 API 응답을 그대로 렌더링)

---

## 18축 루브릭 비교표 (김만서 원본 표에 C/D/E안 열 추가)

김만서 문서의 "심플 프롬프트 vs A안과 B안의 차이" 표(18개 평가 요소, 원본 그대로 대조
확인)에서 A안·B안 값은 원문 그대로 가져오고, C/D/E안 값만 이번 세션 실측으로 채웠다.

| 평가 요소 | A안 (Viva 100점) | B안 (ROAF-B) | C안 (이 repo) | D안 (evidence_bridge) | E안 (Reflection Hook) |
| --- | --- | --- | --- | --- | --- |
| **목적** | 이해도를 정량적으로 평가 | 이해 과정을 정성적으로 진단 | 코드만으로 구조/위험 신호를 저비용 추출 | C안 신호를 B안 형식 Evidence로 자동 변환 | 답변의 자기오류인식 여부를 재귀 검증 |
| **Repository 분석** | ○ | ○ | ○(정적분석) | ○(C안 재사용) | ✗(답변 텍스트만 봄) |
| **질문 생성** | Depth Ladder 기반 | Depth Ladder 기반 | 없음(대화 자체 없음) | 고정 템플릿 4종(오프닝) | 없음 |
| **Follow-up 질문** | 답변 기반 적응형 | 적응형+Signal 기반 재귀 질문 | 해당없음 | **적응형(규칙 기반) — `pipeline/followup_generator.py`, 팀 §3 전략표를 isolation_classifier/reflection_signal로 그대로 구현, 4개 실제 사례로 검증** | 해당없음 |
| **질문 깊이** | 높음 | 높음 | 해당없음 | 2단계(오프닝→적응형 후속), 실제 Codex 2턴 대화로 검증 | 해당없음 |
| **코드 구조 검증** | ○ | ○ | ◎(fan-in/fan-out 실측, 버그 3개 발견) | ○(C안 재사용) | ✗ |
| **설계 의도 검증** | ○ | ○ | △(subrubric 규칙식) | △(C안 재사용+문구화) | ✗ |
| **Trade-off 검증** | ○ | ○ | △(tradeoff_signal 서브축) | △(C안 재사용) | ✗ |
| **Counterfactual 질문** | ○ | ○ | 없음 | 없음 | 없음 |
| **Reflection 유도** | ○ | Reflection Signal로 검증 | 없음 | 없음 | 시도함, 실측 재현율 0/7 |
| **평가 방식** | Rubric 점수(100점) | Rule 기반 Signal 분석 | 규칙식 서브루브릭(0~12→상/중/하) | C안 채점 재사용 | 정규식 패턴 매칭(재귀 확인) |
| **평가 근거** | 항목별 점수와 근거 | Signal Log+Downgrade Log+Evidence | subrubric breakdown(문헌 인용) | Repository Evidence 문단 자동생성 | matched sub-signal+pattern_id |
| **결과 예시** | "78점(Decision 17/20)" | "Alternative: 중(Rule A 강등)" | `architecture-diffusion:App.tsx \| 중 \| 하 \| 하` | "8건 중 1건 인터뷰 없이 종결" | `{reflection_present: false, matched_count: 0}` |
| **설명 가능성(Explainability)** | 중 | 매우 높음 | 매우 높음(전 축 breakdown+문헌 인용 공개) | 매우 높음(C안 그대로) | 높음(왜 안 걸렸는지 정확히 노출) |
| **재현성(일관성)** | 중 | 높음 | **매우 높음(100% 결정론적, 같은 입력→같은 출력)** | 매우 높음 | 매우 높음(규칙기반) |
| **교육 활용성** | 높음 | 매우 높음 | 낮음(교육 피드백 자체 없음) | 중(질문만 생성, 후속 피드백 없음) | 낮음(판정만, 문장 생성 없음) |
| **연구 활용성** | 높음 | 매우 높음 | 높음(버그 재현·hook 메커니즘 연구가치) | 중 | 높음(재현율 실패 사례 자체가 연구데이터) |
| **최종 산출물** | 평가 보고서(Assessment Report) | 진단 보고서(Signal Analysis Report) | `judgment_output.json` | `evidence_packets.json` | reflection 판정 JSON |

**한눈에 보이는 패턴**: C/D안은 "설명 가능성"·"재현성"에서 A/B안을 앞서지만
"질문 생성"·"Follow-up"·"교육 활용성"에서 원천적으로 밀린다 — 대화가 없기 때문에
생기는 정확히 예상된 트레이드오프다. E안은 유일하게 A/B안과 같은 축(Reflection 유도)을
시도했지만 실측 재현율이 가장 낮다.

---

## 5개 안 실행 결과 (전부 실제 실행, 사람이 지어낸 답 없음)

| 안 | 방법론 | LMS 실행 결과 |
| --- | --- | --- |
| A안 | Viva 100점 (사람이 직접 대화) | 78/100, 중상. **가장 치명적 지적: "Repository Knowledge(사실 파악)는 측정하지만 Ownership(재설계 시 뭘 바꿀지)은 측정 못함"** |
| B안 | ROAF-B Signal→Rule→Evidence Trace (사람이 직접 대화) | 등급 중상, Downgrade Log 3건. Evidence→Rule 체인으로 "왜 이 등급인가"는 설명 가능하나 Signal Aggregation·Evidence Confidence 약함 |
| C안 | 이 GitHub repo — 코드만으로 구조+위험 스캔, LLM 대화 없음 | 8 findings 100% 코드 실행, 버그 3개 실측·수정(fan-in 이중계산/eval() 오탐/Vite alias 누락), idiom 1건 확정. **API 비용 0, 대화 자체가 없어 Ownership 축은 원천적으로 측정 불가** |
| D안 | C안 finding → B안 Evidence 형식 자동변환(`evidence_bridge.py`) | 8건 중 1건(diffusion)은 코드 Rule만으로 인터뷰 없이 종결 — 사람/LLM 대화가 필요한 나머지 7건에 자동 생성 질문+Evidence 제공 |
| E안 | Reflection Hook Guard — 답변의 자기오류인식 재귀 판정 | Codex(별도 모델) 독립 생성 답변 7건 검증, **0/7 통과**. 단 원인이 갈림(아래 참조) |

## 안별 장단점 (박진용 문서 형식)

| A안 (Viva 100점) | 내용 |
| --- | --- |
| ✅ 장점 | 사람이 직접 대화해 뉘앙스·애매한 답변 포착 우수, follow-up이 자연스러움 |
| ❌ 단점 | 재현 불가(사람마다 채점 편차), **자체적으로 "Ownership은 못 본다"고 인정**, 사람 시간 비용 최고 |

| B안 (ROAF-B Signal Engine) | 내용 |
| --- | --- |
| ✅ 장점 | Evidence→Rule 체인으로 "왜 이 등급인가"를 감사 가능하게 설명, Downgrade Log가 근거로 남음 |
| ❌ 단점 | Signal Aggregation·Evidence Confidence 정량화가 약함(B안 자체 비평에서 인정), 역시 사람이 직접 대화해야 해서 비용 높음 |

| C안 (이 GitHub repo) | 내용 |
| --- | --- |
| ✅ 장점 | API 비용 0, 100% 재현 가능(같은 코드 재실행 시 동일 결과), 발견한 버그를 코드 레벨에서 즉시 수정 가능 |
| ❌ 단점 | 대화 자체가 없어 Ownership 측정이 원천적으로 불가능, 구조 신호(`cognition-isolation`)가 다중 concern 코드베이스에서 과탐지(D19/D38) |

| D안 (evidence_bridge) | 내용 |
| --- | --- |
| ✅ 장점 | 8건 중 1건은 인터뷰 없이 자동 종결(토큰 절약 실증), Evidence를 사람이 매번 재분석할 필요 없이 자동 생성 |
| ❌ 단점 | 자동 생성 질문이 finding 단위로 끊겨 있어 여러 파일을 엮은 서사형 질문보다 부자연스러움(6개 cognition-isolation finding이 전부 같은 템플릿 질문), follow-up 자동생성 로직 아직 없음 |

| E안 (Reflection Hook Guard) | 내용 |
| --- | --- |
| ✅ 장점 | 재귀 확인(threshold) 구조라 1회성 판정이 아니라 반복 확인 전엔 신뢰 안 함 — idiom_hook과 동일 원칙으로 성급한 확정을 막음 |
| ❌ 단점 | 실측 재현율 0/7 — 정규식이 정확한 문구만 잡아 자연어 표현 다양성에 취약, Codex의 훌륭한 reflection도 놓침(D37) |

---

## 실제 질문·답변 verbatim (D안 실행, `tier-b-risk:Bookshelf.jsx` 사례)

다른 팀원들처럼 실제 프롬프트와 실제 답변을 그대로 옮긴다. 아래는 지어낸 예시가 아니라
`evidence_bridge.py`가 실제로 생성한 질문과, 그 코드만 보고 별도 모델(Codex)이 독립
생성한 답변, 그리고 `feedback/reflection_signal.py`를 실제로 돌린 출력이다.

> **자동 생성된 질문** (`evidence_bridge.py` 실행 결과 그대로):
> "이 코드에 잠재적 위험 패턴이 있는데, 이 부분이 어떤 위험을 가질 수 있는지, 그리고
> 왜 이렇게 구현했는지 설명해보세요."

> **Codex 독립 생성 답변** (실제 코드 `Bookshelf.jsx`의 `dangerouslySetInnerHTML` 블록만 주고 생성):
>
> "이 부분은 dangerouslySetInnerHTML을 써서 XSS 위험이 있는 게 맞는 것 같습니다.
> item.title이랑 item.author가 네이버 도서 API에서 오는 값인데, 응답에 `<b>` 태그
> 같은 게 섞여 있어서 그냥 렌더링하면 태그가 텍스트로 보이는 문제가 있었고, 그걸
> 해결하려고 급하게 dangerouslySetInnerHTML로 처리했던 것 같습니다. 외부 API 응답이라도
> 신뢰할 수 있는 소스라고 안일하게 생각했던 것 같고, 스크립트 삽입 가능성 같은 건 그
> 당시엔 크게 고려하지 못했습니다. 지금 보니 정규식으로 필요한 태그만 걸러내거나
> DOMPurify 같은 걸로 sanitize하고 렌더링했어야 할 것 같습니다."

```bash
$ python3 feedback/reflection_signal.py "이 부분은 dangerouslySetInnerHTML을 써서 ..."
```
```json
{ "reflection_present": false, "matched_count": 0, "required_ok": false, "optional_matches": 0 }
```

이 답변은 XSS 실수를 정확히 인정하고("안일하게 생각했다"), 원인을 설명하고("태그가
텍스트로 보이는 문제"), 개선안까지 낸("DOMPurify로 sanitize") **정성적으로 훌륭한
reflection**인데, 우리 판정기는 0/4로 완전히 놓쳤다. 이게 아래 "가장 중요한 발견"
섹션의 근거다.

### Follow-up까지 실제로 2턴 완주 (`pipeline/followup_generator.py`, 팀 §3 전략표 구현)

위 1턴 답변을 `reflection_signal.py`로 분류하면 `self_error_recognition`이 안 걸린다
(정확한 문구 불일치). 팀 문서(`코드이해도_평가_질문및채점기준.md` §3)의 "오개념 감지 →
바로 정정하지 않고 반례로 스스로 모순을 발견하게 유도" 규칙을 그대로 적용해 **실제로
후속 질문을 자동 생성**했다:

```bash
$ python3 pipeline/followup_generator.py "tier-b-risk:Bookshelf.jsx" "이 부분은 dangerouslySetInnerHTML을..."
```
```json
{
  "followup_question": "그런데 만약 악의적인 사용자가 이 부분의 입력값을 의도적으로 조작한다면 어떤 일이 벌어질까요?",
  "trigger": "오개념 감지(self_error_recognition 미확인) → 소크라테스식 반례로 스스로 모순 발견 유도"
}
```

이 질문을 Codex(별도 모델, 같은 학생 역할 유지)에 그대로 넣어 2턴째 답변을 받았다:

> "이런 값이 조작되면 저장 부분에서 `<script>` 태그나 이벤트 핸들러 속성 같은 걸
> title이나 author에 넣어서 다른 사용자가 그 페이지를 볼 때 스크립트가 실행되게
> 만들 수 있을 것 같습니다. 예를 들어 세션 쿠키나 로컬스토리지에 있는 토큰을 탈취해서
> 외부 서버로 전송하거나, 사용자 몰래 다른 요청을 대신 보내는 것도 가능할 것 같고요.
> 저희 서비스는 API 응답을 그대로 신뢰했기 때문에 사실상 이 API 자체가 공격 벡터가
> 될 수 있었던 상황이라, 피해 범위가 생각보다 클 수 있었을 것 같습니다."

1턴 답변은 "안일하게 생각했다"는 인정에서 멈췄지만, 2턴 답변은 구체적 공격 시나리오
(script 삽입 → 쿠키/토큰 탈취 → 외부 전송, 대리 요청)까지 스스로 끌어냈다 — **follow-up이
1턴만으로는 안 드러나던 깊이를 실제로 끌어냈다는 걸 실측으로 확인**했다. 다른 3개
cognition-isolation 사례(Auth.jsx/Header.jsx/authToken.js)에도 같은 생성기를 실행해
카테고리 매치 개수에 따라 서로 다른 후속 질문(변형 질문/구체화 요청/다음 축 이동)이
정확히 갈리는 것도 확인했다(`isolation_hook`/`isolation_classifier` 재사용).

**정직한 한계**: 이건 A/B안처럼 "매번 새로 생성되는 LLM 적응형 질문"이 아니라, 팀
§3 전략표의 5개 방향 중 하나를 **미리 정의된 규칙(신호 분류 결과)으로 고르는** 것이다.
문구 자체는 고정 템플릿이고, 분기만 적응형이다. API가 생기면 같은 분기 로직 위에서
문구 생성만 LLM으로 교체 가능하도록 설계했다(`followup_generator.py` D48 EXIT 참조).

---

## 방법론 프롬프트 (박종호 문서 형식)

박종호 문서처럼 "질문 생성"과 "채점"을 나눠서 실제 원문을 그대로 옮긴다. **다만 정직하게
짚을 점이 있다 — C안/D안엔 "채점 프롬프트"가 없다.** A/B안은 LLM-as-Judge라 채점 자체가
프롬프트지만, 우리 판단 블록은 코드(규칙식)로 채점하지 프롬프트로 채점하지 않는다. 이
차이 자체가 C안의 "재현 가능성 100%" 장점의 원천이다.

### 질문 생성 (`pipeline/evidence_bridge.py`, `DEPTH_LADDER_OPENING`, 코드에서 그대로 발췌)

```python
DEPTH_LADDER_OPENING = {
    "cognition-isolation": "이 파일이 다른 형제 파일들과 달리 허브 모듈과 연결되어 있지"
        " 않은데, 이 구조를 선택/방치한 이유를 설명해보세요.",
    "architecture-diffusion": "이 파일이 여러 컴포넌트에서 공유되는 확산 지점인데,"
        " 왜 이런 구조를 선택했는지 설명해보세요.",
    "tier-b-risk": "이 코드에 잠재적 위험 패턴이 있는데, 이 부분이 어떤 위험을 가질 수"
        " 있는지, 그리고 왜 이렇게 구현했는지 설명해보세요.",
    "repeated-pattern": "이 패턴이 여러 파일에 반복되는데, 공용 모듈로 뽑지 않은 이유를"
        " 설명해보세요.",
}
```

finding의 `category`(id의 `:` 앞부분)로 위 4개 중 하나를 그대로 꺼내 쓴다 — 박진용/손진원
방식처럼 LLM이 매번 새로 질문을 생성하지 않고 **고정 템플릿 4개**만 쓴다(박진용의 B안과
같은 구조: "결정 포인트 감지 → 고정 질문 템플릿 로드"). 장점은 재현성, 단점은 서사성
부족(6개 cognition-isolation finding이 전부 문구까지 동일한 질문을 받음).

### 답변 생성 — 실제 Codex 호출에 쓴 프롬프트 골격 (역할극, 지어낸 답 방지용 구조)

```
역할극 요청입니다(보안 연구/교육 목적 시뮬레이션 — 실제 학생 데이터 아님).

당신은 아래 실제 코드를 작성한 학생 개발자입니다. 면접관이 이 코드에 대해 질문했고,
실제 주니어 개발자가 자기 코드를 설명할 때 나올 법한 자연스러운 한국어 톤(약간의
확신 부족, "~것 같습니다" 헤지 표현 포함)으로 2~4문장만 답변하세요. 메타코멘트 없이
학생 답변 텍스트만 출력하세요.

## 실제 코드 ({파일 경로, 실제 스니펫 그대로 삽입})
```{언어}
{cognition 블록이 실제로 읽은 코드 스니펫}
```
{finding에 필요한 추가 컨텍스트 — 예: "GenreContext.jsx라는 허브 모듈이 있는데 이 파일은
쓰지 않는다" 같은 사실 관계}

## 면접 질문
"{DEPTH_LADDER_OPENING에서 뽑은 질문 그대로}"

학생 답변만 출력하세요.
```

이 프롬프트를 7건(findings)에 각각 실제 코드만 바꿔 넣어 병렬 실행했고, 답변을 제가
미리 쓰지 않았다는 걸 보장하려고 "메타코멘트 없이 답변 텍스트만" 지시했다. 실제 실행
예시는 위 "실제 질문·답변 verbatim" 섹션 참조.

### 채점 — 프롬프트가 아니라 규칙식 (`judgment/subrubric.py`)

LLM에게 "몇 점 줘"라고 묻는 대신, 3개 축 × 4개 서브축(0~3점) 합산 후 상(≥9)/중(≥5)/하로
매핑한다. 예를 들어 `design_intent` 축:

```python
sub = {
    "repetition_consistency": clamp(repo 내 이 패턴 반복 횟수, 0~3),
    "idiom_conformance_reverse": {"confirmed": 0, "candidate": 1, "none": 3}[idiom_status],
    "rationale_signal": {"rationale": 3, "none": 1, "debt": 0}[파일 코멘트 스캔 결과],
    "mitigation_present": {True: 3, None: 1, False: 0}[방어 코드 존재 여부],
}
# 상=9점 이상, 중=5점 이상, 하=나머지
```

각 서브축엔 문헌 근거가 붙어 있다 — 예: `idiom_conformance_reverse`는 Allamanis & Sutton
(FSE 2014)의 idiom-mining 연구, `rationale_signal`은 Potdar & Shihab(ICSME 2014)의
Self-Admitted Technical Debt 탐지 연구. `risk` 축은 CVSS/FindBugs 문헌에 따라 신뢰도가
심각도 총점을 게이팅하는 구조로 별도 설계(D35, `judgment/subrubric.py` 참조).

---

## 재귀 hook 자기수정 메커니즘 — 이 방법론만의 차별점

다른 방법론(A/B/C 3안 모두 박진용 문서 기준)은 "판정을 한 번 내리면 끝"인데, 이쪽은
**idiom_hook / tier_b_hook / reflection_hook / isolation_hook** 4개의 재귀 확인 구조를
붙였다 — 같은 신호가 threshold(3회, 또는 근거에 따라 2회로 조정)만큼 반복 확인되기 전엔
"미확정"으로 남기고 자동 적용하지 않는다(B안의 "채점 일관성" 문제, 박진용이 지적한
"B안 키워드 암기 취약점"을 코드로 방어하는 접근).

## 답안 품질 6-axis 채점 (PaperOrchestra 루브릭 재사용, 축별 breakdown 전체)

가중치: scientific_depth×0.20 + technical_execution×0.20 + logical_flow×0.15 +
writing_clarity×0.15 + evidence_presentation×0.20 + academic_style×0.10

| Axis | A안 | B안 | C안 | D안 | E안 |
| --- | --- | --- | --- | --- | --- |
| scientific_depth | 60 | 75 | 55 | 65 | 50 |
| technical_execution | 70 | 75 | 90 | 70 | 45 |
| logical_flow | 55 | 65 | 80 | 70 | 75 |
| writing_clarity | 80 | 65 | 60 | 65 | 55 |
| evidence_presentation | 50 | 80 | 85 | 85 | 70 |
| academic_style | 40 | 70 | 90 | 80 | 85 |
| **가중 평균** | **60.25** | **72.50** | **76.00** | **72.25** | **61.00** |

**축별 근거**: A안이 낮은 이유는 logical_flow·evidence_presentation이 약해서다(점수
근거를 스스로 "왜 이 점수인지 모른다"고 인정할 만큼). C안이 가장 높은 이유는 실제
코드 실행·버그 수정·4개 repo 재현으로 technical_execution·academic_style이 가장
강해서다(LLM 논증이 없어 scientific_depth는 중간). E안의 technical_execution=45는
Codex가 독립 생성한 정성적으로 우수한 reflection조차 0/4로 놓친 실측 결과(D37)를
그대로 반영한 것 — logical_flow·academic_style(개념 설계)은 탄탄해도 실행
재현율(technical_execution)이 가장 낮다.

## 토큰 경제성 6-기준 채점 (0~10, 높을수록 경제적)

| 기준 | A안 | B안 | C안 | D안 | E안 |
| --- | --- | --- | --- | --- | --- |
| 인지 단계 비용(repo 분석) | 2 | 2 | 10 | 10 | 10 |
| 판단 단계 비용 | 2 | 3 | 10 | 8 | 9 |
| 질문 생성 비용 | 3 | 4 | 10(해당없음) | 7 | 10(해당없음) |
| 반복 실행 비용 | 1 | 1 | 10 | 6 | 9 |
| 사람 개입 비용 | 3 | 3 | 6 | 5 | 5 |
| 확장성(다른 repo) | 2 | 2 | 9 | 6 | 8 |
| **평균** | **2.17** | **2.50** | **9.17** | **7.00** | **8.50** |

C안이 "저비용·고품질" 사분면에 유일하게 위치하지만, **애초에 대화(Ownership 검증)를
하지 않는다는 근본적 범위 제한**이 있다 — 이건 박진용의 B안("빠르지만 판별력 없음")과
정확히 같은 구조의 트레이드오프다.

---

## 실측으로 드러난 가장 중요한 발견: "재현율 실패"와 "과탐지"는 다르다

E안(Reflection Hook)이 Codex 독립 생성 답변 7건 전부에서 통과 실패(0/7)했지만, fact-check
결과 원인이 두 갈래로 갈렸다.

1. **1건(Bookshelf.jsx, tier-b-risk)은 진짜 재현율 실패다** — XSS 실수를 정확히 인정하고
   DOMPurify 개선안까지 낸 고품질 reflection인데 confirmed 패턴 문구와 표현이 달라 놓쳤다.
2. **6건(cognition-isolation)은 원래 "오류 정정"이 필요한 상황 자체가 아니었다** —
   Codex 6명 전부가 GenreContext 미사용에 대해 각자 다른 타당한 설계 근거(역할 위임/
   성능 최적화/대체 저장소/도메인 무관)를 제시했다. 이건 **C안의 cognition-isolation
   판정 규칙(다중 concern 코드베이스에서 "형제는 다 허브를 써야 한다"는 가정) 자체가
   여전히 과탐지 중이라는 6번째 독립 증거**다.

이에 대응해 `isolation_hook.py`를 별도로 구현했다 — idiom_hook처럼 "정규식 하나=패턴
하나"가 아니라 "카테고리 하나(동의어 alternation)=패턴 하나"로 설계해 자연어 표현
다양성 문제를 완화했고, 실측 결과 6건 중 5건을 정확히 "타당한 근거 있음"으로 분류,
근거가 부족한 1건은 성급히 확정하지 않고 그대로 미확정으로 남겼다.

**추가 발견(D51/D52, escalation_hook 구현 중 실측)**: 위 "0/7"이라는 숫자 자체의
전제도 재검증한 결과 부정확했다. reflection_hook의 최초 confirmed 패턴 4개
(too_trusted_browser 등)는 서로 다른 4개 사례가 아니라 **같은 캐노니컬 예시 문장 하나를
"round 1/2/3"으로 3번 반복 제출해서 확정된 것**이었다 — D41이 다른 모든 카테고리에
적용한 "독립 출처 원칙"이 reflection_hook의 최초 시드 자체에는 소급 적용되지 않았던
것. 재계산 로직을 "같은 출처 반복 제출은 1표만 인정 + 재계산 시 강등도 가능"으로
고치고 나니 **4개 패턴 전부 candidate로 강등**됐다. 즉 지금 reflection_hook은
confirmed 패턴이 0개다 — "재현율 0/7"이 아니라 "애초에 신뢰할 수 있는 confirmed
패턴이 하나도 없었다"가 더 정확한 진단이다. 이 발견 자체는 나쁜 소식이 아니라 D6/D41
원칙이 스스로를 감사(audit)해서 잡아낸 성공 사례로 본다.

---

## 팀 공통 병목과의 수렴

김만서 문서의 결론 — **"Repository Knowledge와 Ownership을 구분해야 한다"** — 는 이쪽
결과와 정확히 같은 지점에서 재확인된다. C안은 코드만으로 "무엇이 이상한가"는 정확히
찾아내지만(Repository Knowledge), "왜 그렇게 설계했는가/재설계한다면 뭘 바꿀 것인가"
(Ownership)는 대화 없이는 원천적으로 측정할 수 없다. D안이 이 간극을 메우려 evidence
기반 질문을 자동 생성했지만, 여전히 **단발 질문**이고 손진원 문서처럼 follow-up으로
점점 깊이 들어가는 멀티턴 Socratic 루프는 구현·검증하지 못했다(API 키 미보유로
실제 대화 세션 자체가 미검증 상태).

## 결론 및 추천

**순수 C안(무료·빠름)만으로는 Ownership 검증이 불가능하다** — 박진용의 "B안만으론
부족하다"와 동일한 결론. 다만 C안+재귀 hook이 제공하는 **감사 가능한 근거(Evidence
Trace)**는 A안(LLM-as-Judge)의 블랙박스 채점 문제를 보완하는 방향으로 결합할 수 있다.
이건 박진용의 최종 권장 전략("B안으로 골격 구축 → A안으로 채점엔진 교체")과 같은
결의 결론이다 — **C안을 저비용 1차 필터로 두고, 남은 finding에 A/B안류의 실제 대화형
Ownership 인터뷰를 붙이는 하이브리드**가 다음 단계다.

## 다음 과제 3가지

1. **Reflection 재현율** — 자연어 표현이 매번 달라 정규식 하나로는 못 잡는다.
   `isolation_hook`처럼 "카테고리 단위 동의어 alternation"으로 일반화했지만, 이 설계가
   held-out(다른 repo) 데이터에서도 통하는지는 아직 미검증.
2. **cognition-isolation 과탐지** — 다중 concern 코드베이스에서 구조 신호만으로는
   "타당한 설계"와 "방치"를 구분 못한다. `isolation_hook`이 1차 완화책이지만 카테고리
   경계를 사람이 미리 정해야 하는 한계가 남는다.
3. **멀티턴 라이브 대화 미검증** — API 키 부재로 실제 세션(질문 생성 지연, 히스토리
   압축, 세션당 비용)을 전혀 측정하지 못했다. 박진용 문서의 실측치(세션당 $0.05~0.15,
   질문 생성 3~5초 지연, SSE 스트리밍 필요)를 그대로 설계 기준으로 참고해야 한다.

## 제 의견

1. **C안 자체를 "Ownership 판정 엔진"으로 팔면 안 된다고 생각합니다.** C안의 진짜
   가치는 정확도가 아니라 "비용을 0으로 만들어서, 그 다음 단계인 대화형 검증에 예산을
   몰아줄 수 있게 하는 1차 필터"라는 데 있습니다. 포지셔닝을 "채점기"가 아니라
   "트리거"로 잡아야 한다고 봅니다.
2. **Reflection Hook의 재현율 문제는 정규식 기반 접근의 근본적 한계라고 봅니다.**
   `isolation_hook`처럼 카테고리 단위로 넓혀도 결국 사람이 카테고리를 미리 정의해야
   하는 한계가 남습니다. 다음 단계로 소형 분류 모델이나 임베딩 유사도를 검토할
   가치가 있다고 생각하지만, 이건 "규칙기반의 장점(비용 0, 완전 재현)"을 일부
   포기하는 트레이드오프라 신중하게 결정해야 합니다.
3. **`cognition-isolation` 같은 구조 규칙의 "허브 하나에 다 모여야 한다"는 가정 자체가
   틀렸다는 게 이번 검증(LMS 6/6)에서 명확해졌습니다.** 패치보다 근본적으로,
   "여러 개의 국소 허브(concern별로 하나씩)를 허용"하는 방향으로 판단 블록을 다시
   설계하는 걸 다음 스프린트에서 논의해보고 싶습니다.

## Notion 팀 비교표 채워 넣을 내용 (이름/질문 생성/Follow-up 질문/평가 방식/평가 근거)

| 이름 | 질문 생성 | Follow-up 질문 | 평가 방식 | 평가 근거 |
| --- | --- | --- | --- | --- |
| 노경천 | Tier A/B 구조·위험 신호 기반 자동 질문 템플릿(D안, `evidence_bridge.py`, LLM 없이 코드 신호로 질문 생성) | 규칙 기반 적응형 분기(`followup_generator.py`) — 팀 §3 전략표를 `isolation_classifier`/`reflection_signal` 분류 결과로 구현, 4개 실제 사례 검증 + Bookshelf.jsx 2턴 완주 | 규칙식 서브루브릭(`subrubric.py`, 0~12점→상/중/하) + 재귀 확인 hook(idiom/tier_b/isolation/reflection) | subrubric breakdown(문헌 인용) + Evidence Trace(`evidence_bridge`) + hook confirmations 로그, 전부 100% 재현 가능 |
