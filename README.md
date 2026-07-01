# Code Review with Feedback — 인지 · 판단 · 피드백 3블록 리뷰 시스템

GitHub 레포의 "코드 이해도"를 검증하기 위한 3블록 파이프라인 실험 구현.
채점기가 아니라 **"왜 이렇게 만들었는지 설명할 수 있는가"를 검증하는 레이어**를 목표로 한다.

```
Repository
    │
    ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  인지 Block  │──▶│  판단 Block  │──▶│ 피드백 Block │
│ (Cognition) │   │ (Judgment)  │   │ (Feedback)  │
└─────────────┘   └─────────────┘   └─────────────┘
 구조/위험 스캔      우선순위·심각도       Depth Ladder
 (기계적 사실)        채점(정성 규칙)      7단계 질문 생성
```

## 왜 3블록으로 나눴는가

기존 코드리뷰 도구(Claude Code Review, CodeRabbit)와 채점 루브릭(PaperOrchestra 6-axis)을 검토한 결과,
대부분 "사실 파악"과 "판단(채점)"을 한 단계에서 처리해 경계가 불분명했다. 이 프로젝트는 세 단계를
명시적으로 분리해서 각 단계의 출력을 독립적으로 검증 가능하게 만든다.

## 디렉토리 구조

| 경로 | 블록 | 역할 |
|---|---|---|
| [`cognition/two_tier_scan.py`](./cognition/two_tier_scan.py) | 인지 | Tier A(구조 스캔, 저비용) + Tier B(위험 키워드 트리거 시에만 발동하는 내용 스캔) |
| [`judgment/score_findings.py`](./judgment/score_findings.py) | 판단 | 인지 블록 출력을 받아 설계의도/질문가치/위험도 3축으로 규칙 기반 채점, 우선순위 산출 |
| [`judgment/subrubric.py`](./judgment/subrubric.py) | 판단 | 3축을 각 4개 서브축(0~12점)으로 세분화해 근거 기반 채점 후 상/중/하로 재매핑(하위호환). 설계 배경: [`SUBRUBRIC_DRAFT.md`](./judgment/SUBRUBRIC_DRAFT.md) |
| [`judgment/idiom_filter.py`](./judgment/idiom_filter.py) | 판단 | finding의 `pattern_key`가 confirmed 관용 패턴과 일치하면 질문가치를 낮춤 (언어별 저장소 참조) |
| [`judgment/idiom_hook.py`](./judgment/idiom_hook.py) | 판단 | 관용 패턴 재귀 업데이트 훅 — 피드백 로그 적재(`feedback`) + threshold 도달 시 candidate→confirmed 승격(`update`) |
| [`judgment/idioms/<lang>/`](./judgment/idioms/) | 판단 | 언어별(javascript/python/java/c/cpp/swift) 관용 패턴 상태(`idiom_patterns.json`)와 피드백 로그(`idiom_feedback_log.jsonl`) |
| [`judgment/tier_b_hook.py`](./judgment/tier_b_hook.py) + [`tier_b_suppression_filter.py`](./judgment/tier_b_suppression_filter.py) | 판단 | Tier B 오탐을 (trigger, matched_text) 단위로 재귀 억제(idiom_hook과 동일 패턴). "인지 블록용"으로 요청됐지만 신뢰도 판단이라 판단 블록에 위치(D14) |
| [`feedback/depth_ladder_template.md`](./feedback/depth_ladder_template.md) | 피드백 | What→How→Why→Alternative→Trade-off→Constraint→Reflection 7단계 강제 템플릿 |
| [`feedback/generate_questions.py`](./feedback/generate_questions.py) | 피드백 | 판단 블록 출력을 받아 Anthropic tool-use로 7단계 질문을 실제 LLM 호출로 자동 생성(스키마 강제, 필드 누락 시 예외) |
| [`feedback/reflection_signal.py`](./feedback/reflection_signal.py) + [`reflection_hook.py`](./feedback/reflection_hook.py) | 피드백 | Depth Ladder 7단계(Reflection) 판정을 idiom_hook과 동일한 재귀 확인 패턴으로 가드 — 자기오류인식/이유설명/새판단/개선안 4개 서브신호가 전부 confirmed 패턴으로 매치돼야 True |
| [`examples/study_match/`](./examples/study_match/) | 전체 | 실제 공개 repo(Study-Match-)에 3블록 전부를 돌린 실행 결과, 관용 패턴 필터 데모 포함 |
| [`pipeline/run_pipeline.py`](./pipeline/run_pipeline.py) | 전체 | 인지→판단 실행 + `injections.json`에 명시된 재귀 hook(idiom/tier_b)을 순차 주입하며 단계마다 before/after 비교표 자동 생성 |
| [`pipeline/ledger.py`](./pipeline/ledger.py) + `ledger.jsonl` | 전체 | 매 주입을 append-only로 영구 기록 — "지금까지 시도한 방법론들 비교해서 보여줘"에 답하는 데이터 소스 |
| [`pipeline/compare_methodologies.py`](./pipeline/compare_methodologies.py) | 전체 | ledger.jsonl을 즉시 집계해 방법론간 비교표를 렌더링(재실행 없이 언제든 조회 가능) |
| [`examples/lms/`](./examples/lms/) | 전체 | 두 번째 실제 공개 repo(jxxnixx/LMS, JS/TS 51파일)에 파이프라인 전체를 돌린 실행 결과 |
| [`examples/shadowbroker/`](./examples/shadowbroker/) | 전체 | 세 번째 실제 공개 repo(Shadowbroker, Python+TS 726파일 monorepo) — tier_b 방법론 첫 실증 |
| [`pipeline/evidence_bridge.py`](./pipeline/evidence_bridge.py) | 전체 | D안(B안+C안 결합) — C안 finding을 B안 형식 Repository Evidence + 질문으로 자동 변환 |
| [`pipeline/followup_generator.py`](./pipeline/followup_generator.py) | 전체 | D안 적응형 Follow-up — 팀 §3 전략표를 isolation_classifier/reflection_signal 분류로 구현, Bookshelf.jsx 2턴 완주로 검증(D48) |
| [`pipeline/escalation_hook.py`](./pipeline/escalation_hook.py) | 전체 | keyword hook 검출 실패 → Socratic escalation → judge 판정을 hook에 재귀 반영(D50). 테스트 중 dedup 버그(D51) + reflection_hook 최초 4패턴 전부 강등(D52) 발견 |
| [`examples/lms/d_plan/`](./examples/lms/d_plan/) | 전체 | D안을 LMS에 실행한 결과 + Codex로 독립 생성한 답변 7건 전체 검증([`codex_verification_full.md`](./examples/lms/d_plan/codex_verification_full.md)), A~E안 비교 및 6-axis 채점표 |
| [`judgment/isolation_hook.py`](./judgment/isolation_hook.py) + [`isolation_classifier.py`](./judgment/isolation_classifier.py) | 판단 | cognition-isolation 판정용 재귀 hook — "정규식 하나"가 아니라 "카테고리(동의어 alternation)" 단위로 타당한 설계 근거를 축적·확정([`검증 결과`](./examples/lms/d_plan/isolation_hook_verification.md)) |

## 실행 방법

```bash
# 1) 인지 블록 — 레포 소스 디렉토리를 스캔
python3 cognition/two_tier_scan.py <repo>/src > scan_output.json

# 2) 판단 블록 — 인지 블록 출력을 받아 우선순위 채점
python3 judgment/score_findings.py scan_output.json <repo>/src > judgment_output.json

# 3) 피드백 블록 — judgment_output.json의 각 finding에 7단계 질문을 실제 LLM 호출로 자동 생성
pip install -r requirements.txt
export ANTHROPIC_API_KEY=<your-key>
python3 feedback/generate_questions.py judgment_output.json          # 전체 finding, JSON 출력
python3 feedback/generate_questions.py judgment_output.json 2 --md   # 상위 2건만, 마크다운 출력

# (fallback) API 키 없이 수기로 채우고 싶으면 feedback/depth_ladder_template.md의 체크리스트 사용
```

### Reflection 판정 재귀 확인 훅 (Depth Ladder 7단계 전용)

```bash
# 학생 답변 텍스트로 즉시 판정(초기엔 confirmed 패턴이 없어 항상 False — 보수적 기본값)
python3 feedback/reflection_signal.py "<학생 답변 텍스트>"

# 사람이 "이 정규식은 진짜 이 서브신호를 나타낸다"고 판정하면 로그에 적재
python3 feedback/reflection_hook.py feedback <sub_signal> <pattern_id> "<regex>" genuine_signal "<note>"

# 로그를 재집계해 threshold(기본 3회) 이상 쌓인 pattern_id를 candidate→confirmed로 승격
python3 feedback/reflection_hook.py update <sub_signal>
```

`<sub_signal>`은 `self_error_recognition | reason_explanation | new_judgment | concrete_improvement`
중 하나. 4개 전부 confirmed 패턴으로 매치돼야 `reflection_present=true`(AND 조건, D33).

### 관용 패턴 재귀 업데이트 훅 (언어별)

```bash
# 사람/후속 리뷰가 finding을 "그냥 관용 패턴이었다"고 판정하면 로그에 적재
python3 judgment/idiom_hook.py feedback <lang> <pattern_key> idiom_not_decision "<note>" "<description>"

# 로그를 재집계해 threshold(기본 3회) 이상 쌓인 pattern_key를 candidate→confirmed로 승격
python3 judgment/idiom_hook.py update <lang>
# 전체 언어 일괄 재집계
python3 judgment/idiom_hook.py update-all
```

`<lang>`은 `javascript | python | java | c | cpp | swift` 중 하나(파일 확장자로 자동 판별되며,
이 명령은 로그를 남기거나 승격을 재계산할 때만 언어를 직접 지정한다). 승격된 언어의
`idiom_patterns.json`만 갱신되고 다른 언어 저장소는 전혀 건드리지 않는다.

## 실행 예시 (Study-Match-, public React+Firebase, 10파일/1,598줄)

`cognition` → `judgment` 파이프라인이 실제로 뽑아낸 5건 (관용 패턴 필터 적용 후):

| 우선순위 | Finding | 어느 Tier/필터에서 잡았나 |
|---|---|---|
| 최우선 | `Competitions.tsx`가 허브 모듈(firebase.ts)과 연결 없음 (fan_in만 보면 정상으로 보임) | Tier A + edge 분석 |
| ~~질문 대상~~ → 우선순위 낮음 | `App.tsx`의 `useAuth` Context(fan_in=6, 허브 다음 확산 지점) | Tier A로 후보 포착 → **idiom_filter가 자동 강등**(아래 관용 패턴 필터 데모 참고) |
| Important(🔴) | `firebase.ts`에서 인증정보(uid/email)가 `JSON.stringify`되어 `throw`된 Error에 담김 | Tier B (트리거 매치, 파일 10개 중 2개만 딥리드 → 비용 80% 절감) |
| 검토 대상 | `Competitions.tsx` 시크릿 패턴 매치 — **실측 오탐**(캐글 URL 문자열의 `risk-s`가 `sk-`와 우연히 매치). 판단 블록이 자동 확정하지 않고 별도 등급으로 격리 | Tier B |
| 질문 대상 | `onSnapshot`이 4개 파일에 반복 등장(공용 훅 미추출) | 반복 패턴 스캔 |

전체 원본 출력은 [`scan_output.json`](./examples/study_match/scan_output.json), [`judgment_output.json`](./examples/study_match/judgment_output.json), 7단계 질문까지 채운 최종 결과는 [`findings.md`](./examples/study_match/findings.md) 참고.

### 관용 패턴 필터 데모 — useAuth Context가 실제로 강등된 과정

1. `idiom_hook.py feedback javascript react-context-global-state idiom_not_decision`을 3회 기록
2. `idiom_hook.py update javascript` → `promotion_threshold=3` 도달 → `judgment/idioms/javascript/idiom_patterns.json`에서 `status: candidate → confirmed`
3. `score_findings.py` 재실행 → `App.tsx` finding의 `질문가치`가 `상 → 하`로 자동 강등, `priority`에 강등 사유 자동 표기
4. 다른 언어(`python`/`java`/`c`/`cpp`/`swift`) 저장소는 `patterns: []`로 그대로 — 언어별 분리가 실제로 작동함을 확인

전 과정이 재현 가능한 명령으로 [`examples/study_match/findings.md`](./examples/study_match/findings.md)의 "관용 패턴 필터 데모" 절에 기록되어 있다.

## 다국어 재검증 실측 (RunPod_Deploy_Agent, public, Python 6개 + JS 2개 혼합)

인지 블록을 다국어로 확장(D13)한 뒤 실제 두 번째 공개 repo에 돌려서 확인한 것:

- Python import 파싱이 실제로 작동함: `large-model-loader-guard.py`가 `bnb_manual_device_map.py`/`env_setup.py`를 import하는 edge를 정확히 잡음
- **새 오탐 발견 및 수정(D17)**: `model.eval()`(PyTorch 표준 API, 안전)이 위험한 전역 `eval()` 호출로 오탐지됨 → `(?<!\.)` 부정 후방탐색으로 메서드 호출 형태를 배제해 수정, 재실행으로 오탐 사라짐 확인
- **새 한계 발견(미수정, 기록만)**: 이 repo는 파일 10개에 edge가 단 2개뿐인 희소 그래프라 "허브" 개념 자체의 신뢰도가 낮음(fan_in=1짜리 두 파일이 우연히 hub 후보가 됨). Study-Match-처럼 edge가 충분히 많은 그래프에서만 hub/isolation 판정이 의미 있다는 게 실측으로 드러남

## 세 번째 실증: jxxnixx/LMS (public, JS/TS 51파일/4,175줄) — 재귀 hook 폐루프 전체 검증

`pipeline/run_pipeline.py`로 인지→판단→hook 주입→비교표 생성을 한 번에 실행. 결과 원본:
[`examples/lms/`](./examples/lms/), 재현 명령:
```bash
python3 pipeline/run_pipeline.py LMS/src pipeline/examples/lms_injections.json
```

**실행 중 발견하고 즉시 고친 버그 3개(전부 재검증 완료)**:
- **D18 — `@/` 경로 별칭 import 전량 누락**: 이 repo는 `@/api/...` 형태 alias import를 99건 쓰는데 기존 코드는 상대경로(`.`)만 인식해 그래프가 사실상 텅 빔(최대 fan_in=2/51파일). `@/`도 로컬 import로 인식하게 수정 → 최대 fan_in 12로 정상화
- **D19 — 고립 판정 범위 오류로 오탐 대폭발**: 기존 로직은 "fan_in≥1인 전체 파일 중 허브에 안 걸린 파일"을 전부 고립으로 판정 → 51개 중 30개가 "최우선"으로 쏟아짐. "entry→root가 직접 라우팅하는 형제 파일"로 비교 범위를 제한해 30건 → 6건으로 정상화(Study-Match- 회귀는 그대로 통과)
- **D20 — Tier B `eval_or_dangerous_html` 트리거를 finding화하는 규칙 자체가 누락**: 인지 블록은 `Bookshelf.jsx`의 `dangerouslySetInnerHTML`을 정확히 잡았는데 판단 블록에 대응 규칙이 없어 조용히 버려지고 있었음 → 규칙 추가, Important(🔴)로 정상 노출 확인

**재귀 hook 폐루프 실제 검증(D21/D22)**: `useBooksQueries.ts`(fan_in=6, 확산 후보)를 실제 코드 검토 결과
`@tanstack/react-query` 공식 문서 권장 컨벤션(리소스당 커스텀 훅)으로 판단해 idiom_hook에 주입 →
`architecture-diffusion:useBooksQueries.ts` 질문가치가 상→하로 자동 강등됨(아래 표). **반면 진짜 위험
신호(`dangerouslySetInnerHTML`, 네이버 API 응답을 그대로 렌더링하는 실제 XSS 가능 지점)는 주입 대상에서
의도적으로 제외** — 오케스트레이터가 무조건 다 억제하지 않고, 사람이 실제로 코드를 읽고 판단한 것만
반영한다는 걸 보여주는 사례.

| Finding | Before | After | 변화 |
|---|---|---|---|
| `architecture-diffusion:useBooksQueries.ts` | 상 | **하** | ✅ 관용 패턴으로 강등 |
| `tier-b-risk:Bookshelf.jsx:dangerous-html` | 중 | 중 | — (진짜 위험이라 주입 안 함) |
| `cognition-isolation:*` (6건) | 상 | 상 | — (관용패턴 hook 대상 아님, 별도 검토 필요) |

**남은 한계(정직하게 기록)**: D19로 범위를 좁혔어도 `authToken.js`처럼 GenreContext와 개념적으로
무관한 파일이 여전히 "고립"으로 잡힌다 — "형제는 전부 허브를 써야 한다"는 가정 자체가 관심사가
여러 개인 코드베이스에서는 부분적으로만 맞다. 관용패턴 hook과 별개로 "고립 판정용" 억제 메커니즘이
아직 없음(다음 단계 9번).

## 방법론간 비교표 — 축적된 원장을 즉시 조회 (D23~D26)

`run_pipeline.py`는 실행할 때마다 결과를 `pipeline/ledger.jsonl`에 append하고, 언제든
`compare_methodologies.py`로 지금까지 시도한 모든 방법론(idiom_hook 패턴별/tier_b_hook 트리거별)을
집계해서 볼 수 있다 — 재실행 없이 즉시 조회된다.

```bash
python3 pipeline/compare_methodologies.py
```

실제 축적된 결과(Study-Match-·LMS·Shadowbroker 3개 repo, idiom 2개 + tier_b 1개 패턴 확정):

| 방법론 | 키 | 적용 repo 수 | 총 주입 횟수 | 변경된 finding 누적 | 최근 예시 |
|---|---|---|---|---|---|
| idiom | `react-context-global-state` | 1 | 2 | 1 | `Study-Match-`: `architecture-diffusion:App.tsx` 상→하 |
| idiom | `react-query-custom-hook` | 1 | 2 | 1 | `LMS`: `architecture-diffusion:useBooksQueries.ts` 상→하 |
| tier_b | `hardcoded_secret_pattern` | 1 | 1 | 1 | `Shadowbroker`: `tier-b-risk:test_api_settings.py:secret` 하→(제거됨) |

**실행 중 발견한 버그(D25)**: 같은 repo를 실행 위치에 따라 다른 상대경로(`Study-Match-/src` vs
`repo_candidates/Study-Match-/src`)로 기록해 "적용 repo 수"가 1이어야 할 게 2로 잘못 집계됨 →
`normalize_repo()`로 마지막 디렉터리명 기준 정규화해 수정, 재검증 완료.

### tier_b 방법론 첫 실증(Shadowbroker, public, Python+TS 혼합 monorepo, 726파일)

`pipeline/examples/shadowbroker_injections.json`으로 실제 테스트 픽스처 오탐(`backend/tests/test_api_settings.py`의
`AIS_API_KEY="saved-ais-key"` — 명백한 플레이스홀더, 실제 크리덴셜 아님)을 tier_b_hook에 주입해 확인.

**부수적으로 발견한 더 근본적인 한계(D26, 미수정·정직하게 기록)**: `meshIdentity.ts`(1500줄 이상)에서
`auth_info_leak_via_thrown_error` 트리거가 오탐지됨 — "email"이라는 단어가 파일 8번째 줄 **주석**
(`// No email.`)에만 등장하고, `JSON.stringify`/`throw`는 완전히 무관한 다른 함수들(암호화 키 직렬화,
에러 핸들링)에서 나타남. 이 트리거는 "3개 키워드가 같은 파일 어딘가에 다 있으면" 발동하는데, 파일이
커질수록 우연한 동시발생(coincidence) 확률이 올라가 정밀도가 떨어진다 — Study-Match-의 firebase.ts처럼
작은 파일에선 잘 통했던 설계가 대형 파일에서는 근접성(proximity) 체크 없이는 못 버틴다는 게 실측으로
드러남. `tier_b_hook`으로 이 특정 매치("email")를 억제하면 다른 파일의 진짜 위험까지 같이 막을 수 있어
(매치 텍스트가 너무 일반적) 주입하지 않았다 — 코드 레벨 수정(근접성 검사)이 필요한 사안으로 별도 기록.

## 알려진 한계 (숨기지 않고 기록)

- ~~fan-in 이중계산~~ — **D12로 수정**: edge를 (src,dst) 집합으로 dedupe 후 집계, `firebase.ts` 실측 fan-in이 8→7로 정정됨
- ~~Tier B secret 오탐(`risk-s`가 `sk-`에 매치)~~ — **수정**: `\bsk-` 단어경계 강제로 해결
- ~~Tier B eval 오탐(`model.eval()`)~~ — **D17로 수정**: 위 "다국어 재검증 실측" 참고
- **관용 패턴 감지 정규식의 취약성**: `createContext(` 단순 매치는 TypeScript 제네릭(`createContext<AuthContextType>(`)을 실측에서 한 번 놓쳤다. `createContext\s*(<[^>]*>)?\s*\(`로 수정했지만, 이런 구문 변형은 언어/문법마다 계속 나올 수 있음
- **언어 판별의 `.h` 모호성** — **D15로 부분 완화**: repo_root가 주어지면 C++ 전용 토큰(`class`/`namespace`/`template<`/`std::`) 유무로 재판정하지만, 그 토큰들을 안 쓰는 C++ 헤더는 여전히 c로 오판정 가능. 실제 C/C++ repo로는 아직 검증 안 됨
- **hub 판정이 희소 그래프에서 신뢰도 낮음(신규 발견, 미수정)**: RunPod_Deploy_Agent처럼 edge가 몇 개 안 되는 repo에서는 fan_in=1짜리가 "허브"로 뽑혀도 의미가 약함 — 최소 edge 수 임계값 미달 시 hub 판정 자체를 보류하는 로직이 없음
- **javascript 외 언어의 관용 패턴 저장소는 전부 빈 상태(미검증)**: python/java/c/cpp/swift는 구조(디렉토리·threshold)만 있고 실제 피드백으로 채워진 패턴이 하나도 없음
- **`feedback/generate_questions.py`는 제어 흐름만 검증됨, 실제 LLM 출력 품질은 미검증**: 스키마 강제(7단계 필드 누락 시 예외)·API 키 없을 때 실패 방식·마크다운 렌더링은 스텁 클라이언트로 확인했지만, 실제 Anthropic API를 호출해 생성된 질문의 품질(판별력, Depth Ladder 취지 부합 여부)은 이 세션에서 검증하지 않았음(API 키/과금 필요)

## 설계 결정 로그

- **D1** ([`feedback/depth_ladder_template.md`](./feedback/depth_ladder_template.md)) — 피드백 블록은 7단계 전부를 필수 필드로 고정
  - WHY: 즉흥 생성 시 항목 간 깊이 편차가 재현 불가능한 수준으로 커짐(실측: 4건 중 1건만 우연히 7단계 다 채움)
  - COST: finding마다 질문 7개를 다 만들어야 해서 생성 비용 증가 → 판단 블록에서 우선순위 상위로 걸러진 항목에만 적용해 상쇄
  - EXIT: 과하면 What/Why/Reflection 3단계 축소판으로 다운그레이드(필드명은 유지해 하위호환)
- **D2** ([`cognition/two_tier_scan.py`](./cognition/two_tier_scan.py)) — 인지 블록을 Tier A(구조)/Tier B(위험 트리거 내용)로 이원화
  - WHY: 그래프/import 스캔만으로는 내용 기반 이슈(인증정보 유출)를 못 잡음 — 실측으로 확인
  - COST: 위험 키워드 사전에 없는 새 패턴은 여전히 놓침, 정규식 특성상 오탐 발생
  - EXIT: `RISK_TRIGGERS`에 항목 추가, 또는 판단 블록의 hook 재귀 업데이트(발동 로그 기반 자동 승격)로 대체
- **D3** ([`judgment/score_findings.py`](./judgment/score_findings.py)) — 판단 블록은 규칙 기반 정성 채점(상/중/하), ML 아님
  - WHY: 사례가 적고 기준이 명확해(설계의도/질문가치/위험도) 규칙 기반이 더 투명하고 디버깅 가능
  - COST: 새 패턴이 생기면 사람이 직접 규칙을 추가해야 함(자동 일반화 안 됨)
  - EXIT: 규칙이 늘어나 유지보수 안 되면 `judgment_rules.yaml`로 분리, 또는 hook 재귀 업데이트로 자동 보정
  - **후속 조치(D5~D7로 해소)**: "관용 패턴 vs 진짜 설계 결정" 자동 구분이 없다는 COST는 아래 idiom filter로 해결
- **D4** (예시 repo 선정) — 공개 repo 중 diskUsage 최소(102KB)·fork 아님·원본 작업인 `Study-Match-`를 데모 대상으로 채택
  - WHY: 토큰 소비 최소화 + 실제 학생 포트폴리오형 구조라 이 시스템의 실제 타겟군을 대표
  - COST: 단일 소규모 repo만 검증 — 대형/다언어 repo에서 Tier A/B 로직이 그대로 통하는지는 미검증
  - EXIT: `cognition/two_tier_scan.py`는 언어 무관 regex 기반이라 Python/Java 등에도 그대로 적용 가능, 대형 repo로 재검증 필요
- **D5** ([`judgment/idiom_filter.py`](./judgment/idiom_filter.py)) — 관용 패턴 목록을 코드가 아니라 별도 상태 파일(`idioms/<lang>/idiom_patterns.json`)로 분리
  - WHY: 관용 패턴 목록은 계속 늘어나는 "데이터"이지 "로직"이 아님 — 분리해야 재귀 업데이트가 코드 재배포 없이 가능
  - COST: 상태 파일이 stale하면 같은 코드에서도 실행 결과가 달라짐(재현성 저하)
  - EXIT: 상태 파일을 git에 커밋해 버전관리 → 이상 동작 시 git revert로 특정 시점 복원
- **D6** ([`judgment/idiom_hook.py`](./judgment/idiom_hook.py)) — 단일 피드백으로 즉시 confirmed 승격하지 않고 threshold(기본 3회) 반복 확인 후 승격
  - WHY: 한 번의 판단으로 확정하면 특정 사례에 과적합되어 실제 위험 신호까지 묻어버릴 위험(RunPod_Deploy_Agent BLOCK 남발 금지 사례, arXiv:2603.18059 — 엄격 policy 시 성공률 0.356→0.067 붕괴 선례 적용)
  - COST: 승격까지 시간이 걸려 초반엔 관용 패턴도 계속 "질문가치 상"으로 남아있음(느린 수렴)
  - EXIT: `promotion_threshold`가 `idiom_patterns.json` 필드로 노출되어 있어 값만 바꾸면 즉시 조정 가능
- **D7** ([`judgment/idioms/`](./judgment/idioms/)) — 관용 패턴 저장소를 언어별로 분리(`javascript/python/java/c/cpp/swift`)
  - WHY: 관용 패턴은 언어/프레임워크에 강하게 종속됨(JS Context vs Java static Singleton vs C 전역 변수) — 하나로 합치면 한 언어에서 학습한 패턴이 다른 언어의 진짜 위험 신호까지 걸러버릴 수 있음
  - COST: 언어 수만큼 상태 파일/로그가 늘어나 관리 포인트 증가, 확장자 기반 언어 판별의 오분류 가능성(`.h`)
  - EXIT: 새 언어는 `idiom_filter.py`의 `LANG_EXT_MAP`에 확장자 매핑만 추가하면 됨
- **D11** ([`feedback/generate_questions.py`](./feedback/generate_questions.py)) — 피드백 블록 7단계 질문 생성을 Anthropic tool-use로 자동화
  - WHY: 수기 생성 시 즉흥 편차 문제(D1)가 코드 레벨에서 완전히 해소 안 됨 — tool-use 스키마로 7단계 필드를 강제하면 누락 시 예외로 즉시 드러남
  - COST: API 키/네트워크 의존성 생김, 호출당 비용 발생, 오프라인 실행 불가. 이 세션에서는 스텁 클라이언트로 제어 흐름만 검증했고 실제 API 호출 품질은 미검증
  - EXIT: `ANTHROPIC_API_KEY` 없으면 즉시 중단(조용히 실패 안 함). API 없이 쓰려면 `feedback/depth_ladder_template.md` 수기 체크리스트로 되돌아가면 됨(코드 삭제 불필요)
- **D12** ([`cognition/two_tier_scan.py`](./cognition/two_tier_scan.py)) — fan-in을 (src,dst) edge 집합으로 dedupe한 뒤 집계
  - WHY: 같은 모듈을 import문 여러 줄로 나눠 쓰면 파일 단위가 아니라 import문 단위로 세어 수치가 부풀려짐(실측: `firebase.ts` 7→8)
  - COST: "몇 번 import했는지"라는 다중성 정보는 사라짐 — 지금 요구사항(연결 여부만 판정)엔 dedupe가 맞음
  - EXIT: 다중성이 필요해지면 edges를 (src,dst,count)로 바꾸면 됨, fan_in 계산 로직은 불변
- **D13** ([`cognition/two_tier_scan.py`](./cognition/two_tier_scan.py)) — 인지 블록을 JS/TS 외 Python/Java/C/C++로 확장
  - WHY: `idiom_filter.py`의 `LANG_EXT_MAP`은 이미 다국어를 가정하는데 인지 블록의 `SRC_EXTS`는 JS/TS뿐이라 다른 언어 repo를 스캔하면 파일이 통째로 누락되는 불일치가 있었음
  - COST: 언어별 import 정규식이 늘어남. Swift는 로컬 파일간 import가 없어(모듈 단위 가시성) 구조 스캔 대상에서 제외(문서화된 한계)
  - EXIT: 새 언어는 `EXT_GROUPS`에 확장자 + `extract_targets_for_file`에 분기만 추가
- **D14** ([`judgment/tier_b_hook.py`](./judgment/tier_b_hook.py)) — Tier B 오탐 억제를 인지 블록이 아니라 판단 블록에 위치
  - WHY: "이 매치가 진짜 위험인지 오탐인지"는 사실 추출이 아니라 신뢰도 판단 — `idiom_filter.py`와 동일 성격이라 같은 계층(판단)에 둬야 3블록 경계가 지켜짐. "인지 블록용 훅"으로 요청받았지만 구현하며 정확한 위치를 재확인함
  - COST: 인지 블록은 오탐 여부를 전혀 모른 채 raw match를 그대로 내보내야 함(의도된 설계)
  - EXIT: 분리가 과했다고 판명되면 파일을 `cognition/`으로 옮기고 import 경로만 변경(로직은 이동 무관)
- **D15** ([`judgment/idiom_filter.py`](./judgment/idiom_filter.py)) — `.h`의 C/C++ 모호성을 파일 내용 스니핑으로 개선(repo_root 있을 때만)
  - WHY: 확장자만으론 확정 불가 — `class`/`namespace`/`template<`/`std::` 같은 C++ 전용 토큰 유무로 재판정하면 오분류가 줄어듦
  - COST: 완벽하지 않음(이 토큰을 안 쓰는 C++ 헤더는 여전히 c로 오판정), repo_root 없으면 기존처럼 c 고정
  - EXIT: 부족하면 실제 컴파일러/AST 판별(예: clang 파싱 성공 여부)로 교체
- **D16** ([`judgment/score_findings.py`](./judgment/score_findings.py)) — hub 동점 시 fan-out 낮은(sink에 가까운) 쪽으로 tie-break
  - WHY: D12 수정의 부작용으로 App.tsx와 firebase.ts의 fan_in이 7로 동점이 되는 회귀를 실측으로 발견 — fan_in만으론 "서비스 허브"(fan_out 낮음)와 "컨테이너"(fan_out 높음)를 구분 못함
  - COST: fan_out도 계산해야 해서 `find_hub` 시그니처가 `edges`를 추가로 받게 변경됨
  - EXIT: 이 휴리스틱도 틀리면 파일명 패턴 화이트리스트(`*service*`, `*db*` 등)로 대체 검토
- **D17** ([`cognition/two_tier_scan.py`](./cognition/two_tier_scan.py)) — `eval(` 트리거에서 메서드 호출(`obj.eval(`) 제외
  - WHY: RunPod_Deploy_Agent 실측 — `model.eval()`(PyTorch 표준 API, 안전)이 위험한 전역 `eval()`로 오탐지됨. `(?<!\.)` 부정 후방탐색으로 배제하면 진짜 위험한 전역 `eval(...)`은 그대로 잡힘
  - COST: 극히 드물게 변수명이 우연히 `eval`인 메서드 호출도 같이 배제될 수 있음
  - EXIT: 유사 오탐이 더 쌓이면 `tier_b_hook.py` 재귀 억제 루프로 이관
- **D18** ([`cognition/two_tier_scan.py`](./cognition/two_tier_scan.py)) — `@/` 경로 별칭 import도 로컬 import로 인식
  - WHY: jxxnixx/LMS 실측 — Vite/TS 관례(`"@": "./src"`)로 만든 `@/api/...` import가 99건인데 상대경로(`.`)만 인식해 그래프가 사실상 텅 빔
  - COST: alias 접두어를 tsconfig/vite.config에서 동적으로 읽지 않고 `'@/'` 하드코딩 — 다른 접두어(`~/` 등) 프로젝트는 여전히 놓침
  - EXIT: `LOCAL_IMPORT_PREFIXES`에 접두어 추가, 또는 tsconfig `paths` 파싱으로 교체
- **D19** ([`judgment/score_findings.py`](./judgment/score_findings.py)) — 고립 판정 범위를 "전체 파일"에서 "entry→root 직계 형제"로 제한
  - WHY: jxxnixx/LMS 실측 — 51개 중 30개가 "최우선" 고립으로 오탐지됨. "형제 컴포넌트 전부가 허브를 써야 한다"는 가정이 관심사가 여러 개인 대형 코드베이스에서는 깨짐
  - COST: 형제 그룹 바깥의 진짜 고립 파일은 이 규칙으로 못 잡음(의도적 범위 축소)
  - EXIT: 형제 그룹을 root 직계가 아니라 2단계까지 확장하려면 `find_routed_peers`의 BFS 깊이만 늘리면 됨
- **D20** ([`judgment/score_findings.py`](./judgment/score_findings.py)) — `eval_or_dangerous_html` 트리거를 finding화하는 규칙 추가
  - WHY: jxxnixx/LMS 실측 — 인지 블록이 `dangerouslySetInnerHTML`을 정확히 잡았는데 판단 블록에 대응 규칙이 없어 조용히 버려지고 있었음(순수 누락 버그)
  - COST: 없음
  - EXIT: 트리거 추가와 finding화 규칙 추가가 분리돼 있어 또 누락될 수 있음 — 트리거→템플릿 딕셔너리로 리팩터링하면 근본 해소
- **D21** ([`judgment/score_findings.py`](./judgment/score_findings.py)) — React Query "리소스별 커스텀 훅" 컨벤션을 관용 패턴 후보로 추가 인식
  - WHY: jxxnixx/LMS 실측 — `useBooksQueries.ts`가 확산 후보인데 `@tanstack/react-query` 공식 문서 권장 패턴이라 createContext만 보던 기존 탐지로는 놓쳤음
  - COST: 다른 라이브러리 컨벤션(Redux Toolkit slice 등)은 여전히 미탐지
  - EXIT: 컨벤션이 늘어나면 `PATTERN_DETECTORS` 딕셔너리로 리팩터링
- **D22** ([`pipeline/run_pipeline.py`](./pipeline/run_pipeline.py)) — 오케스트레이터는 "무엇이 관용패턴/오탐인지" 스스로 추론하지 않음, `injections.json`을 사람이 채움
  - WHY: jxxnixx/LMS 실측 — `dangerouslySetInnerHTML`은 실제로 진짜 위험이라 자동으로 "다 오탐 처리"했다면 판단 블록 신뢰도 자체가 오염됐을 것
  - COST: 완전 무인 실행이 안 됨 — 사람이 먼저 코드를 읽고 `injections.json`을 채워야 함
  - EXIT: 자동 추론이 필요해지면 LLM 판단 단계를 추가하되, 생성된 각 injection에 `note`를 강제해 감사 가능성 유지
- **D23** ([`pipeline/ledger.py`](./pipeline/ledger.py)) — 파이프라인 실행 결과를 append-only 원장(`ledger.jsonl`)에 영구 저장
  - WHY: "지금까지 시도한 방법론들을 비교해서 보여달라"는 질문에 답할 축적된 데이터가 실측 확인 결과 없었음 — 매 주입을 한 줄씩 append하면 나중에 언제든 집계 가능
  - COST: 같은 methodology를 여러 번 실행하면 로그가 무한정 늘어남, retention 정책 없음
  - EXIT: 파일이 너무 커지면 SQLite로 교체(인터페이스는 `append_entry`/`load_entries` 그대로 유지)
- **D24** ([`pipeline/compare_methodologies.py`](./pipeline/compare_methodologies.py)) — 비교표는 캐시 없이 ledger.jsonl을 매번 재집계해서 생성
  - WHY: 원장 자체가 이미 append-only 진실 소스라 재계산 비용이 무시할 만큼 작음 — 집계 로직과 저장 로직 분리
  - COST: 원장이 아주 커지면(수만 줄) 매번 전체를 읽어 느려질 수 있음
  - EXIT: 느려지면 groupby 결과를 캐시 파일로 저장하고 원장 변경 시에만 재계산
- **D25** ([`pipeline/ledger.py`](./pipeline/ledger.py)) — repo 식별자를 원본 경로가 아니라 정규화된 이름(`normalize_repo`)으로 집계
  - WHY: 실측 발견 — 같은 저장소를 실행 위치에 따라 다른 상대경로로 기록해 "적용 repo 수" 집계가 부풀려짐(1이어야 할 게 2로)
  - COST: 서로 다른 두 repo가 우연히 같은 마지막 디렉터리명을 쓰면 하나로 합쳐질 위험(드묾)
  - EXIT: 정확한 식별이 필요해지면 `git remote get-url origin`을 저장하는 방식으로 교체
- **D26** (`cognition/two_tier_scan.py`의 `auth_info_leak_via_thrown_error` 트리거) — Shadowbroker의 `meshIdentity.ts` 오탐을 tier_b_hook으로 억제하지 않고 미수정으로 남김
  - WHY: 매치 텍스트("email")가 너무 일반적 키워드라 억제하면 다른 파일의 진짜 위험까지 같이 가려질 위험이 큼 — 이 트리거 자체가 "3개 키워드 co-occurrence, 근접성 무시" 설계라 대형 파일에서 정밀도가 떨어지는 구조적 문제
  - COST: 당장 이 오탐은 그대로 노출됨(Important로 잘못 분류된 채)
  - EXIT: `matched_text` 주변 N줄 이내에 3개 키워드가 모두 있는지 근접성 검사를 추가하는 코드 수정이 근본 해법(hook 억제로 땜질하면 안 되는 사례)
- **D27** ([`judgment/subrubric.py`](./judgment/subrubric.py)) — 판단 블록 3축(설계의도/질문가치/위험도)에 서브루브릭 4항목씩 도입
  - WHY: EVALUATION.md가 스스로 인정한 "LLM-as-Judge 정량화 열위"를 메우는 지점 — 규칙기반은 유지하되(D3) 판정 근거를 한 줄 문자열에서 감사 가능한 4항목 breakdown으로 세분화. 서브축은 기존 인지 블록 출력 필드(fan_in/pattern_key/matched_text/trigger)만 재사용해 새 스캔 로직 추가 없이 구현
  - COST: finding당 채점 항목이 3개→12개로 늘어 evidence 조립 코드가 finding 종류별로 늘어남(공용 함수 하나로 못 뭉침). 컷오프(9/5)가 실측 데이터 없이 임의값
  - EXIT: 과하면 축당 서브항목 2개로 축소. `THRESHOLDS`만 바꾸면 판단 블록 전체 재보정 가능
- **D28** ([`judgment/subrubric.py`](./judgment/subrubric.py)) — 서브축 총점(0~12) → 기존 상/중/하 문자열로 재매핑해 하위호환 유지
  - WHY: `idiom_filter.py`의 `DOWNGRADE_MAP`이 정확히 "상"/"중"/"하" 키만 인식 — 서브루브릭 도입이 기존 판단 블록 소비자를 깨면 안 됨
  - COST: 9/5 컷오프가 임의적, 서브축 breakdown이라는 풍부한 정보를 최종적으로는 3단계로 다시 뭉갬
  - EXIT: 컷오프를 `THRESHOLDS` 상수로 분리해뒀으니 데이터가 쌓인 뒤 자동 재보정 가능. breakdown 자체는 `finding["subrubric"]`에 그대로 남아있어 필요하면 3단계 대신 원점수를 직접 소비 가능
- **D29** ([`judgment/score_findings.py`](./judgment/score_findings.py)) — risk 축의 `spread_count`는 Tier B(진짜 보안/신뢰성 위험) finding에서만 0이 아닌 값을 쓰고, cognition-isolation/architecture-diffusion/repeated-pattern은 항상 0으로 고정
  - WHY: 초기 구현에서 diffusion/repeated-pattern에 fan_in·반복 파일 수를 그대로 risk spread_count로 재사용했더니 architecture-diffusion:App.tsx의 risk가 기존 "하"에서 "중"으로 부풀려지는 회귀가 실측(Study-Match- 재실행)으로 발견됨 — "많이 참조된다/반복된다"는 구조적 특성이지 보안 위험의 확산이 아님을 구분해야 했음
  - COST: cognition-isolation/diffusion/repeated-pattern의 risk 서브축 4개 중 spread_scope 1개는 항상 0으로 고정되어 사실상 3개 서브축만 유효 활용됨
  - EXIT: 구조적 확산과 위험 확산을 같은 축에서 다르게 가중치를 주고 싶어지면 risk 축을 5서브축으로 늘리고 별도 항목(structural_spread) 추가
- **D30** (전체 검증) — Study-Match-(4 findings) + jxxnixx/LMS(8 findings, `run_pipeline.py` 전체 재실행)로 회귀 확인
  - WHY: risk 축은 사용자 대면 가장 민감한 판정이라 기존 값과 100% 일치하는지가 최소 안전선 — 실제로 전 findings에서 risk만은 기존 상/중/하와 정확히 일치함을 확인(D29로 spread_count를 risk-only로 제한한 결과)
  - COST: question_value 축은 4건 중 1건(`tier-b-risk:firebase.ts`, 중→상)이 재계산으로 바뀜 — 서브축 근거(mitigation_present/scenario_specific 등)가 원래의 단일 추정값보다 두꺼워졌기 때문이며, 되돌릴 수 없는 의도된 변화. design_intent 축은 전 findings에서 자유서술 텍스트→정량값으로 형식 자체가 바뀜(비교 대상 아님)
  - EXIT: question_value 재계산값이 실제 팀 판단과 어긋난다고 판명되면 `score_question_value`의 개별 evidence(tradeoff_signal 등)만 조정 — 축 구조 자체를 되돌릴 필요 없음
- **D31** ([`judgment/idiom_filter.py`](./judgment/idiom_filter.py)) — idiom_filter가 question_value를 덮어쓸 때 subrubric 감사 트레일도 함께 갱신
  - WHY: 실측 발견 — `architecture-diffusion:App.tsx`에서 subrubric 원점수(total=9→"상")와 idiom_filter가 최종적으로 덮어쓴 값("하")이 finding 안에 불일치 상태로 공존했음. POC_TEST.md에서 재구성한 B안 자체 비평의 "Signals After Filter가 Downgrade Log와 안 맞는다"는 지적과 정확히 같은 클래스의 결함
  - COST: idiom_filter가 subrubric.py 내부 스키마(`sub`/`total` 키)를 알아야 해서 두 모듈 결합이 약간 늘어남
  - EXIT: subrubric.py가 스키마를 바꾸면 이 덮어쓰기 블록도 같이 바꿔야 함 — 공용 타입으로 뽑으면 결합도 낮출 수 있음
- **D32** ([`feedback/reflection_hook.py`](./feedback/reflection_hook.py)) — Reflection 판정을 idiom_hook.py와 동일한 재귀 확인 패턴으로 가드
  - WHY: POC_TEST.md 문제4("Reflection이 너무 쉽게 확정된다") 해소 — 자기오류인식/이유설명/새판단/개선안 4개 서브신호 각각을 정규식 패턴으로 잡되, 그 패턴이 confirmed 상태가 되기 전까지는 신뢰하지 않음(idiom_hook과 동일한 3회 확인 원칙)
  - COST: confirmed 패턴이 없으면 진짜 reflection도 항상 False로 나옴 — 매우 보수적
  - EXIT: sub_signal별 `promotion_threshold`를 개별 조정 가능(파일이 이미 분리돼 있음)
- **D33** ([`feedback/reflection_signal.py`](./feedback/reflection_signal.py)) — reflection_present는 4개 서브신호 전부 매치(AND)돼야 True
  - WHY: ROAF-B 정의(자기오류인식→이유설명→새판단→개선안)를 그대로 코드화 — 하나라도 없으면 "아직 Knowledge 수준"
  - COST: 실측 결과 **B안 문서 자체가 제시한 모범 Reflection 예시**("아 맞네요. 제가 브라우저를 너무 신뢰했습니다. 운영환경이라면 백엔드에서 제한해야 합니다")조차 3/4만 매치되고 reason_explanation(명시적 "그래서/왜냐하면" 연결어)이 없어 최종 False로 판정됨 — 단일 발화 기준 AND-4가 지나치게 엄격할 수 있음을 시사
  - EXIT: 너무 엄격하면 OR-3(4개 중 3개 이상)으로 완화하거나, 여러 턴을 합쳐서 검사하도록 `evaluate_reflection`에 다중 턴 입력 지원 추가(POC_TEST.md 문제5의 Aggregation과 같은 방향)
- **D34** ([`feedback/reflection_signal.py`](./feedback/reflection_signal.py)) — AND-4를 "self_error_recognition 필수 + 나머지 3개 중 2개 이상"으로 완화
  - WHY: D33 EXIT에서 제안한 순수 OR-3(4개 중 아무 3개)을 그대로 시도하기 전에 실측 프로브("그래서 백엔드에서 제한해야 합니다." — 자기오류인식 없이 이유·새판단·개선안 3개만 있는 문장)를 먼저 넣어봤더니 optional_matches=3으로 순수 OR-3 기준을 통과해버렸다 — 애초에 틀렸다는 인정이 없으면 "원래부터 맞았던 답변"도 reflection으로 오판하게 됨. self_error_recognition은 Reflection의 정의(자기 수정) 자체를 성립시키는 조건이라 OR로 완화하면 안 되고 항상 필수로 둬야 한다는 걸 실측으로 확인
  - COST: self_error_recognition confirmed 패턴이 아직 1개("너무 신뢰했")뿐이라 다른 오류인식 표현("아차", "잘못 봤네요" 등)을 쓰면 여전히 과소탐지됨 — 재현율은 낮은 채로 정밀도만 높인 상태
  - EXIT: 실제 학생 답변이 쌓이면 `MIN_OPTIONAL_MATCHES` 상수만 조정하거나 `REQUIRED_SUB_SIGNALS`에 다른 서브신호 추가로 재보정 가능
- **D35** ([`judgment/subrubric.py`](./judgment/subrubric.py)) — 4서브축 분해를 웹서치로 확인한 문헌 근거에 맞춰 재검토·일부 교체
  - WHY: POC_TEST.md D31 검증 과정의 "Signal→Construct 매핑 외부 검증 없음" 지적에 대한 응답. `design_intent.location_signal`(파일명 힌트)은 근거 문헌이 없어 가장 약한 서브축이었음 — Self-Admitted Technical Debt 탐지 연구(Potdar & Shihab, ICSME 2014; Maldonado & Shihab 2015)가 "의도성의 근거 = 코드 코멘트의 명시적 설명/시인 언어"임을 확립해 `rationale_signal()`(파일 내용에서 rationale/debt 인디케이터 스캔)로 교체. `risk` 축은 CVSS(Exploitability·Impact 지표 분리)와 FindBugs/SpotBugs(confidence는 severity와 별개 축) 문헌이 공통으로 "신뢰도와 심각도를 단순 합산하지 말라"고 하는데 기존 구현이 이를 위반하고 있어, 신뢰도가 심각도 총점을 게이팅하는 공식으로 변경. `question_value`의 4축(트레이드오프/repo_specificity/idiom_contamination/ladder_richness)은 검토 결과 이미 근거가 있어(고전 검사이론 변별도 지수, Haladyna item-writing guideline, CAT의 item exposure control 문헌, Bloom's Taxonomy) 재설계 없이 인용만 보강. 상세 인용: [`SUBRUBRIC_DRAFT.md`](./judgment/SUBRUBRIC_DRAFT.md#문헌-근거-d35)
  - COST: `rationale_signal()`이 repo_root 파일 I/O를 요구해 cognition-isolation/tier-b-risk finding에도 파일 읽기가 추가됨(이전엔 diffusion만 읽었음). risk 축은 여전히 최종 3단계(상/중/하) 하나로 뭉개져서 신뢰도·심각도 두 construct를 최종 사용자에게 완전히 분리해 보여주진 못함(subrubric.sub에는 남음). rationale/debt 인디케이터 정규식은 영어/한국어 일부만 커버
  - EXIT: 인디케이터 정규식 오탐/누락이 쌓이면 idiom_hook류 재귀 학습 루프로 교체 검토. risk를 confidence/severity 두 필드로 완전 분리하려면 `apply_subrubric()` 반환 스키마만 바꾸면 됨(score_risk 내부 로직은 이미 분리돼 있음). **문헌이 이 도메인에 실제로 전이되는지는 여전히 미검증** — 다음 단계는 사람 채점과의 직접 비교
- **D36** ([`pipeline/evidence_bridge.py`](./pipeline/evidence_bridge.py)) — D안(B안+C안 결합) 최초 구현: C안 finding을 B안의 "Repository Evidence" 형식으로 자동 변환
  - WHY: B안 프롬프트 Step1은 사람이 직접 Repository를 분석해 근거 문단을 써야 했다. C안(cognition+judgment)이 이미 그 분석을 코드로 자동화했으므로 그 출력을 그대로 재사용
  - COST: 자동 생성 질문이 finding 단위로 끊어져 있어 B안 원본처럼 여러 파일을 엮은 서사형 질문보다 자연스러움이 떨어짐(LMS 실행 시 cognition-isolation 6건이 전부 동일한 템플릿 질문을 받음)
  - EXIT: 품질 부족 시 자동 evidence를 초안으로만 쓰고 사람이 다듬는 반자동 모드로 전환
- **D37** (D안 LMS 시뮬레이션, `examples/lms/d_plan/`) — Codex(별도 모델)로 독립 생성한 가상 답변으로 Reflection 판정을 검증, 압도적 예시 1건만으로는 패턴 승격하지 않음
  - WHY: 직접 작성한 시뮬레이션 답변은 "패턴에 맞춰 쓴 것 아니냐"는 의심에서 자유롭지 않음 — 실제 코드 컨텍스트만 주고 별도 모델(codex:codex-rescue)이 생성한 답변으로 검증해야 재현율 문제가 진짜인지 확인 가능. 결과: 정성적으로 매우 우수한 reflection(자기오류인식+이유+새판단+구체적 개선안 전부 포함)인데도 confirmed 패턴과 문구가 안 맞아 0/4로 완전히 놓침 — D34가 예상한 것보다 재현율 문제가 훨씬 심각함이 확정됨
  - COST: 이 발견에도 불구, D32의 "3회 확인 후 승격" 원칙을 지켜 새 후보 패턴 3개(`안일하게 생각`/`지금 보니`/`sanitize|DOMPurify`)는 confirmations=1로만 기록하고 승격하지 않음 — 당장은 재현율이 그대로 낮은 채로 남음
  - EXIT: 위 3개 후보에 2건씩 더 재확인이 쌓이면 자동 승격됨(`reflection_hook.py update <sub_signal>`), 재현율이 그때 다시 측정 가능
- **D38** (`examples/lms/d_plan/codex_verification_full.md`) — LMS 인터뷰 가능 finding 7건 전부 Codex 병렬 생성으로 검증, 방향 전환 발견
  - WHY: 1건(Bookshelf.jsx)만으로는 "재현율 문제인지 우연인지" 판단 근거가 약했음. 나머지 6건(cognition-isolation)까지 전부 Codex 독립 생성으로 검증한 결과 **7건 전부 reflection_present=False**였지만 원인이 다름: 1건은 진짜 재현율 실패(양질의 오류인정+개선안이 패턴 불일치로 누락), 6건은 "가상 학생"이 전부 GenreContext 미사용에 대한 타당한 설계 근거를 제시해 애초에 reflection이 필요한 상황이 아니었을 가능성이 높음
  - COST: 이 결과가 시사하는 우선순위 전환을 아직 실행하지 않음 — Reflection 패턴 재현율 개선보다 D19의 `cognition-isolation` 규칙 자체(다중 concern 코드베이스 과탐지)를 먼저 재검토해야 할 수 있다는 결론만 기록하고 코드 변경은 안 함
  - EXIT: `cognition-isolation` 규칙에 "합리적 근거 제시 시 자동 하향" 재귀 hook을 추가하는 안(idiom_hook/tier_b_hook과 동일 패턴)이 다음 후보 — 다만 이번엔 코드 신호가 아니라 자연어 답변 품질로 판단해야 해서 설계가 다름
- **D39** ([`judgment/isolation_hook.py`](./judgment/isolation_hook.py)) — cognition-isolation용 재귀 hook은 "정규식 하나=패턴 하나"가 아니라 "카테고리 하나=동의어 alternation"으로 설계
  - WHY: idiom_hook처럼 정규식 하나로 패턴을 잡으면 reflection_hook이 이미 실증한 재현율 붕괴가 그대로 재발함(D37 — Codex의 좋은 답변도 정규식 문구 불일치로 놓침). 자연어 정당화는 표현이 매번 달라 4개 카테고리(role_separation/perf_optimization/alt_storage_or_scope/domain_irrelevance)를 미리 정의하고 카테고리당 넓은 alternation 패턴을 축적하는 쪽으로 설계
  - COST: 카테고리 경계를 사람이 미리 정해야 함 — 코드처럼 유한한 문법이 아니라서 새로운 정당화 유형이 나오면 카테고리 자체를 추가해야 함
  - EXIT: 카테고리 부족 시 "미분류" 비율로 감지 가능, 그때 카테고리 추가 또는 LLM 자유분류+매핑으로 전환
- **D40** ([`judgment/isolation_classifier.py`](./judgment/isolation_classifier.py)) — 4개 카테고리 중 confirmed 패턴이 하나라도 매치되면 justified=True
  - WHY: 명백한 실수 정정(reflection)과 달리 "타당한 설계 근거"는 여러 이유 중 하나만 맞아도 충분 — idiom_filter의 "confirmed 패턴 1개 매치=하향"과 같은 OR 논리
  - COST: 한 답변이 여러 카테고리에 동시 매치될 때(Header.jsx 실측: perf_optimization+domain_irrelevance) 어느 게 "진짜 이유"인지 구분 못함
  - EXIT: 카테고리별 강도(가중치)가 필요해지면 matched_categories 개수/조합으로 세분화
- **D41** (`judgment/isolation_categories/*/patterns.json`) — role_separation/perf_optimization/domain_irrelevance의 promotion_threshold를 3→2로 낮춤
  - WHY: 실측 — LMS 6개 답변 중 3개 카테고리가 정확히 confirmations=2에서 멈춰 threshold=3 미달. idiom_hook의 threshold=3은 "같은 리뷰어가 같은 정규식을 3번 확인"하는 맥락인데, 여기는 "서로 다른 파일의 서로 다른 학생이 독립적으로 같은 카테고리에 수렴"하는 맥락이라 신뢰 조건이 다름 — 독립 출처 2곳의 수렴 자체가 이미 유의미한 신호로 판단
  - COST: 이 조정이 "6건의 우연한 분포(2개씩 짝지어짐)에 맞춰 정당화됐다"는 의심에서 자유롭지 않음 — 더 큰 표본에서 threshold=2가 여전히 적절한지 미검증. `alt_storage_or_scope`는 관측 1건뿐이라 threshold를 낮춰도 승격 안 됨(의도된 보수성 유지 확인됨)
  - EXIT: 다른 repo에서 재검증해 오탐(잘못 justified=True 판정)이 나오면 threshold를 다시 3으로 올리거나 카테고리별로 다르게 세분화
- **D42** ([`TEAM_POC_SUMMARY.md`](./TEAM_POC_SUMMARY.md)) — 팀 발표용으로 4명의 팀원 POC 요약과 같은 포맷으로 이 repo의 결과를 정리
  - WHY: 팀 발표 자료가 "팀원별 POC 테스트 요약"(김만서/박진용/손진원/박종호) 형식으로 통일돼 있어, 이 repo의 결과도 같은 포맷(레포/결정포인트→방법론 비교표→핵심 발견→팀 공통 병목과의 수렴→다음 과제)으로 맞춰야 다른 팀원 발표와 나란히 비교 가능. 다른 3명이 "대화형 인터뷰 프롬프트끼리" 비교했다면 이쪽은 "코드만으로 어디까지 가고 어디서부터 대화가 필요한가"를 실측했다는 점을 명시해 포지셔닝을 분명히 함
  - COST: 팀원들 문서는 전부 실제 LLM API로 돌린 대화 시뮬레이션인데 이쪽 C/D안은 API 없이 코드만으로 돈 결과라 "대화형 판별력"(강/애매/약 답변 구분, 박진용 방식) 자체는 비교표에 못 넣음 — E안(Reflection)만 유일하게 실제 자연어 답변(Codex 생성)으로 검증됨
  - EXIT: API 키가 생기면 D안의 evidence_bridge 질문을 실제 멀티턴 세션에 연결해 박진용의 강/애매/약 3세트 프레임으로 재검증 — 그때 이 문서의 "대화 없이 어디까지 가능한가" 결론이 진짜 맞는지 확정 가능
- **D43** (~~`PRESENTATION_SCRIPT.md`~~, 폐기됨 — D45 참조) — TEAM_POC_SUMMARY.md(보고서)와 별도로 실제 구술 발표문을 작성했던 시도
  - WHY(당시): 팀 Notion 문서의 "우리가 다 우월하다고 말하면 안 된다"는 발표 원칙을 반영한 구어체 버전이 별도로 필요하다고 판단
  - COST(당시): 판단 블록만 "성공"으로 명시하고 인지·피드백은 한계를 그대로 노출
  - EXIT: **실행됨** — 사용자가 "TEAM_POC_SUMMARY만이 원했던 형태"라고 명시적으로 정정, D45로 삭제
- **D44** (`TEAM_POC_SUMMARY.md` 구조 보강) — 실행한 3명(김만서/박진용/손진원)의 공통 구조 요소 중 빠졌던 3가지를 추가
  - WHY: 사용자 요청으로 팀 Notion 문서 헤더 구조를 직접 grep해 대조한 결과, 실행한 3명 전부가 (1) 실제 프롬프트/질문 원문 verbatim (2) 실제 답변 verbatim (3) 번호형 비평 또는 "제 의견" 마무리 중 최소 2개를 포함하는데 기존 `TEAM_POC_SUMMARY.md`는 요약표만 있고 원문 인용이 빠져 있었음. Bookshelf.jsx 질문·Codex 답변·reflection_signal.py 실행 결과를 verbatim으로 삽입, 박진용 형식의 ✅/❌ 장단점 표를 A~E안마다 추가, 김만서 형식의 "제 의견" 3개 추가
  - COST: 문서 길이가 길어짐(179줄) — 감수하기로 함, 발표용 별도 압축본은 D45로 폐기
  - EXIT: 분량이 문제되면 발췌해서 쓰되 새 문서를 또 만들지 않고 이 파일 안에서 섹션을 골라 쓰는 쪽으로
- **D45** (`PRESENTATION_SCRIPT.md` 삭제) — 사용자가 "TEAM_POC_SUMMARY만이 원했던 형태"라고 명시적으로 정정, 별도 발표 스크립트 폐기
  - WHY: 보고서(TEAM_POC_SUMMARY.md)와 구술 발표문을 분리하는 게 팀 문서 관습에 없었고, 사용자는 애초에 팀원들과 같은 "보고서 하나" 형태만 원함 — 제가 임의로 산출물을 하나 더 만든 것
  - COST: 없음 — git 이력에 남아있어 필요하면 `git show 6381bfe:PRESENTATION_SCRIPT.md`로 복구 가능
  - EXIT: 향후 발표 자료가 별도로 필요해지면, 새 파일을 만들기 전에 먼저 사용자에게 "보고서 하나로 충분한지" 확인부터 할 것
- **D46** (`TEAM_POC_SUMMARY.md` — "방법론 프롬프트" 섹션 추가) — 박종호 형식(질문 생성/채점 프롬프트 분리)에 맞춰 실제 프롬프트 원문을 추가하되, "채점 프롬프트가 없다"는 사실을 숨기지 않음
  - WHY: 사용자가 "POC 테스트를 위한 방법론 프롬프트 보여줘"라고 요청 — `DEPTH_LADDER_OPENING`(질문 생성 템플릿)과 Codex 역할극 프롬프트 골격(답변 생성)은 실제 코드/호출 이력에서 그대로 발췌 가능했음. 다만 채점은 A/B안과 달리 LLM 프롬프트가 아니라 `subrubric.py`의 규칙식이라, "채점 프롬프트"란 게 애초에 존재하지 않는다는 점을 섹션 서두에 명시해 없는 걸 지어내지 않음
  - COST: 다른 팀원 문서와 완전히 같은 모양(프롬프트 3종 세트)을 기대하면 어긋남 — "우리는 채점을 프롬프트가 아니라 코드로 한다"는 게 오히려 C안의 핵심 차별점이라는 걸 이 섹션에서 정면으로 설명해야 했음
  - EXIT: LLM-as-Judge 축(A안류)을 C안에 실제로 추가하게 되면 그때 진짜 채점 프롬프트를 이 섹션에 채워 넣을 것
- **D47** (`TEAM_POC_SUMMARY.md` — 18축 루브릭 표 추가) — 김만서의 원본 18행 비교표(Simple Prompt/A안/B안)를 raw 파일에서 직접 확인 후 C/D/E안 열을 추가
  - WHY: 사용자가 18개 세로축(목적~최종 산출물)을 지정하며 A~E안 표를 요청 — 원본 문서를 다시 열어(2086~2105행) A안/B안 값을 그대로 옮기고, C/D/E안은 이번 세션 실측 데이터로만 채워 새 주장을 지어내지 않음. "Repository 분석"처럼 답이 뻔한 행도 실측 근거(정적분석 vs 답변 텍스트만 봄)를 달아 근거 없이 ○/✗만 찍지 않음
  - COST: C/D/E안은 대화가 없어 "질문 생성/Follow-up/질문 깊이/Counterfactual/교육 활용성" 5개 행에서 전부 "없음/해당없음/낮음"으로 채워짐 — 표만 보면 열위로 보일 수 있으나, "설명 가능성/재현성"에서는 반대로 A/B안을 앞선다는 트레이드오프를 표 아래 문단에 명시해 균형을 맞춤
  - EXIT: 실제 대화형 검증(D42/D46 EXIT)이 이뤄지면 "질문 생성/Follow-up/질문 깊이" 행이 D안부터 갱신 가능
- **D48** ([`pipeline/followup_generator.py`](./pipeline/followup_generator.py)) — D안에 적응형 Follow-up 질문 생성을 실제로 구현, D47 표의 "미구현" 셀을 진짜로 채움
  - WHY: 사용자가 팀 Notion 비교표(질문 생성/Follow-up 질문 칸, 모든 팀원이 실제 값을 채워 넣음)를 보여주며 "우리 진행 방식을 저기에 맞춰야지, 구현을 잘못했다"고 명확히 정정 — D안이 단발 질문만 내고 Follow-up을 "없음/미구현"으로 방치하는 건 팀 표준에 맞지 않음. 팀 자체 문서(`코드이해도_평가_질문및채점기준.md` §3 "적응형 후속 질문 전략" 표: 모호/추상적→구체화, 대안 미언급→대안탐색, 근거 얕음→변형질문, 오개념감지→소크라테스식 반례, 충분히 깊음→다음 축)를 그대로 규칙 트리로 옮기고, "1차 답변 상태" 판정은 새 LLM 호출 없이 기존 `isolation_classifier`/`reflection_signal`을 재사용. Bookshelf.jsx(tier-b-risk) 사례에서 Codex로 실제 2턴까지 완주해 검증 — 1턴("안일하게 생각했다"에서 멈춤)보다 2턴("script 삽입→쿠키탈취→외부전송"까지 구체화)이 실제로 더 깊었음을 실측 확인. cognition-isolation 3개 사례(Auth/Header/authToken)도 카테고리 매치 개수에 따라 서로 다른 후속 질문으로 정확히 분기되는 것 확인
  - COST: A/B안처럼 "매번 새로 생성되는 LLM 적응형 질문"이 아니라 팀 §3 표의 5개 방향 중 하나를 **미리 정의된 규칙(신호 분류 결과)으로 선택**하는 구조 — 문구는 고정 템플릿이고 분기만 적응형. "생성형 적응형"이 아니라 "규칙 기반 적응형"이라는 한계를 문서에 명시
  - EXIT: API가 생기면 같은 분기 로직(5개 방향) 위에서 각 분기의 질문 문구만 Codex/Claude가 매번 새로 생성하도록 교체 가능 — `_risk_type_followup`/`_isolation_followup`의 return 문자열만 LLM 호출로 대체하면 됨, 분기 트리 자체는 재사용
- **D49** (`judgment/isolation_categories/domain_irrelevance/patterns.json` 정규식 버그 수정) — `딱히.*필요`의 그리디 와일드카드가 무관한 문맥까지 160자 건너뛰어 오매칭
  - WHY: escalation 데모용으로 authToken.js를 재검증하다 실측으로 발견 — 텍스트 초반의 "딱히 큰 고민 없이"와 후반의 "리렌더링될 필요" 사이 160자를 `.*`가 그대로 삼켜 domain_irrelevance가 완전히 무관한 문장에 오매칭됨. `.{0,15}`로 범위를 제한
  - COST: 원래 이 패턴을 confirmed시킨 두 출처(Auth.jsx/Header.jsx)에서 회귀 재확인 필요 — 둘 다 재확인 완료(매치 유지)
  - EXIT: 카테고리 정규식에 그리디 와일드카드(`.*`)를 쓸 때마다 이 함정이 반복될 수 있음 — 새 카테고리/패턴 추가 시 `.*` 대신 `.{0,N}`을 기본으로 쓰는 컨벤션화 검토
- **D50** ([`pipeline/escalation_hook.py`](./pipeline/escalation_hook.py)) — keyword hook 검출 실패 시 Socratic+Depth Ladder로 escalate하고, escalation 성공 판정을 hook에 재귀적으로 되먹이는 루프를 구현
  - WHY: 사용자 제안("keyword hook 검출 실패하면 소크라틱+DepthLadder로 보내고 hook을 업데이트하는 재귀 규칙") — D37/D39~41에서 내가 수작업으로 하던 "새 데이터→hook 후보 등록"을 자동화. `followup_generator.py`(D48)가 escalation 질문 생성까지는 했지만 결과를 hook에 되먹이는 마지막 연결이 없었음
  - COST: escalation "성공" 여부(judge) 자체는 결정론적 규칙으로 못 함 — 반드시 이 모듈 밖(Codex 등 실제 LLM)에서 판정을 받아와야 하는 반자동 루프. 완전 자동 폐루프가 아님
  - EXIT: judge를 규칙으로 대체하면(예: evaluate_reflection 재적용) escalation의 의미(hook이 아직 모르는 신호를 더 깊이 파고들어야만 본다는 것) 자체가 사라짐 — judge는 hook과 독립적이어야 한다는 제약을 지켜야 함
- **D51** (`isolation_hook.py`/`reflection_hook.py` `recursive_update()` 재설계) — 같은 출처 반복 제출 방지(dedup) + 양방향 승격/강등
  - WHY: escalation_hook.py를 Bookshelf.jsx로 실제 테스트하다가 실측으로 발견 — 기존 `votes[key] += 1`은 로그 줄 수를 그대로 세서 같은 출처가 같은 pattern_id를 반복 제출하면 threshold를 인위적으로 넘길 수 있었다(isolation_hook은 `source_finding`을 저장은 했지만 집계는 안 씀, reflection_hook은 애초에 `source_finding` 필드 자체가 없었음). 두 파일 모두 `source_finding`(또는 fallback으로 timestamp) 집합의 크기로 집계하도록 변경 — 같은 출처는 몇 번을 제출해도 1표. 또한 기존엔 한 번 confirmed되면 재계산해도 절대 candidate로 안 돌아갔는데(단방향 승격만), 이제는 재계산할 때마다 `count>=threshold`로 상태를 그대로 재평가(양방향)
  - COST: 과거에 "confirmed"였던 패턴이 재계산 후 "candidate"로 떨어질 수 있음(실제로 D52에서 4건 전부 발생) — 이전 세션에서 "재현율 X% 확인"이라고 보고했던 수치들의 전제(그 패턴들이 진짜 confirmed였다는 것) 자체가 흔들림
  - EXIT: `source_finding`이 비어있는 과거 로그는 timestamp를 fallback 키로 써서 최소한 서로 다른 줄로는 구분되게 함 — 다만 진짜 출처가 같은데 fallback이 달라 우연히 다시 부풀려질 위험은 남아있어, 신규 코드는 `source_finding`을 반드시 채워야 함
- **D52** (reflection_hook 4개 서브신호 전부 재검증 — 최초 seed 패턴이 전부 강등됨) — D51 적용 + 과거 로그 `source_finding` 역보강(note에서 출처 추론) 후 재계산한 결과, `too_trusted_browser`/`so_connector`/`should_do_pattern`/`backend_limit_pattern` 4개 패턴 전부가 "confirmed"에서 "candidate"로 강등됨
  - WHY: D32/D33에서 이 4개 패턴을 처음 시드할 때, 서로 다른 4개의 실제 사례가 아니라 **같은 캐노니컬 예시 문장 하나를 "round 1/2/3"으로 3번 반복 제출**해서 확정시켰다는 걸 로그 원문(note 필드)에서 직접 확인. D41에서 정립한 "서로 다른 독립 출처가 필요하다"는 원칙이 reflection_hook의 최초 4개 패턴 자체에는 소급 적용된 적이 없었음. 사용자에게 "지금 강등 vs 예외로 남김" 중 선택지를 제시했고, "지금 강등(권장)"으로 결정 — 원칙 일관성을 재현율 실적보다 우선
  - COST: **reflection_hook의 confirmed 패턴이 현재 0개**다 — `self_error_recognition`이 D34에서 REQUIRED로 지정한 유일한 필수 서브신호인데 confirmed 패턴이 없으므로 `reflection_present`는 새로운 독립 출처 2~3개가 쌓이기 전까지 항상 False다. 이전에 보고한 "재현율 0/7"(D37/D38)이라는 표현조차 이제 보면 애초에 confirmed 패턴이 있었다는 전제 자체가 부정확했다 — 진짜 상태는 "재현율 측정 불가(트래커가 아직 아무것도 확정 안 함)"에 더 가까움
  - EXIT: 서로 다른 4개 이상의 실제(가짜/시뮬레이션이라도 서로 독립적인) 답변으로 각 서브신호를 다시 3회 이상 독립 확인해야 reflection_hook이 다시 작동을 시작함. `escalation_hook.py`(D50)가 바로 이 재축적 경로 — 앞으로 escalation이 성공할 때마다 정직하게 새 confirmations가 쌓인다
- **D53** (전역 `~/.claude/agents/codex-judge.md` 신설 — 이 repo 밖 설정 파일) — codex-rescue가 judge/verdict 역할 요청을 거부해서 별도 forwarding 에이전트를 만듦
  - WHY: escalation_hook.py(D50)의 judge 단계를 실제 Codex로 돌리려 했으나 `codex:codex-rescue`가 "저는 순수 rescue-forwarder라 역할 재할당 요청은 처리 안 합니다"라고 2번 재시도에도 동일하게 거부(자기 자신에 대한 역할 지정 시도로 오해). codex-rescue 정의 파일을 직접 고치는 대신(플러그인 마켓플레이스 파일이라 업데이트 시 덮어써질 위험) 같은 `codex-companion.mjs task` forwarding 메커니즘을 쓰되 "이 프롬프트는 Codex에게 전달할 payload"라는 프레이밍을 명시한 별도 에이전트(`codex-judge`)를 `~/.claude/agents/`에 신설
  - COST: 새 에이전트 파일은 세션 시작 시 한 번 로드되는 레지스트리라 **이번 세션에는 반영 안 됨** — 실시간 검증을 위해 같은 메커니즘(`node codex-companion.mjs task ...`)을 이번 세션에서는 Bash로 직접 호출해 우회. 실제로 Codex가 정상 판정함을 확인(VERDICT: true, PATTERN_HINT: concrete_improvement) — 문제가 Codex 자체가 아니라 codex-rescue 래퍼의 해석 층이었음이 실증됨. `pipeline/escalation_hook.py`로 이 진짜 verdict를 hook에 반영 → concrete_improvement의 `sanitize_pattern`이 confirmations=1 유지(같은 출처라 dedup이 정상 작동, 인위적 승격 없음)까지 확인
  - EXIT: 다음 세션부터 `subagent_type: "codex-judge"`로 정상 호출 가능할 것으로 예상 — 새 세션에서 재확인 필요. codex-rescue 플러그인이 업데이트돼 임의 역할 프롬프트를 투명하게 전달하게 되면 이 별도 에이전트는 폐기하고 합침

## 다음 단계 (미해결)

1. ~~판단 블록에 "프레임워크 관용 패턴 목록" 대조 필터 추가~~ — D5~D7로 완료(javascript만 실증, 나머지 언어는 빈 상태)
2. ~~Tier B 트리거 오탐/이중계산 로그를 쌓아 hook 재귀 업데이트로 자동 보정~~ — D14(`tier_b_hook.py`)로 재귀 억제 루프 신설·검증 완료. 단, `sk-`/`eval(` 오탐 자체는 이미 코드로 직접 고쳤고(D12/D17), 이 훅은 *앞으로 발견될* 새 오탐용
3. ~~피드백 블록의 7단계 질문 생성을 수기가 아니라 LLM 호출로 자동화~~ — D11로 코드 구현 완료. **단, 실제 API 호출로 생성 품질을 검증하는 것은 아직 남아있음**(API 키로 최소 1회 실행 후 findings.md와 비교 필요)
4. ~~다른 언어/규모의 repo(Python)로 재검증~~ — D13으로 인지 블록 다국어 확장 + RunPod_Deploy_Agent(Python+JS 혼합)로 실증 완료(위 "다국어 재검증 실측" 참고). **대형 monorepo는 아직 미검증**
5. python/java/c/cpp/swift 관용 패턴 저장소에 실제 시드 데이터 채우기(현재 전부 `patterns: []`)
6. ~~언어 판별을 확장자 기반에서 AST/툴체인 기반으로 교체 검토~~ — D15로 `.h`만 부분 완화(내용 스니핑), 완전한 AST 기반 전환은 아직 안 함
7. **신규**: hub 판정에 최소 edge 수 임계값 추가 — 희소 그래프(RunPod_Deploy_Agent 실측)에서 무의미한 hub가 뽑히는 문제 미해결
8. **신규**: Java/C/C++ import(`import`/`#include`) 파싱은 코드로는 존재하나 실제 Java/C/C++ repo로 검증된 적 없음(Python만 실증됨)
9. **신규(jxxnixx/LMS 실측)**: D19로 고립 오탐을 30→6건 줄였지만, 남은 6건 중 개념적으로 허브와 무관한 파일(`authToken.js` 등)은 여전히 노이즈 — 관용패턴 hook과 별개로 "고립 판정용" 억제 메커니즘이 없음
10. **신규**: `pipeline/run_pipeline.py`는 `injections.json`을 사람이 채워야 함(D22) — LLM이 코드를 읽고 injection 후보를 자동 생성하되 `note`는 강제하는 반자동화가 다음 단계
11. ~~ledger.jsonl에 tier_b 방법론 실제 축적 사례가 없음~~ — Shadowbroker(`test_api_settings.py` 시크릿 오탐)로 완료. 대량 축적(수백 건) 시 성능/가독성은 여전히 미검증
12. **신규(Shadowbroker 실측)**: `auth_info_leak_via_thrown_error` 트리거가 근접성 검사 없이 "3개 키워드가 파일 어딘가에 다 있으면" 발동해 대형 파일(1500줄+)에서 오탐 발생(D26) — 코드 수정(근접 N줄 검사) 필요, hook 억제로는 부적합한 사례
13. **신규(Shadowbroker 실측)**: 726개 파일 규모 monorepo에서 `cognition-isolation` findings가 90건 이상 쏟아짐 — D19가 가정한 "entry point 1개, root 1개" 구조가 아니라 frontend/backend/스크립트가 독립된 여러 진입점을 가진 monorepo라 `find_routed_peers`가 사실상 무력화됨(진입점 다중화 미대응)
14. ~~판단 블록 3축을 LLM-as-Judge 수준으로 정량화(EVALUATION.md의 "열위(인정)" 항목)~~ — D27~D30(`judgment/subrubric.py`)으로 규칙기반 서브루브릭 구현·Study-Match-/LMS 재검증 완료. ~~서브축 construct 대표성의 외부 검증~~ — D35로 웹서치 기반 문헌 근거(SATD 탐지, CVSS/FindBugs confidence-severity 분리, 고전 검사이론 변별도 지수, Haladyna item-writing guideline, item exposure control) 확보, `location_signal`→`rationale_signal()` 교체·`risk` 공식 게이팅 구조로 변경 완료. **단, "이 문헌들이 이 도메인(레포 리뷰)에 그대로 전이되는가"는 논문 자체의 실증이지 이 시스템에서 실증된 게 아님 — 사람이 직접 채점한 것과 비교하는 검증은 여전히 안 함**. `exposure_client`의 "server" 문자열 휴리스틱 등 나머지 도메인 특화 서브축은 이번 라운드에서 손대지 않음(대체할 문헌을 못 찾음, `SUBRUBRIC_DRAFT.md`에 정직하게 기록). LLM-as-Judge 자체(자연어 논증 평가)로의 전환도 여전히 안 함, 규칙기반의 정량화 버전일 뿐
15. ~~Reflection 판정이 너무 쉽게 확정됨(POC_TEST.md 문제4)~~ — D32~D34로 완료. AND-4(너무 엄격, B안 모범 예시도 탈락) → "self_error_recognition 필수 + 나머지 2/3"으로 재보정, B안 모범 예시=True/피상적 답변=False/자기오류인식 없는 프로브=False 3건 전부 실측 확인. **단, 4개 서브신호 각각의 confirmed 패턴은 아직 예시 1건씩만 시드됨**(다양한 실제 답변으로 더 채워야 재현율이 오름)
16. ~~D38 발견에 대응해 cognition-isolation용 재귀 hook 신설~~ — D39~D41로 완료. `isolation_hook.py`/`isolation_classifier.py`가 4개 카테고리(role_separation/perf_optimization/alt_storage_or_scope/domain_irrelevance)로 6개 실제 Codex 답변 중 5건을 "타당한 근거"로 정확히 분류, 근거 부족한 1건(authToken.js)은 성급히 확정 안 함. **단, 이 6건은 카테고리 패턴을 도출한 바로 그 데이터라 held-out 검증이 아니다** — 다른 repo의 새 답변으로 재검증해야 진짜 일반화 여부를 알 수 있음. `score_findings.py`에도 아직 연결 안 함(학생 답변 입력 자체가 정적 스캔 파이프라인엔 없음)

## 발표용 라이브 데모 실행 순서 (검증됨)

인지 블록(cost_saved_ratio)과 판단 블록(관용 패턴 자동 강등)을 화면 공유로 직접 실행해서 보여주는 절차.
아래 명령 그대로 실행해 실측 확인됨.

### 사전 준비 (발표 30분 전, 반드시 새 클론 사용)

공유 clone을 쓰면 `judgment/idioms/javascript/idiom_patterns.json`이 이미 confirmed 상태라
"before"(질문가치=상)가 안 보인다. 반드시 새 클론에서 진행할 것.

```bash
git clone https://github.com/popixoxipop-collab/Code_reviewer_with_feedback.git
git clone https://github.com/popixoxipop-collab/Study-Match-.git
cd Code_reviewer_with_feedback
# 데모용으로만 로컬 초기화 (커밋 안 함, 발표 후 git checkout으로 복원)
printf '{\n  "promotion_threshold": 3,\n  "patterns": []\n}\n' > judgment/idioms/javascript/idiom_patterns.json
> judgment/idioms/javascript/idiom_feedback_log.jsonl
```

### 화면공유 순서 (5단계)

```bash
# 1) 인지 블록
python3 cognition/two_tier_scan.py ../Study-Match-/src > /tmp/scan.json
cat /tmp/scan.json   # cost_saved_ratio: 0.8 을 짚어줄 것

# 2) 판단 블록 BEFORE — App.tsx 질문가치="상"인 걸 보여줌
python3 judgment/score_findings.py /tmp/scan.json ../Study-Match-/src

# 3) 팀원 3명이 "이건 관용패턴"이라 판정했다고 가정, 라이브로 기록
python3 judgment/idiom_hook.py feedback javascript react-context-global-state idiom_not_decision "리뷰1"
python3 judgment/idiom_hook.py feedback javascript react-context-global-state idiom_not_decision "리뷰2"
python3 judgment/idiom_hook.py feedback javascript react-context-global-state idiom_not_decision "리뷰3"

# 4) 재귀 업데이트 → confirmed 승격되는 순간을 보여줌
python3 judgment/idiom_hook.py update javascript

# 5) 판단 블록 AFTER — 같은 명령 재실행, "상→하" 자동 강등 확인
python3 judgment/score_findings.py /tmp/scan.json ../Study-Match-/src
```

발표 후: `git checkout -- judgment/idioms/javascript/` (공유 clone이었다면 원상복구)
