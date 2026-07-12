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
| [`judgment/subrubric_hook.py`](./judgment/subrubric_hook.py) | 판단 | 서브축 가중치를 idiom_hook과 동일한 재귀 확인 구조로 조정 — "misaligned" 피드백이 threshold 이상 쌓인 서브축은 trusted(1.0)→discounted(0.3) |
| [`judgment/idiom_filter.py`](./judgment/idiom_filter.py) | 판단 | finding의 `pattern_key`가 confirmed 관용 패턴과 일치하면 질문가치를 낮춤 (언어별 저장소 참조) |
| [`judgment/idiom_hook.py`](./judgment/idiom_hook.py) | 판단 | 관용 패턴 재귀 업데이트 훅 — 피드백 로그 적재(`feedback`) + threshold 도달 시 candidate→confirmed 승격(`update`) |
| [`judgment/idioms/<lang>/`](./judgment/idioms/) | 판단 | 언어별(javascript/python/java/c/cpp/swift) 관용 패턴 상태(`idiom_patterns.json`)와 피드백 로그(`idiom_feedback_log.jsonl`) |
| [`judgment/tier_b_hook.py`](./judgment/tier_b_hook.py) + [`tier_b_suppression_filter.py`](./judgment/tier_b_suppression_filter.py) | 판단 | Tier B 오탐을 (trigger, matched_text) 단위로 재귀 억제(idiom_hook과 동일 패턴). "인지 블록용"으로 요청됐지만 신뢰도 판단이라 판단 블록에 위치(D14) |
| [`feedback/depth_ladder_template.md`](./feedback/depth_ladder_template.md) | 피드백 | What→How→Why→Alternative→Trade-off→Constraint→Reflection 7단계 강제 템플릿 |
| [`feedback/generate_questions.py`](./feedback/generate_questions.py) | 피드백 | 판단 블록 출력을 받아 7단계 질문을 실제 LLM 호출로 자동 생성(스키마 강제, 필드 누락 시 예외). 기본 제공자는 NVIDIA Build(`qwen/qwen3.5-397b-a17b`), `FEEDBACK_PROVIDER=anthropic`으로 Claude로 전환 가능(D56) |
| [`feedback/nvidia_client.py`](./feedback/nvidia_client.py) + [`nvidia_key_pool.py`](./feedback/nvidia_key_pool.py) | 피드백 | [`popixoxipop-collab/nvidia-build`](https://github.com/popixoxipop-collab/nvidia-build)에서 그대로 가져온 API 키-로테이션 클라이언트 — 무료 티어 40 RPM/모델/키 한도를 팀원 키 풀링으로 확장 |
| [`feedback/smoke_test_nvidia_parsing.py`](./feedback/smoke_test_nvidia_parsing.py) | 피드백 | NVIDIA의 OpenAI 호환 tool_calls 응답 파싱 로직을 네트워크 없이(고정 fixture로) 검증 — 실제 라이브 호출 검증은 아님(D56) |
| [`feedback/turn_engine.py`](./feedback/turn_engine.py) | 피드백 | 스펙 04시트 턴 상태기계(코드종속 L1→표면/부분/방어 분류→L2 트레이드오프→L3 극단시나리오→reflection, 최대 4턴) 실제 구현. `run_decision_point()`가 오케스트레이션, 질문은 매 레벨 `ask_question` 툴로 새로 생성(D87) |
| [`feedback/smoke_test_turn_engine.py`](./feedback/smoke_test_turn_engine.py) | 피드백 | `classify_answer()`의 level별(l1/l2/l3 vs reflection) 분기 로직을 fixture로 격리 검증(D87) — 실제 confirmed 패턴 DB 상태와 무관하게 코드 정확성만 확인 |
| [`feedback/reflection_signal.py`](./feedback/reflection_signal.py) + [`reflection_hook.py`](./feedback/reflection_hook.py) | 피드백 | Depth Ladder 7단계(Reflection) 판정을 idiom_hook과 동일한 재귀 확인 패턴으로 가드 — 자기오류인식/이유설명/새판단/개선안 4개 서브신호가 전부 confirmed 패턴으로 매치돼야 True |
| [`examples/study_match/`](./examples/study_match/) | 전체 | 실제 공개 repo(Study-Match-)에 3블록 전부를 돌린 실행 결과, 관용 패턴 필터 데모 포함 |
| [`pipeline/run_pipeline.py`](./pipeline/run_pipeline.py) | 전체 | 인지→판단 실행 + `injections.json`에 명시된 재귀 hook(idiom/tier_b)을 순차 주입하며 단계마다 before/after 비교표 자동 생성 |
| [`pipeline/ledger.py`](./pipeline/ledger.py) + `ledger.jsonl` | 전체 | 매 주입을 append-only로 영구 기록 — "지금까지 시도한 방법론들 비교해서 보여줘"에 답하는 데이터 소스 |
| [`pipeline/compare_methodologies.py`](./pipeline/compare_methodologies.py) | 전체 | ledger.jsonl을 즉시 집계해 방법론간 비교표를 렌더링(재실행 없이 언제든 조회 가능) |
| [`dataset/mine_repo.py`](./dataset/mine_repo.py) | 전체 | 외부 GitHub repo를 clone→인지→판단 파이프라인에 통과시켜 `examples/<lang>/<repo>/`에 fixture로 저장(D74) |
| [`dataset/corpus_report.py`](./dataset/corpus_report.py) | 전체 | `examples/**/judgment_output*.json` 전체를 언어별로 집계 — finding 개수/타입/risk-trigger 커버리지 리포트(D74) |
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

# 기본값: NVIDIA Build (qwen/qwen3.5-397b-a17b) — 팀 공유 .env에 NVIDIA_API_KEY_1..N 필요
# (키 발급/풀링 방법은 https://github.com/popixoxipop-collab/nvidia-build 참고)
export NVIDIA_API_KEY_1=<your-key>
python3 feedback/generate_questions.py judgment_output.json          # 전체 finding, JSON 출력
python3 feedback/generate_questions.py judgment_output.json 2 --md   # 상위 2건만, 마크다운 출력

# Claude로 되돌리려면
FEEDBACK_PROVIDER=anthropic ANTHROPIC_API_KEY=<your-key> python3 feedback/generate_questions.py judgment_output.json

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

## 네 번째 실증: 언어별 corpus 확장 + 품질 검증 (D74/D75, 외부 GitHub repo 41개)

`dataset/mine_repo.py`로 Python/Java/C·C++/JS·TS 외부 repo(`gh search repos`로 선정, 두 차례
스케일업으로 언어당 9~11개, 총 41개) 를 인지→판단 파이프라인에 통과시키고,
`dataset/corpus_report.py`로 기존 JS/TS fixture(`study_match`, `lms`)와 함께 집계했다.
품질 검증(D75) 결과 원본 120건 중 21건(17.5%)이 repo 태그와 다른 실제 언어의 파일
(예: Django repo의 번들 JS 라이브러리)로 드러나 제외했다 — 아래는 **필터링 후** 수치:

```
language     repos  findings  types
----------------------------------------------------------------------
c_cpp           11        26  architecture-diffusion=10, cognition-isolation=16
java             9        18  architecture-diffusion=9, cognition-isolation=8, tier-b-risk=1
javascript      10        40  architecture-diffusion=8, cognition-isolation=18, repeated-pattern=1, tier-b-risk=13
python          11        15  architecture-diffusion=8, cognition-isolation=6, tier-b-risk=1
----------------------------------------------------------------------
total: 4 languages, 99 findings (필터 전 120건, 기존 12건 대비 8.25배)

risk-trigger coverage (tier-b-risk present?): c_cpp만 NO -- 필터 전엔 1건 있었으나
그 1건(navtree.js)도 cross-language noise였음이 드러나 제외됨(java/javascript/python은 yes)
```

**언어별 finding-밀도 차이**: JS/TS가 repo당 평균 4.0건(40/10)으로 가장 높고, C/C++가
2.4건(26/11)으로 가장 낮다 — Tier B 트리거(`react-context`/`react-query`/`onSnapshot`)가
JS/Firebase 전용이라 예상된 편향이 여전히 남아있음. C/C++는 같은 언어에서도 repo에 따라
편차가 컸다(`turnstile` 12파일/0건 vs `EasyQtSql` 156파일/12건).

**품질 검증에서 실제로 확인한 2가지 결함(D75)**:
1. **cross-language noise** — repo 하나를 통째로 한 언어로 태깅하면, 그 repo 안의 다른
   언어 파일(번들 JS, 별도 프론트엔드 등)이 잘못 집계된다. `resolve_lang()`로 재확인해
   위 표에서는 이미 제외했다.
2. **Java 같은-패키지 edge 누락(미수정)** — `LibraryManageSystem`을 재-clone해 직접 대조:
   허브 `Model.java`가 같은 패키지의 `ConnectDatabase.java`를 `new ConnectDatabase()`로
   직접 참조하는데도, 자바가 같은 패키지 내 참조엔 import가 필요 없어서 `JAVA_IMPORT_RE`가
   이 edge를 못 잡아 `cognition-isolation:ConnectDatabase.java`가 오탐으로 남아있다.

개별 repo·finding 목록과 각 결함의 WHY/COST/EXIT는 D74/D75 참고.

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
- ~~NVIDIA 제공자(기본값)는 tool_choice 준수 여부를 라이브로 검증 못 함(D56)~~ — **2026-07-06 해결(D58)**: 87개 카탈로그 모델 × 실제 finding 12개 전수조사로 라이브 검증 완료. 결과/방법론은 [`SURVEY_RESULTS.md`](./SURVEY_RESULTS.md) 참고. 기본 모델을 `qwen/qwen3-next-80b-a3b-instruct`로 교체(동일 100% 준수, 4배 빠름)
- **Java의 같은 패키지(package-private) 참조가 fan-in 그래프에서 원천적으로 안 보임(D75 실측, 미수정)**: `JAVA_IMPORT_RE`는 `import` 문만 파싱하는데, 자바는 같은 패키지 내 클래스끼리는 import 없이 바로 참조 가능하다. 실측(`LibraryManageSystem`, D75): `database` 패키지의 `Model.java`가 `new ConnectDatabase()`로 같은 패키지의 `ConnectDatabase.java`를 직접 참조하는데도 edge가 안 잡혀 `cognition-isolation:ConnectDatabase.java`("허브로 가는 edge 없음")가 오탐으로 발생함. 같은 한계가 D18(TS `@/` alias)·Swift 구조스캔 제외("모듈 단위 가시성이라 파일간 import 없음")와 근본적으로 같은 클래스 — "언어의 암묵적 가시성 규칙이 명시적 import 문과 다른 경우" 전부가 잠재적 사각지대.
- **repo 하나에 여러 언어가 섞이면 파일 단위가 아니라 repo 단위로 언어를 태깅한 통계가 왜곡됨(D75 실측, `dataset/` 스크립트에서만 완화됨)**: `two_tier_scan.py`의 `SRC_EXTS`는 언어 무관하게 확장자로만 파일을 훑고 `SKIP_DIRS`에 `static`/`vendor` 류가 없다 — Django 프로젝트의 `static/js/`에 번들된 서드파티 minified JS(`Chart.min.js` 등)나, Java 백엔드+React 프론트엔드가 한 repo에 있는 경우 둘 다 finding으로 잡히지만 언어는 repo의 "주 언어"로 뭉뚱그려진다. `dataset/corpus_report.py`가 `judgment/idiom_filter.py`의 `resolve_lang()`로 finding.file 확장자를 재확인해 이런 "cross-language noise"를 언어별 집계에서 제외하도록 고쳤지만(실측 21/120건, 17.5%), 스캐너 자체(`two_tier_scan.py`)나 판단 블록(`score_findings.py`)의 finding 스키마엔 여전히 실제 파일 언어 필드가 없다.

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
- **D53** ([`judgment/subrubric_hook.py`](./judgment/subrubric_hook.py)) — 서브루브릭 4서브축을 idiom_hook과 동일한 재귀 확인 구조(candidate→threshold→조정)로 가중치화, D50~D52의 dedup+양방향 수정을 처음부터 반영
  - WHY: subrubric.py(D27~D35)는 4서브축을 전부 고정 가중치 1.0으로 그냥 더했다 — POC_TEST.md(D31)가 지적한 "이 분해가 construct를 대표하는지 외부 검증 없음"의 근본 원인. 사람이 특정 finding에서 "이 서브축 값이 최종 판정과 안 맞았다"고 반복 피드백하면(`record_feedback(axis, sub_axis, "misaligned", ..., source_finding)`) `recursive_update(axis)`가 source_finding(또는 timestamp fallback)으로 dedup한 뒤 독립 출처가 threshold(기본 3) 이상이면 trusted(1.0)→discounted(0.3), 미만이면 다시 trusted로 — 재계산마다 양방향 재평가한다(D51/D52가 isolation_hook/reflection_hook에서 실측으로 발견한 "같은 출처 반복 제출로 threshold 우회"·"한 번 확정되면 영원히 확정" 문제를 이 모듈은 처음부터 겪지 않음). `_weighted_sum`/`_normalize`로 0~12 스케일을 유지하되, 가중치가 전부 기본값이면 정규화가 항등함수라 **기존 출력과 100% 하위호환**(Study-Match- 재실행으로 실측 확인)
  - COST: 실측 데모(design_intent.mitigation_present에 3개 독립 출처로 misaligned 피드백 → discounted) 결과, `tier-b-risk:firebase.ts`는 7→6으로, `repeated-pattern:onSnapshot`은 8→9(중→상, 버킷 경계 넘음)로 **서로 다른 방향으로 바뀜**을 확인했다 — 서브축 하나를 낮추는 게 "노이즈 제거"로 깔끔하게 끝나지 않고, 정규화 분모가 줄면서 나머지 축들의 상대적 비중이 올라가 경계선 근처 finding의 버킷이 예측하기 어려운 방향으로 흔들릴 수 있다. risk 축은 게이팅 조건(`confidence_raw == 0`)을 가중치와 분리해 원본 신뢰도로만 판정하도록 명시적으로 예외 처리함. D52와 동일한 COST도 계승: 재계산할 때마다 상태가 바뀔 수 있어 "이 서브축은 discounted다"라는 과거 보고가 다음 재계산에서 뒤집힐 수 있음
  - EXIT: 버킷 경계 흔들림이 문제되면 `_normalize`를 절대 스케일(가중치 무관하게 항상 12로 나눔)로 바꾸는 것도 검토 가능(단, 그러면 discounted 서브축이 사실상 0점 처리되는 효과라 다른 트레이드오프 발생). `escalation_hook.py`(D50)와 마찬가지로 이 모듈도 "misaligned 판정"을 스스로 못 함 — 사람 또는 후속 LLM 리뷰가 판정을 넣어줘야 하는 반자동 루프
- **D54** ([`feedback/interview_rubric.py`](./feedback/interview_rubric.py)) — Project Ownership Verification 인터뷰의 3축(구조_인지도/트레이드오프_인지도/대안_탐색_능력)에 축별 5단계 레벨 정의를 코드화
  - WHY: 이 3축은 인터뷰 시점에 1~5 정수 점수만 매겨졌고 어느 레벨 기준에 해당하는지 텍스트로 명시된 적이 없었다 — subrubric.py(D27)가 정적분석 3축에서 이미 겪은 "근거 없는 판정" 문제를 인터뷰 채점도 똑같이 겪고 있었다. 사용자가 제공한 축별 5단계 정의를 `RUBRIC` dict로 코드화하고, 이미 매긴 9개 점수(3의사결정×3축)를 실제 답변 근거와 다시 대조해 [`interview_rubric_verification.md`](./examples/lms/d_plan/interview_rubric_verification.md)에 기록 — 그 결과 2건이 레벨 경계에 걸쳐 있음을 발견(의사결정 1 구조_인지도=3은 레벨 2와 경계, 의사결정 2 트레이드오프_인지도=4는 레벨 5와 경계)
  - COST: subrubric.py처럼 서브축으로 분해하지 않음(정적분석 신호가 아니라 사람이 대화를 총체적으로 읽고 판단하는 축이라 분해할 근거 신호가 없음) — 판정 재현성은 subrubric.py보다 낮고, 경계 케이스 판정은 여전히 채점자 재량
  - EXIT: 경계 케이스가 반복되면 각 레벨을 하위 신호로 더 쪼개 subrubric.py 방식(근거 필드→가중합)으로 승격 가능, `RUBRIC` 딕셔너리 구조만 유지하면 됨
- **D55** (전역 `~/.claude/agents/codex-judge.md` 신설 — 이 repo 밖 설정 파일) — codex-rescue가 judge/verdict 역할 요청을 거부해서 별도 forwarding 에이전트를 만듦 (원래 D53으로 작성 — 위 두 항목과 충돌해 D55로 재조정)
  - WHY: escalation_hook.py(D50)의 judge 단계를 실제 Codex로 돌리려 했으나 `codex:codex-rescue`가 "저는 순수 rescue-forwarder라 역할 재할당 요청은 처리 안 합니다"라고 2번 재시도에도 동일하게 거부(자기 자신에 대한 역할 지정 시도로 오해). codex-rescue 정의 파일을 직접 고치는 대신(플러그인 마켓플레이스 파일이라 업데이트 시 덮어써질 위험) 같은 `codex-companion.mjs task` forwarding 메커니즘을 쓰되 "이 프롬프트는 Codex에게 전달할 payload"라는 프레이밍을 명시한 별도 에이전트(`codex-judge`)를 `~/.claude/agents/`에 신설
  - COST: 새 에이전트 파일은 세션 시작 시 한 번 로드되는 레지스트리라 **이번 세션에는 반영 안 됨** — 실시간 검증을 위해 같은 메커니즘(`node codex-companion.mjs task ...`)을 이번 세션에서는 Bash로 직접 호출해 우회. 실제로 Codex가 정상 판정함을 확인(VERDICT: true, PATTERN_HINT: concrete_improvement) — 문제가 Codex 자체가 아니라 codex-rescue 래퍼의 해석 층이었음이 실증됨. `pipeline/escalation_hook.py`로 이 진짜 verdict를 hook에 반영 → concrete_improvement의 `sanitize_pattern`이 confirmations=1 유지(같은 출처라 dedup이 정상 작동, 인위적 승격 없음)까지 확인
  - EXIT: 다음 세션부터 `subagent_type: "codex-judge"`로 정상 호출 가능할 것으로 예상 — 새 세션에서 재확인 필요. codex-rescue 플러그인이 업데이트돼 임의 역할 프롬프트를 투명하게 전달하게 되면 이 별도 에이전트는 폐기하고 합침
- **D56** ([`feedback/generate_questions.py`](./feedback/generate_questions.py)) — 기본 LLM 제공자를 Anthropic Claude에서 NVIDIA Build(`qwen/qwen3.5-397b-a17b`)로 전환. **모델 선택 자체는 D58로 대체됨** (아래, `qwen/qwen3-next-80b-a3b-instruct`)
  - WHY: 2026-07-06 별도 세션에서 실제 코드(`compression_rank1_test.py`)를 NVIDIA 3개 모델(qwen3.5-397b-a17b/nemotron-3.3-super-49b/llama-3.1-8b-instruct)에 리뷰시키고 각 지적을 코드와 대조 검증한 결과, qwen3.5-397b-a17b가 사실관계 오류 없이 가장 정확했음(nemotron-49b는 확신도 High로 낸 지적 1건이 사실과 다름, llama-3.1-8b는 할루시네이션+반복 필러). NVIDIA Build 무료 티어는 40 RPM/모델/키 한도 외 별도 quota가 없어(2026-07-06 확인) [`nvidia-build`](https://github.com/popixoxipop-collab/nvidia-build) 키 풀링과 결합하면 비용 없이 운용 가능
  - COST: NVIDIA Build는 OpenAI 호환 스키마(`tools`/`tool_calls`, 문자열 `arguments`)라 Anthropic의 객체형 `tool_use` 블록과 응답 형태가 완전히 달라 `generate_for_finding()`이 provider별로 분기됨. `feedback/nvidia_client.py`·`nvidia_key_pool.py`는 별도 private repo(`nvidia-build`)에서 그대로 복사해온 것이라 그쪽이 바뀌면 수동 재동기화 필요(패키지 의존성 대신 vendoring한 이유: private repo라 `pip install git+https://...`가 CI/팀 공유에 부적합하고, 파일 2개짜리에 git submodule은 과함). 이 세션엔 `NVIDIA_API_KEY`가 없어 qwen3.5가 이 7필드 스키마에서 `tool_choice`를 실제로 지키는지는 검증 못 함(`smoke_test_nvidia_parsing.py`는 파싱 로직만 fixture로 구조 검증)
  - EXIT: `FEEDBACK_PROVIDER=anthropic` 환경변수 하나로 즉시 원복, 코드 삭제 불필요. `nvidia_client.py`/`nvidia_key_pool.py` drift가 문제되면 `nvidia-build`를 public으로 바꾸거나 사설 PyPI 인덱스로 배포해 `requirements.txt` 의존성으로 전환(공개 API는 동일해 호출부 변경 없음)
- **D57** ([`feedback/interview_rubric.py`](./feedback/interview_rubric.py)) — 인터뷰 채점 3축을 요구사항정의서 FR-04-01의 5축(코드이해/설계논리/대안비교/반례대응/자기수정)에 맞춰 정리
  - WHY: 대시보드 목업(`frontend/mockups/dashboard.html`)이 이미 FR-04-01 5축 레이더 차트를 전제로 만들어져 있는데 채점 코드는 3축뿐이었음. 게다가 기존 "트레이드오프_인지도" 축은 이름과 달리 레벨 설명 5개가 전부 "반례" 기준으로 쓰여 있어 실질적으로 이미 FR의 "반례 대응"과 동일한 축이었음(이름-내용 불일치). 즉 전면 재설계가 아니라 ①구조_인지도→코드_이해, 트레이드오프_인지도→반례_대응, 대안_탐색_능력→대안_비교로 재명명 ②원래 없던 설계_논리·자기_수정 2축 신설. 자기_수정은 `reflection_signal.evaluate_reflection()`(D34)의 서브신호 매칭 개수를 그대로 1~5점 초안으로 승격해 재사용(`auto_score_self_correction()`) — 레벨 4 경계를 현재 `reflection_present=True` 판정 기준과 정확히 일치시킴
  - COST: 기존 3축의 dict 키는 하위호환을 위해 이름을 바꾸지 않고 그대로 둠(`examples/lms/d_plan/interview_rubric_verification.md`에 이미 "구조_인지도=3" 같은 기록이 있어 키를 바꾸면 근거가 깨짐) — 대신 `FR_AXIS_ALIAS`로 대응관계만 명시해 RUBRIC 안에 구 이름 3개·신규 이름 2개가 섞여 있음. **`auto_score_self_correction()`을 D37의 Codex 실측 케이스(Bookshelf.jsx XSS 답변, "정성적으로 매우 우수한 reflection"이라고 문서가 직접 평가)로 검증한 결과 1/5점("오류를 전혀 인정하지 않음")이 나옴** — 새 버그가 아니라 D37/D34가 이미 기록한 `reflection_signal.py`의 정규식 재현율 문제(matched_count 0/4)가 1~5 등급에도 그대로 드러난 것. "자동 초안일 뿐 최종 확정은 사람"이라는 원칙(D54)이 있어 이 오판정이 그대로 리포트에 나가지는 않지만, 자동 초안 자체의 신뢰도는 여전히 낮음
  - EXIT: 다음 회차부터 새 이름으로 직접 채점하려면 RUBRIC 키를 `FR_AXIS_ALIAS` 값으로 바꾸고 옛 검증 문서엔 각주만 남기면 됨. `auto_score_self_correction()`의 임계값이 계속 안 맞으면 이 함수만 고치면 됨(RUBRIC 구조는 불변) — 근본적으로는 `reflection_signal.py`의 confirmed 패턴 시드가 1개뿐이라(D9 COST) 다양한 표현을 못 잡는 문제이므로, 실제 학생 답변이 쌓여야 진짜 개선됨

- **D58** ([`feedback/generate_questions.py`](./feedback/generate_questions.py)) — 기본 모델을 `qwen/qwen3.5-397b-a17b`에서 `qwen/qwen3-next-80b-a3b-instruct`로 교체
  - WHY: 2026-07-06 라이브 전수조사(87개 카탈로그 모델 × 실제 finding 12개)로 D56의 근거를 이 저장소의 실제 task(스키마 강제 tool-calling)에서 재검증. 두 모델 다 `tool_choice` 100% 준수(12/12)·질문 품질 대등이지만 qwen3-next-80b-a3b-instruct가 13.2s로 qwen3.5-397b-a17b(52.9s)보다 4배 빠름. 별도 코드리뷰 벤치마크(`nvidia-build`)에서도 속도·정확도·재현성 3축 전부 상위 — 서로 다른 두 task가 같은 모델을 가리킴
  - COST: 없음 확인됨(같은 증거 기준 순수 개선). `idiom_filtered` 케이스가 fixture에 2/12뿐이라 "짧게/쉽게" 지시 준수 검증은 약함
  - EXIT: `SURVEY_RESULTS.md`에 100% 준수 확인된 대안 순위표 있음 — `stepfun-ai/step-3.5-flash`(4.6s, 최속이나 재현성 미검증), `deepseek-ai/deepseek-v4-pro`(48.9s, 재현성 최고 0.9)

- **D59** ([`METHODOLOGY_AUDIT_HANDOFF.md`](./METHODOLOGY_AUDIT_HANDOFF.md)) — "3단계 고정 구조"·L1~L5 히트맵·5축 채점 세 개념의 관계를 감사해 문서로 확정
  - WHY: "3단계 고정 구조 + 동적 질문 생성에서 3단계가 뭐고 L1~L5·5축과 어떻게 연결되는가"라는 질문이 반복 제기됨. 저장소 전체(`README.md`/`POC_TEST.md`/`TEAM_POC_SUMMARY.md`)와 요구사항명세서 v2.0 원문을 재대조한 결과 "3단계"는 세션 진행 단계가 아니라 **인지·판단·피드백 3블록 파이프라인**(`README.md:1`, `POC_TEST.md:1`)을 가리키는 말이었고, L1~L5(FR-5.7)·5축 채점(`interview_rubric.py`)과는 코드상 연결이 전혀 없음(grep 0건)을 확인. 부가로 이 저장소 자체가 팀 5개 경쟁안(A~E) 중 C/D/E안일 뿐이라는 사실도 재확인(`TEAM_POC_SUMMARY.md`)
  - COST: 이 감사는 혼동의 원인을 문서화했을 뿐 실제 공백(Depth Ladder 7단계→L1~L5 압축 규칙 부재, 5축 프레임워크 3종 불일치, A/B안 원본 미확보)을 해소하지는 못함 — 전부 팀 결정이 필요한 채로 남음
  - EXIT: 팀이 압축 규칙·축 프레임워크를 확정하면 `METHODOLOGY_AUDIT_HANDOFF.md`의 "팀이 실제로 결정해야 할 것" 섹션을 지우고 그 결정을 `interview_rubric.py`/FR 문서에 직접 반영

- **D60** ([`METHODOLOGY_AUDIT_HANDOFF.md`](./METHODOLOGY_AUDIT_HANDOFF.md)) — 핸드오프 문서 범위를 방법론 정합성(D59, 3문항)에서 AI 파이프라인 전체 6문항 감사로 확장
  - WHY: "AI 기능 처리 로직을 못 쓴다"는 수준의 차단 질문(모델/CodeSearchNet/Decision Point 추출/GitHub API 연동/방법론/채점방식)이 한 세트로 다시 제기됨. D59는 3문항(방법론)만 다뤄서 나머지 3문항(모델·데이터·아키텍처 현실)이 별도 chat 답변에만 남아 있었음 — 전부 같은 문서에 통합해야 팀이 한 번에 참조 가능. 재검증 결과 신규 확정 사실: 판단 블록은 LLM 호출이 코드에 전혀 없음(grep 0건, LLM-as-judge 아님), CodeSearchNet·GitHub API 실연동 둘 다 0건(스펙 선언뿐), 최종등급명 "소유/표면/미흡"은 스펙 table4에 있으나 컷오프 수치는 스펙·코드 어디에도 없음
  - COST: 문서 하나가 길어져 특정 질문 하나만 빠르게 찾기 어려워짐 — TL;DR 표를 최상단에 둬서 완화
  - EXIT: 문항이 더 늘어나 문서가 과하게 길어지면 문항별로 파일 분리하고 이 문서는 인덱스 역할만 하도록 축소

- **D61** ([`benchmarks/harness.py`](./benchmarks/harness.py), [`benchmarks/reproducibility.py`](./benchmarks/reproducibility.py)) — 채점·MEAS-02 두 신규 벤치마크가 공유하는 동시호출/재현성 비교 모듈 신설
  - WHY: `full_survey.py`/`rerun_failed.py`가 이미 `ThreadPoolExecutor`+진행률출력 루프를 각자 인라인 구현해뒀고, 이번이 3번째 필요 시점(`score_findings.py` D13 EXIT의 "3번째로 필요해지면 공용 모듈로 추출" 원칙과 동일). 재현성 비교는 `nvidia-build/DECISIONS.md` D9가 한 번도 커밋하지 못한 부분(세션 스크래치패드 한정, 수동 보정)인데, 이 저장소의 새 벤치마크는 둘 다 스키마강제 tool-calling(D56/D58 패턴)이라 출력이 구조화 JSON — regex-Jaccard 근사 없이 필드 단위 exact-match로 정확히 계산 가능해짐
  - COST: 자유서술 출력(`generate_questions.py`의 Depth Ladder 값 자체)에는 이 exact-match가 너무 엄격 — 그런 경우는 여전히 D9식 Jaccard/사람 대조가 필요
  - EXIT: 벤치마크가 하나만 남으면 호출부에 도로 인라인
- **D62** — 채점·MEAS-02 두 벤치마크의 후보 모델을 이미 코드리뷰(`nvidia-build`)+tool-calling(`SURVEY_RESULTS.md`) 양쪽에서 검증된 5개(`qwen3-next-80b-a3b-instruct`/`deepseek-v4-pro`/`glm-5.2`/`minimax-m3`/`nemotron-3-ultra-550b-a55b`)로 한정
  - WHY: 87개 카탈로그 재탐색은 비용/시간 낭비 — 이 5개가 이미 두 독립 과제를 통과함. 특히 qwen3-next-80b-a3b-instruct는 기획명세서 00시트가 "질문생성기·채점기 동일 모델"로 이미 지정한 모델이라, 여기서는 "최선 선택"이 아니라 "그 결정이 채점/추출 역할에서도 성립하는가"를 검증하는 목적
  - COST: 채점/evidence-추출에 이 5개보다 더 적합한 모델을 놓칠 수 있음
  - EXIT: 5개 전부 저조하면 `stepfun-ai/step-3.5-flash`(tool-calling 100%/최속, 정밀도 미검증) 추가
- **D63** ([`feedback/llm_interview_grader.py`](./feedback/llm_interview_grader.py)) — FR-04-01 5축 채점을 스키마강제 tool-calling(`GRADING_TOOL`)으로 최초 구현 — `interview_rubric.py`가 D54부터 "최종 점수는 사람/LLM이 확정해야 한다"고 표시해둔 4/5축(자기_수정 제외)의 첫 실제 채점 코드
  - WHY: D56/D58이 이미 `DEPTH_LADDER_TOOL`(7필드)에서 스키마강제 tool-calling이 안정적으로 동작함을 검증함. 자유서술 채점은 파싱이 불안정하고, "근거 인용 강제"(기획명세서 00시트 확정 결정)를 구조적으로 보장 못 함
  - COST: 5축×{score,evidence} 스키마가 7필드 DEPTH_LADDER보다 커서 일부 모델 tool-calling 실패율이 오를 가능성(실측 결과는 D69 참고)
  - EXIT: 실패율 높으면 축별 5회 개별 tool call로 분리
- **D64** ([`benchmarks/grading_testset.py`](./benchmarks/grading_testset.py)) — 채점 벤치마크 ground truth를 목표레벨(1/3/5) 사전라벨링 시뮬레이션 답변 15개로 구성(실제 학생 답변 전무)
  - WHY: `METHODOLOGY_AUDIT_HANDOFF.md`/README가 이미 "실제 학생 답변으로 단 한 건도 검증된 적 없다"고 인정한 상태 — 유일하게 지금 실행 가능한 방법
  - COST: 목표레벨=정답 취급은 자기참조적 라벨("우리가 그 레벨을 의도하고 썼다")일 뿐 실제 사람 채점자와의 합치도가 아님 — 결과 문서에 명시
  - EXIT: 실제 학생 인터뷰 데이터가 쌓이면 사람이 채점한 실답변 셋으로 교체
- **D65** ([`judgment/meas02_decision_point_extractor.py`](./judgment/meas02_decision_point_extractor.py)) — Phase 2를 "정적분석(`cognition`/`judgment` 블록) vs LLM결합 비교"에서 "기획명세서 그대로의 순수 LLM MEAS-02 추출기 구현+벤치마크"로 전면 재설계
  - WHY: `기획명세서_AI기반_프로젝트교육품질관리플랫폼.xlsx`(00시트, "확정 설계 결정(Locked)")가 이미 "Decision Point 추출 = 순수 LLM(정적 분석 미사용) — AST·CodeSearchNet 매칭 방식은 폐기"로 확정함. 이 저장소의 정적분석 블록(cognition/judgment)은 팀이 이미 폐기하기로 결정한 방식이라, 그 우월성을 다시 벤치마크하는 건 이미 답 난 질문 — 대신 스펙이 요구하는 실제 I/O 계약(코드조각+요구사항+회차포커스 → Decision Point 세트[파일·함수·판단유형·근거·연결요구사항])을 구현하는 게 팀에 쓸모있음
  - COST: 애초에 설계했던 하이브리드(evidence dict 부분위임, `apply_subrubric()` 재사용) 설계는 전량 폐기. 실측 결과(D69) 이 추출기는 단일 파일만 보므로 cross-file 구조 신호(허브 미연결 등)를 원천적으로 못 잡음 — 스펙이 선택한 아키텍처의 알려진 트레이드오프이지 버그 아님
  - EXIT: 팀이 정적분석 재도입/하이브리드를 결정하면 `score_findings.py`/`subrubric.py`와 병행 비교를 이 모듈과 별도로 재설계
- **D66** — MEAS-02 벤치마크의 정밀도 지표를 "recall"이 아니라 **reference-set coverage**로 명명(기존 4개 정적분석 finding은 gold standard가 아니라 참고 세트)
  - WHY: 정적분석 자체가 팀 결정상 폐기 대상이라 그걸 정답으로 삼으면 안 됨 — `EVALUATION.md` 이래의 정직성 원칙 계승
  - COST: 원래 기대했을 "recall"이라는 단어와 다름, 설명 필요
  - EXIT: 실제 학생 코드 기반 사람 검증 데이터가 쌓이면 진짜 gold standard로 교체
- **D67** ([`benchmarks/`](./benchmarks/)) — 채점·MEAS-02 벤치마크를 위한 최상위 `benchmarks/` 디렉토리 신설(`judgment/`나 `pipeline/`이 아님)
  - WHY: 이건 인지·판단·피드백 블록 전체를 가로지르는 방법론 벤치마크지 `pipeline/compare_methodologies.py`(단일 방법론의 훅 이력 집계)와 다른 목적. `full_survey.py`가 이미 repo-root survey script 전례이고, 자매 repo `nvidia-build/benchmarks/`가 이미 이 repo 전체에서 참조되는 컨벤션
  - COST: survey류 스크립트가 repo-root(`full_survey.py`)와 `benchmarks/` 두 곳에 나뉨
  - EXIT: 나중에 `full_survey.py`/`rerun_failed.py`도 `benchmarks/`로 이동(순수 코드 이동, 이번 범위 밖)
- **D68** — MEAS-02 벤치마크의 Phase 0을 "Study-Match-/LMS repo clone만"으로 축소, `examples/lms/judgment_output_baseline.json` 재생성 요구 제거
  - WHY: bucket-agreement 비교(`subrubric.py` 의존)를 더 이상 하지 않으므로, 그 baseline이 D29(subrubric.py 도입) 이전 스키마라는 문제 자체가 무관해짐. 단 실제 코드 조각 입력을 위해 repo clone은 유지
  - COST: 없음(요구사항 축소)
  - EXIT: 해당 없음
- **D69** ([`benchmarks/grading_run_benchmark.py`](./benchmarks/grading_run_benchmark.py), [`benchmarks/meas02_run_benchmark.py`](./benchmarks/meas02_run_benchmark.py)) — 채점(15케이스)·MEAS-02(4케이스) 두 벤치마크 실행 완료, 기획명세서 00시트 "Qwen 스펙 미검증 — 락 전 실측 필요" 리스크를 부산물로 검증
  - WHY/결과: **팀이 이미 확정한 `qwen3-next-80b-a3b-instruct`는 두 역할 모두에서 깨끗하게 검증됨** — 채점: tool_choice 100%, MAE 0.28(1~5점 척도), 재현성 0.93. MEAS-02: tool_choice 100%, 단일 파일에서 탐지 가능한 참고 finding 3/3 전부 커버(reference-set coverage), 평균 22초/호출. **단, cross-file 구조 신호(firebase.ts 허브에 연결 안 된 Competitions.tsx의 고립)는 이 모델도 못 잡음** — 정적분석 폐기(D65)의 실제 대가가 실측으로 확인된 지점. 나머지 4개 비교 모델(`deepseek-v4-pro`/`glm-5.2`/`minimax-m3`/`nemotron-3-ultra-550b-a55b`)은 API 키 1개 공유+동시성 경합(일부는 당시 다른 병렬 세션의 `benchmark_track_a/b.py` 실행과 겹쳐 쿼터 소진 — `TRACK_AB_BENCHMARK_RESULTS.md` D70~D73 참고)으로 성공률이 0~75%에 그쳐 순위를 신뢰할 수 없음
  - 참고(교차검증): 병렬 세션의 D70~D73(`TRACK_AB_BENCHMARK_RESULTS.md`)이 별도 6모델 벤치마크에서 **qwen3-next-80b가 정밀도·재현성은 만점이지만 다른 5개 모델보다 4~10배 느림**(24~36s vs 2.6~6.5s)을 확인 — 실시간 세션 응답 지연 이슈로 이어질 수 있어 팀이 알아야 할 트레이드오프. 같은 문서가 `openai/gpt-oss-120b`의 채점 재현성 결함(σ 기반 0.37)도 확인 — `nvidia-build` 코드리뷰 벤치마크에서 이미 드러난 이 모델의 비결정성 문제(D10에서 배제 사유)가 채점 역할에서도 재현된 것
  - COST: 5개 모델 x 소규모 케이스만 테스트, 대규모 실제 학생 세션/큰 monorepo 규모는 미검증. 상세 방법론적 한계(단일 키 동시성 경합 등)는 `benchmarks/grading_benchmark_results.md`/`benchmarks/meas02_results.md`에 명시
  - EXIT: qwen3-next-80b가 실전에서 속도 문제로 부적합 판정되면 D62 후보군에서 재검토(단, 재검토 전 반드시 API 키를 여러 개로 늘려 동시성 경합 없이 재측정할 것)

- **D70~D73** ([`benchmark_track_a.py`](./benchmark_track_a.py), [`benchmark_track_b.py`](./benchmark_track_b.py)) — Track A(질문생성)/Track B(채점) 6모델 실측 벤치마크 실행 + deepseek-v4-pro 접근불가로 mistral-nemotron 교체(D73)
  - WHY: 기획명세서가 모델을 qwen3-next-80b-a3b-instruct 단일로 lock했지만, 질문생성과 채점은 성공기준이 다른 별개 역할이라 "이미 고른 모델이 각 역할에서 합격선을 넘는가"를 실측 검증할 필요가 있었음(사용자 요청). 상세 결과·발견·한계는 [`TRACK_AB_BENCHMARK_RESULTS.md`](./TRACK_AB_BENCHMARK_RESULTS.md) 참고
  - COST: 실행 중 `benchmarks/`(D61~D69, 병렬 세션 작업)와 목적이 겹치는 걸 뒤늦게 발견 — 원래 D61부터 번호를 매기려다 충돌해 D70으로 재조정. 이 벤치마크의 채점 축 이름·재현성 계산 방식이 `benchmarks/`의 production 정합 버전보다 엄격도가 낮음(`TRACK_AB_BENCHMARK_RESULTS.md`의 비교표 참고)
  - EXIT: 팀이 공식 벤치마크로 하나만 채택하려면 `benchmarks/`(더 엄격, production 코드 정합) 쪽을 실행해 이 결과와 대조 후 이 문서에 "상위호환됨" 각주 추가

- **D74** ([`dataset/mine_repo.py`](./dataset/mine_repo.py), [`dataset/corpus_report.py`](./dataset/corpus_report.py)) — 인지·판단 블록(정적분석, `two_tier_scan.py`+`score_findings.py`)을 처음으로 JS/TS 외 3개 언어(Python/Java/C·C++)의 실제 공개 repo에 돌려 finding fixture를 신설, 두 차례 스케일업(언어당 1~2개 → 5~7개 → 9~11개, 총 41개 repo)
  - WHY: `full_survey.py:36-47`의 `FIXTURES`가 여전히 `study_match`/`lms` 둘뿐이라 finding 다양성이 12개(전부 JS/TS)로 고정돼 있었음. "다국어 재검증 실측"(132번 줄, RunPod_Deploy_Agent Python 6+JS 2)과 "세 번째 실증"(140번 줄, jxxnixx/LMS)이 이미 다국어 파싱 버그(D17, 메서드 호출 형태의 위험 함수 호출 오탐)와 sparse-graph 한계를 실측으로 드러냈지만, 그 결과가 `examples/`에 `judgment_output.json`으로 저장된 적은 없어서(스크래치 버그헌팅으로 끝남) 재사용 가능한 fixture가 하나도 안 남아있었다. 사용자 요청(popixoxipop-collab org 대신 외부 GitHub repo로 소싱)에 따라 `gh search repos`로 실재하는 소규모~중규모 repo를 선정해 `mine_repo.py`(clone→scan→score를 스크립트화)로 전부 통과시켰고, 스캔/채점 코드 자체는 무수정(순수 stdlib, 리포별 하드코딩 없음을 사전 확인) — 새로 만든 건 오케스트레이션과 집계뿐.
  - COST: 최종 41개 repo/120건 원본 findings도 여전히 SFT 정석 물량(보통 수백~수천)엔 못 미침 — 이건 "언어당 repo 수"보다 "언어별 finding 밀도" 문제로 드러남(1차 스케일업 시점 JS/TS 6.2건/repo vs Python 1.1건/repo). Python 2차 추가 repo(django/api 키워드 검색)로 밀도가 3건/repo까지 올라 어느 정도 완화됐지만 여전히 JS/TS보다 낮음. `turnstile`(C, 12파일)은 finding 0건으로 남음 — repo가 나빠서가 아니라 132번 줄이 이미 실측한 "edge가 적은 sparse graph에선 hub/isolation 판정 자체의 신뢰도가 낮다"는 한계. **이 120건 중 21건(17.5%)이 실제로는 cross-language noise였음이 D75 품질검증으로 드러남** — 최종 신뢰 가능한 수치는 D75 참고.
  - EXIT: 여전히 물량이 더 필요하면 `mine_repo.py <git_url> <lang> [slug]`를 반복 호출해 언어당 repo를 더 늘리면 됨(스크립트는 이미 반복 실행 검증됨). `full_survey.py`/`rerun_failed.py`의 `FIXTURES`에 새 경로들을 추가하면 87모델 서베이도 이 확장된 corpus로 재실행 가능(이번 pass에선 의도적으로 안 건드림 — 그건 별개 관심사).

- **D75** ([`dataset/corpus_report.py`](./dataset/corpus_report.py)) — D74 corpus의 품질 검증(사용자 요청) 중 실제 결함 2건 발견, 1건은 이 스크립트에서 수정
  - WHY: 물량만 늘리고 내용을 확인 안 하면 "그럴듯하지만 틀린" fixture가 SFT 데이터로 그대로 흘러들어갈 위험이 있어, D74로 만든 41개 repo 중 일부를 실제로 재-clone해 finding 원문과 대조 검증했다. **발견 1(수정함)**: `examples/python/API-Manager/`(Django) 등 3개 repo에서 `tier-b-risk` finding이 실제로는 `static/js/`에 번들된 서드파티 minified JS(`Chart.min.js` 등)였고, `examples/java/Modern-API-Development-with-Spring-6-and-Spring-Boot-3/`는 finding 13건 전부가 이 repo의 React 프론트엔드(`Auth.js`/`Login.js` 등)였다 — repo 하나를 통째로 하나의 언어로 태깅한 게 원인. `judgment/idiom_filter.py`의 `resolve_lang()`(이미 프로덕션에서 쓰는 함수, 재구현 없이 import)로 `finding.file`의 실제 확장자를 재확인해 repo 태그와 다르면 언어별 집계에서 제외하도록 `corpus_report.py`를 고쳤다. **발견 2(미수정, 문서화만)**: `examples/java/LibraryManageSystem/`을 재-clone해 직접 대조한 결과, `cognition-isolation:ConnectDatabase.java`("허브로 가는 edge 없음")가 오탐임을 확인 — 허브 `Model.java`가 `new ConnectDatabase()`로 같은 패키지(`database`) 클래스를 직접 참조하는데, 자바는 같은 패키지 내 참조에 `import`가 필요 없어 `JAVA_IMPORT_RE`가 이 edge를 원천적으로 못 잡는다. 상세는 "알려진 한계" 섹션 참고.
  - COST: cross-language noise 필터링 후 corpus는 120건 → **99건**으로 줄었다(21건, 17.5% 제외). 필터는 `dataset/corpus_report.py`(내가 만든 집계 스크립트)에만 적용됨 — `two_tier_scan.py`/`score_findings.py`(공유 프로덕션 파이프라인, 동시에 다른 세션이 작업 중)는 건드리지 않았으므로 `examples/*/judgment_output.json` 원본 파일 자체엔 여전히 이 21건이 섞여 있다. Java 같은-패키지 사각지대는 발견만 하고 안 고쳤음 — `score_findings.py`의 hub/isolation 판정 로직을 바꾸는 건 D74보다 범위가 크고, 지금 이 저장소에서 다른 세션이 동시에 `benchmarks/`·`judgment/meas02_decision_point_extractor.py`를 작업 중이라 핵심 판단 블록을 건드리는 건 더 조심스럽게 별도로 계획해야 한다고 판단.
  - EXIT: cross-language noise를 스캐너 단에서부터 막고 싶으면 `two_tier_scan.py`의 `SKIP_DIRS`에 `static`/`vendor`/`node_modules`류를 보강하거나(단, 공유 파일이라 다른 세션과 조율 필요), `score_findings.py`가 만드는 finding 스키마에 `resolve_lang(file)` 결과를 언어 필드로 아예 박아넣으면 `corpus_report.py`의 사후 재계산이 불필요해짐. Java 같은-패키지 edge 문제는 `JAVA_IMPORT_RE`가 파싱한 것과 별개로 "같은 디렉터리(=대개 같은 패키지) 파일들끼리는 무조건 edge로 간주"하는 보수적 휴리스틱을 추가하면 완화 가능(단, 오탐↔누락 트레이드오프 재평가 필요).

- **D76** ([`cognition/two_tier_scan.py`](./cognition/two_tier_scan.py), [`judgment/score_findings.py`](./judgment/score_findings.py)) — D75 EXIT의 두 제안을 실제로 구현(사용자 요청): `SKIP_DIRS`에 static/vendor 보강 + finding 스키마에 `lang` 필드 신설
  - WHY: D75가 `dataset/corpus_report.py`(내 집계 스크립트)에서만 사후 필터링으로 우회했던 cross-language noise를, 공유 프로덕션 파이프라인(`two_tier_scan.py`/`score_findings.py`) 자체에서 근본적으로 막아달라는 사용자 요청. `two_tier_scan.py`의 `SKIP_DIRS`(D76 이전: `node_modules`/`.git`/`dist`/`build`/`__pycache__`/`.venv`/`venv`)에 `static`/`vendor`/`vendored`를 추가해 서드파티 자산 디렉터리 자체를 스캔 대상에서 뺐다. 이것만으론 "Java 백엔드 repo에 React 프론트엔드가 같이 있는" 경우(전용 vendor 디렉터리가 아닌 진짜 다른 언어 소스)를 못 잡으므로, `score_findings.py`의 `score()` 끝에 `_tag_lang()`을 추가해 모든 finding에 `judgment/idiom_filter.py`의 `resolve_lang()`(`.h` 파일은 내용 기반 c/cpp 재판정 포함, D15와 동일 로직 재사용)로 계산한 실제 언어를 `lang` 필드로 박아넣었다.
  - COST: 재검증 결과(41개 repo 전부 재-mine) — `SKIP_DIRS` 보강만으로 raw finding이 **120→112건**으로 줄었다(정적/vendor 자산 8건이 애초에 스캔 대상에서 빠짐: `examples/python/API-Manager`가 4→1건, `examples/java/zgc-ems`가 4→1건 등). 남은 cross-language 사례는 **13건**(`Modern-API-Development-with-Spring-6-and-Spring-Boot-3`의 React 프론트엔드 12건 + `EasyQtSql`의 `navtree.js` 1건) — 둘 다 "static/vendor라는 이름이 아닌 진짜 다른 언어 디렉터리"라 `SKIP_DIRS`로는 원천 차단이 안 되고, 새 `lang` 필드가 있어야 `corpus_report.py`가 걸러낼 수 있다. 최종 `dataset/corpus_report.py` 집계는 112 - 13 = **99건**으로 D75 때와 동일(우연히 같은 숫자 — D75는 20건을 사후 필터, 이번엔 8건을 스캔 단계에서 차단 + 13건을 스키마 필드로 필터). 기존 `examples/lms/`·`examples/study_match/` fixture는 D76 이전 스키마라 `lang` 필드가 없음 — `corpus_report.py`가 `"lang" in finding`으로 분기해 하위호환 유지(없으면 `resolve_lang(file)`로 즉석 계산).
  - EXIT: `lms`/`study_match`도 재-clone해 `score_findings.py`를 다시 돌리면 `lang` 필드를 채울 수 있음(이번 pass에선 재-clone 경로가 로컬에 없어 보류). Java 같은-패키지 edge 사각지대(D75 발견 2)는 여전히 미수정 — 다음 손댈 후보는 이쪽이지만, 공유 판단 블록(`score_findings.py`)의 hub/isolation 로직 자체를 바꾸는 거라 D74~D76보다 범위가 크다.

- **D77** ([`benchmarks/grading_run_benchmark.py`](./benchmarks/grading_run_benchmark.py), [`benchmarks/meas02_run_benchmark.py`](./benchmarks/meas02_run_benchmark.py)) — D69가 미신뢰로 남긴 4개 모델(deepseek-v4-pro/glm-5.2/minimax-m3/nemotron)을 모델별 순차 실행+전량 재시도로 재검증 완료(사용자 요청: "쿼터 제한으로 안나온 부분은 마저 채워넣기")
  - WHY: D69 자신이 이미 "동시성 경합이라 재검증 없인 신뢰하면 안 됨"이라고 EXIT에 못박아뒀다. `main()`을 5모델 동시 제출에서 모델별 순차 실행(각 모델 내부는 그대로 max_workers 동시성)으로 바꾸고, 실패 건을 2~20초 간격으로 최대 3라운드 순차 재시도(매 성공마다 즉시 디스크 저장 — 재시도 스크립트가 타임아웃으로 죽어도 유실 없게)했다.
  - COST/결과: **채점** — qwen/deepseek-v4-pro/minimax-m3 3개 전부 100% 회복(deepseek는 격리 단독 호출도 즉시 성공 — D69의 "쿼터 소진" 추정이 맞았음을 확인), nemotron 87%(잔여는 503/timeout 혼재, 진짜 서비스 이슈로 보임). **MEAS-02** — qwen/deepseek 100%, nemotron 75%. **minimax-m3는 25%로 채점(100%)과 딴판** — 실패가 거의 전부 120s 타임아웃이라, 짧은 프롬프트(채점)엔 강하지만 긴 프롬프트(MEAS-02는 전체 코드파일+요구사항 전문)에 취약한 모델 고유 특성으로 추정. **glm-5.2만 유일하게 두 벤치마크 다 0%** — 모델별 순차 실행(경합 제거)+격리 단독 호출 3회+20초 간격 순차 재시도 7연속까지 총 9회 시도 전부 실패(주로 120s 타임아웃). SURVEY_RESULTS.md의 예전 87모델 전수조사에서도 이 모델만 5/12(42%, "genuinely slow")였던 이력과 일치 — 경합이 아니라 이 모델 자체가 지속적으로 이용 불가 수준이라는 결론. 두 `to_markdown()`의 "방법론적 한계" 문단을 이 최종 수치로 갱신.
  - EXIT: glm-5.2를 후보군에서 빼고 재검토하려면(EXIT 조건 재충족 시) 이 5개 벤치마크 스크립트의 `MODELS` 리스트에서 제거. minimax-m3를 큰 컨텍스트 task에 계속 쓰려면 프롬프트를 청크로 쪼개는 방식 검토.

- **D78** ([`TRACK_AB_BENCHMARK_RESULTS.md`](./TRACK_AB_BENCHMARK_RESULTS.md)) — D73의 "deepseek-v4-pro 접근 불가" 결론을 정정하고 세 벤치마크(Track A/B, benchmarks/grading, benchmarks/meas02) 통합 결론 작성
  - WHY: 사용자가 "분당 40회를 다른 세션에서도 호출해서 막힌 거 아니냐"고 직접 반증 가설을 제기 — 격리 단독 호출로 재테스트하니 즉시 성공(D73 당시엔 Track A→B 연속 실행 직후라 일시적 쿼터 소진이었을 가능성이 높음, 영구 접근거부 아님). "즉시 429=접근불가"로 성급히 결론 내렸던 게 틀렸다는 걸 인정하고 정정 섹션을 문서 최상단 가까이에 추가.
  - COST: D73 시점의 원래 표는 지우지 않고 그대로 둔 채 정정 섹션을 뒤에 추가하는 방식을 택함 — 문서를 처음부터 끝까지 안 읽으면 정정 전 결론(표)만 보고 오해할 위험이 남음.
  - EXIT: 문서가 더 길어지면 원래 표 자체를 정정된 숫자로 덮어쓰고 "최초 관측값은 git history 참고"로 각주 처리.

- **D79** ([`benchmark_track_a.py`](./benchmark_track_a.py), [`benchmark_track_b.py`](./benchmark_track_b.py) 관련 산출물) — 사용자 요청("부실했던 부분 채워 넣어")으로 Artifact의 deepseek-v4-pro 완전제외·mistral-large-3 Track B 빈칸을 실제 재호출로 채워 6모델→7모델로 확장
  - WHY: D78의 정정(deepseek-v4-pro는 접근불가가 아니라 일시적 쿼터 소진)을 문서 텍스트로만 남기지 않고, 실제로 이 모델을 Track A(`gq.build_prompt`+Depth Ladder 스키마)·Track B(자체 채점 프롬프트) 양쪽 방법론으로 재호출해 진짜 비교 가능한 데이터를 얻었다. mistral-large-3도 Track B(4답변×3회, `call_with_retry`로 최대 3회 자동재시도)를 재호출해 "쿼터 소진" 유령 막대를 실제 수치로 교체했다.
  - COST: deepseek-v4-pro Track A/B(24건)·mistral-large-3 Track B(12건) 추가 호출 비용 발생. deepseek-v4-pro는 두 트랙 다 qwen 다음으로 느림(34.6s/28.1s)이 확인돼 "빠른 대안 후보" 목록에선 제외해야 함이 명확해짐.
  - EXIT: 차트 데이터는 `track_a_summary.json`/`track_b_summary.json`(7개 모델)에 최종 반영, 원시 호출 로그는 `deepseek_track_a.json`/`deepseek_track_b.json`/`mistral_large_track_b.json`(gitignore됨, 재실행으로 regenerate 가능).

- **D80** ([`benchmark_track_a_multilang.py`](./benchmark_track_a_multilang.py), [`track_a_multilang_results.json`](./track_a_multilang_results.json)) — Track A(질문생성)를 D74~D76 다국어 corpus(Python/Java/JS/C·C++)로 처음 재현(사용자 질문: "JS/TS에서 이긴 모델이 다른 언어에서도 이기나?" — 지금까지 SURVEY_RESULTS.md/D58/D61~D79 전부 JS/TS(Study-Match-/LMS)만 썼다는 게 이 세션에서 처음 확인됨)
  - WHY: 언어당 finding 2개(tier-b-risk 1개 + architecture-diffusion 1개, C/C++만 tier-b-risk가 아예 없어 대신 cognition-isolation 사용, D75/D76이 이미 문서화한 한계) × 6모델 × 1회 = 48콜로 1차 정찰. `feedback/generate_questions.py`의 `build_prompt`/`DEPTH_LADDER_TOOL`을 그대로 재사용(별도 프롬프트 재구현 없음).
  - **확정 결과(전체 8×6=48건, 429 오염 전부 실제 값으로 교체 완료)**: **`qwen3-next-80b-a3b-instruct`(현재 locked 기본값)/`step-3.5-flash`/`llama-4-maverick`/`deepseek-v4-pro`/`mistral-large-3`, 5개 모델이 4개 언어 전부 8/8 성공(정밀도 100%)** — JS/TS에서 검증된 스키마 준수가 다른 언어에서도 그대로 유지됨을 처음 확인. 유일한 진짜 결함은 **`gpt-oss-120b`가 javascript·c_cpp에서 실패(각 50%)** — tool_choice를 안 지키고 자유서술로 응답(에러 메시지 확인, 429 아님) — D66/artifact가 이미 지적한 채점 재현성 결함이 질문생성 스키마 준수에서도 언어 의존적으로 재현됨. 속도는 언어 무관하게 일관됨: qwen(37.5~50.7s)·deepseek(33.9~57.0s)이 여전히 최하위권, 나머지는 전 언어에서 3~8s대.
  - COST: **1차 측정에서 `mistral-large-3`가 8건 중 5건 지속적 HTTP 429였던 건 실제 결함이 아니라 완전한 오탐이었음이 재시도로 확정됨** — 최종 데이터는 4개 언어 전부 100%로, 다른 상위권 모델과 동일하다. 근본 원인을 코드로 확인: `feedback/nvidia_client.py:27-33`의 `chat()`은 429 시 "풀에서 다음 키로 재시도"하도록 설계돼 있는데(`max_retries=3`), 이건 팀 전체 키 풀(`.env.example`이 `NVIDIA_API_KEY_1`~`_7`, 7명분 가정)을 전제로 한 설계다. 이 세션은 개인 키 1개만 `NVIDIA_API_KEY_1`로 썼으므로 429 시 "다음 키"가 사실상 같은 키라 재시도가 매번 즉시 같은 429로 끝났다(1차 실패 응답 전부 0.5~0.7초 — 재시도 3회가 전부 즉발 실패했다는 신호). deepseek-v4-pro/mistral-large-3 같은 대형 flagship 모델은 무료 티어에서 40rpm보다 엄격한 한도가 걸려있는 것으로 보이나, **시간(수십 분)이 지나자 같은 키로도 전부 성공** — 즉 영구적 차단이 아니라 일시적 소진이었다(같은 교훈이 D11/artifact "정정됨"/"채워짐" 항목에서 반복 확인된 패턴). 표본이 언어당 2건뿐이라 재현성(D9/D61식 반복측정)은 안 봤음 — 이건 "대략적 방향성 정찰"이지 확정 벤치마크가 아니다.
  - EXIT: 재현성까지 보려면 `REPEATS`를 3으로 올려 재실행(같은 429 리스크 있으니 팀 키 풀을 여러 개 확보해두면 대기시간 없이 바로 됨). `gpt-oss-120b`의 javascript/c_cpp 실패가 우연인지 일관된 패턴인지 확인하려면 그 두 언어만 finding을 늘려 재측정.

- **D82** (아티팩트, [`track_a_multilang_results.json`](./track_a_multilang_results.json)) — 사용자가 아티팩트에서 "mistral-nemotron이 아직도 429로 뜬다"고 지적 → 실제로는 D80이 이 모델을 애초에 `MODELS` 리스트에서 빠뜨렸던 것(6모델 중 mistral-nemotron 없음)인데, 아티팩트 렌더 코드가 "데이터 없음"과 "429 미확정"을 구분 안 하고 둘 다 같은 회색 "429" 칸으로 표시해서 마치 재시도로도 안 풀린 진짜 429처럼 보였다
  - WHY: `langBench` 객체에 `mistralai/mistral-nemotron` 키 자체가 없는데, 히트맵 렌더 함수는 `MODEL_ORDER`(7개, Track A/B용 범례에서 온 목록) 전체를 순회하면서 `langBench[m]`이 없으면 무조건 "429/미확정" 라벨을 붙였다 — "이 모델은 테스트를 안 했다"와 "테스트했는데 레이트리밋으로 못 채웠다"가 코드상 구분이 안 됐던 게 근본 원인
  - COST: mistral-nemotron을 실제로 4개 언어 × 1회 = 8콜 재실행해 확정 데이터를 얻었다(전부 100%, 5.6~6.9s — 다른 상위권 모델과 동일하게 안정적). fallback 라벨도 "429/미확정" → "—/미실행"으로 수정해 앞으로 같은 부류의 "누락을 오탐으로 보이게 하는" 표시 오류를 방지
  - EXIT: 지금은 7개 모델(qwen3-next-80b/step-3.5-flash/llama-4-maverick/deepseek-v4-pro/gpt-oss-120b/mistral-large-3/mistral-nemotron) 전부 `langBench`에 실측값이 있다. 새 모델을 히트맵에 추가할 때는 `MODEL_COLOR`/`MODEL_SHORT`뿐 아니라 `langBench`에도 반드시 같이 추가해야 함 — 하나만 빠뜨리면 이번과 같은 오탐성 "429" 표시가 재발한다.

- **D83** ([`~/.claude/hooks/scripts/nvidia-keypool-guard.py`](https://github.com/) 전역 설정, repo 밖) — D81에서 만든 nvidia-keypool-guard hook의 오탐 3건을 실사용 중 발견해 즉시 수정
  - WHY: hook이 "이 명령이 NVIDIA API를 벌스트 호출하는가"를 command 텍스트의 파일명/키워드 매치로만 판정하다 보니, (1) `head`/`grep`으로 `benchmark_track_b.py`를 그냥 읽기만 해도 차단, (2) `cd ...\nhead ...` 같은 멀티라인 명령에서 개행이 구분자로 인식 안 돼 단일라인에서만 통과, (3) `kill`/`pkill`로 이미 떠 있는 벤치마크 프로세스를 죽이려는 것까지 "실행 시도"로 오판해 차단 — 셋 다 이번 세션에서 실제로 겪은 뒤 즉시 고침
  - COST: 읽기전용/프로세스관리 도구 allowlist(`head/cat/grep/less/tail/wc/sed/awk/kill/pkill/ps/pgrep`)를 하드코딩했다 — 목록에 없는 새로운 읽기전용 도구(예: `bat`, `rg`)를 쓰면 다시 오탐 가능. `\bpython3?\b` 유무로 "진짜 실행"을 판별하는 것도 완벽하진 않음(예: `python3 -c "print('benchmark_track_a')"`처럼 실행이지만 무관한 경우도 걸릴 수 있음)
  - EXIT: allowlist에 없는 도구로 오탐 재발 시 `READ_ONLY_TOOLS`/`PROC_MGMT_TOOLS` 튜플에 추가. `has_python_exec` 판정이 근본적으로 부족하면 "실제 API 호출까지 가는가"를 더 정확히 보려면 명령이 실제로 `.chat(`/`client.chat`을 실행 경로에서 도달하는지까지 AST 분석해야 하는데, 그건 이 hook의 비용 대비 과함(지금 휴리스틱으로 충분).

- **D84** ([`benchmark_track_ab_multilang.py`](./benchmark_track_ab_multilang.py)) — Track A(질문생성)+Track B(채점)를 언어별로 동시 확장하는 스크립트 작성(336콜: Track A 8find×7model×3rep + Track B 8item×7model×3rep) — **D86에서 실행 20/336에서 중단됨, 이유는 D86 참고**
  - WHY: 사용자 요청 "언어별 Track A,B 진행한 표를... 3축(정밀도/재현성/속도)". Track A는 D80의 기존 8개 finding을 REPEATS=3(재현성 측정 위해)으로 재실행, Track B는 언어당 finding 1개씩 골라 강/약 답변 쌍을 D71/D72와 같은 방식(실제 코드 확인 후 근거있는 강한 답변 vs 얕은 약한 답변)으로 신규 작성 — Python(Enum 기반 endpoint), Java(placeholder API_KEY), JS(테스트파일 오탐), C++(벤더링된 유닛테스트 프레임워크) 각각의 실제 코드를 재-clone해서 확인 후 작성
  - COST: 강/약 답변을 언어당 1쌍만 만들어서 "언어 자체의 난이도"가 아니라 "그 언어에서 뽑은 특정 finding의 난이도"에 가까움(D84 코드 주석에도 명시). 결과적으로 이 COST를 따지기도 전에 D86로 전면 재검토됨.
  - EXIT: 아래 D86 참고 — 이 스크립트 자체(Track A/B 호출 로직, 강/약 답변 데이터)는 재사용 가능하나, "무엇을 벤치마크할 것인가"의 단위 자체가 바뀌어야 함.

- **D86** (실행 중단, 방법론 재검토) — 사용자가 기획명세서 04시트("턴 상태기계") 원문을 직접 인용해 지적: 지금까지의 모든 Track A 벤치마크(SURVEY_RESULTS.md/D58/D61~D84 전부)가 스펙의 **적응형 상호작용**이 아니라 **단발성 7필드 생성 도구**(`feedback/generate_questions.py`의 `DEPTH_LADDER_TOOL`)를 테스트해온 것이었음을 발견 → D84 실행분(20/336 진행 중) 즉시 중단
  - WHY: 스펙 04시트 R30C5 턴 상태기계 원문(사용자 인용): Decision Point 하나당 "① 코드종속 질문(파일·함수명 삽입) → ② 답변 즉시평가 → ③ 표면/부분/방어 분류 → ④ 방어 아니면 L2(트레이드오프) 반례 → 실패시 L3(극단 시나리오) → ⑤ L3도 실패시 Self Reflection 유도+확인질문 → ⑥ depth/시간 상한 또는 방어 성공시 다음 DP"라는 **학생 답변에 반응하는 적응형(최소 1턴~최대 4턴) 루프**를 요구한다. 반면 `generate_questions.py`는 finding 메타데이터만 보고 학생 답변 없이 7필드를 한 번에 다 생성 — 이건 애초에 스펙이 말하는 "질문 생성 방식" 자체가 아니라 "질문 후보 뱅크 생성기"에 가깝다. 실제로 스펙에 가까운 적응형 분기 로직은 별도로 존재한다: `pipeline/followup_generator.py`(D48)가 학생 첫 답변을 `isolation_classifier`/`reflection_signal`(정규식 기반)로 분류해 5개 사전작성 템플릿 중 하나를 고르고, `pipeline/escalation_hook.py`(D50)가 성공판정을 재귀 반영하는 구조 — 그런데 D48 스스로 COST에 "진짜 LLM 기반 적응형 질문은 아니다, 규칙기반 적응형(고정 분기 트리에서 사전정의 5방향 중 택1)"이라고 명시했고, D48 EXIT가 "API가 생기면 각 분기점에서 Codex/Claude를 호출해 문구를 매번 새로 생성하도록 교체 가능"이라고 이미 예고했던 업그레이드가 `generate_questions.py`가 실제 API를 호출하게 된 지금까지도 실행된 적이 없다.
  - COST: D58/D61~D84까지 쌓아온 "질문생성 모델 벤치마크" 전부가 프로덕션이 실제로 쓰는 학생-상호작용형 흐름이 아니라 그 앞단의 후보뱅크 생성 도구만 검증한 것이었다는 뜻 — 모델 선정(D58) 자체가 틀렸다는 건 아니지만(단발 7필드 생성 품질은 여전히 유효한 지표), "이 모델이 적응형 압박 루프에서도 잘하는가"는 전혀 검증된 적이 없다. 진행 중이던 336콜(D84)의 20건은 유효한 데이터지만 나머지 316건을 계속 쌓는 건 잘못된 단위를 검증하는 데 API 예산을 더 쓰는 것이라 판단해 즉시 중단.
  - EXIT: 사용자 결정(2026-07-07) — (1) D48/D50을 D48 EXIT가 예고한 대로 규칙기반 템플릿→실제 LLM 생성으로 업그레이드하는 걸 먼저 하고, (2) 그 다음에 스펙의 턴 상태기계(①~⑥)를 실제로 재현하는 적응형 벤치마크를 새로 설계한다. 두 단계 다 아직 미착수 — 다음 세션/다음 작업 단위.

- **D87** ([`feedback/turn_engine.py`](./feedback/turn_engine.py)) — D86 EXIT (1)단계 실행: D48 EXIT가 예고한 업그레이드("각 분기점에서 Codex/Claude를 호출해 문구를 매번 새로 생성, 분기 로직은 그대로 재사용")를 실제로 구현해 스펙 04시트 6단계 턴 상태기계를 처음으로 재현
  - WHY: `pipeline/followup_generator.py`(D48)/`escalation_hook.py`(D50)는 답변 분류+분기는 하지만 질문 텍스트가 5개 고정 템플릿 중 하나이고 에스컬레이션이 1단계뿐이었다(L2/L3/reflection 없음). `turn_engine.py`는 `run_decision_point()`로 L1(코드종속 질문, `judgment/idiom_filter.py`의 `_find_file_content`를 재사용해 **실제 파일 소스**를 프롬프트에 포함 — 기존엔 파일명뿐이었고 실제 코드 내용을 보여준 적이 없었음) → 분류(표면/부분/방어) → L2(트레이드오프) → L3(극단시나리오) → reflection까지 최대 4턴을 실제로 오케스트레이션하고, 매 레벨의 질문을 `ask_question` 툴로 강제한 LLM 호출로 새로 생성한다(고정 템플릿 재사용 없음). `classify_answer()`는 D48 EXIT의 "분기 로직은 그대로 재사용" 원칙대로 기존 `isolation_classifier`/`reflection_signal`(둘 다 confirmed 정규식 매칭, D6 계보)을 그대로 호출하고 그 출력을 3단계로 재해석만 한다.
  - **스모크테스트로 발견한 버그 2건(둘 다 즉시 수정)**: (1) `generate_questions.py`의 `parse_nvidia_tool_response()`가 툴 이름 `"depth_ladder_questions"`에 하드코딩돼 있어 새 `ask_question` 툴에 재사용 불가 — 항상 즉시 RuntimeError(모델은 정상 응답했는데 파서가 다른 이름만 찾음) → 전용 파서 `_parse_ask_question_response()` 신설. (2) `evaluate_reflection()`을 L1/L2/L3 답변 채점에 그대로 재사용하면 **강한 답변도 항상 "표면"으로 나옴** — 원인은 `self_error_recognition`(자기 오류 인정) 서브신호가 필수라서인데, 이건 reflection 단계(사후 반성)에만 의미 있는 조건이지 아직 반례 도전을 안 받은 L1/L2/L3 답변엔 안 맞는 기준이었다. `classify_answer(level=...)`로 분기해 reflection 단계에서만 원래 조건(필수+optional≥2)을 쓰고, L1~L3는 optional 서브신호 개수만으로 판정하도록 수정.
  - COST: **`feedback/reflection_signal.py`의 confirmed 패턴이 4개 서브신호 전부 0개임을 실측으로 확인**(`self_error_recognition`/`reason_explanation`/`new_judgment`/`concrete_improvement` 전부 candidate조차 없거나 0건) — 즉 tier-b-risk/repeated-pattern/architecture-diffusion 카테고리(4개 중 3개)는 지금 confirmed-pattern DB가 비어 있어 **어떤 답변을 넣어도 항상 "표면"으로만 분류**된다(L1~L3 기준으로 고쳐도 마찬가지 — optional 서브신호 자체가 하나도 confirmed 안 됐으므로). `judgment/isolation_classifier.py`(cognition-isolation 카테고리)만 confirmed 패턴이 있어(`role_separation`/`perf_optimization`/`domain_irrelevance` 각 1개, `alt_storage_or_scope`는 0개) 실제로 표면/부분/방어 3단계가 다 나온다 — 그래서 스모크테스트도 cognition-isolation finding(`cognition-isolation:allocatorstringstorage.h`, loki C++)으로 검증했다. 이건 새 코드의 결함이 아니라 이 저장소의 recursive-hook confirmed-pattern DB가 애초에 재현/일반화용 데이터로 충분히 안 쌓였다는, 이미 알려진(D21/D34/D37 계보) 콜드스타트 한계가 그대로 드러난 것.
  - **검증 결과(qwen3-next-80b, cognition-isolation:allocatorstringstorage.h)**: 약한 답변("잘 모르겠습니다, 그냥 그렇게 했습니다") 반복 → l1/l2/l3/reflection 전부 표면 판정, 4턴 전부 소진 후 `exhausted_at_cap`(25.3s). 강한 답변(위임+불필요 근거 포함) → L1에서 즉시 `defended`, 1턴만에 종료(3.6s). 에스컬레이션 로직이 답변 품질에 실제로 반응함을 확인. 생성된 L1 질문도 실제 코드 심볼(`AllocatorStringStorage`, `SimpleStringStorage<E, A>::emptyString_` 등)을 인용 — `pipeline/evidence_bridge.py`의 고정 템플릿(`DEPTH_LADDER_OPENING`)보다 질적으로 다름.
  - EXIT: 7모델 전체 벤치마크(D86가 미룬 다음 단계)를 돌리기 전에, reflection_signal의 confirmed 패턴을 최소한으로라도 채워야 risk-type 카테고리에서도 의미 있는 표면/부분/방어 분리가 나온다 — 안 그러면 그 3개 카테고리는 항상 4턴 다 소진하는 결과만 나와서 "에스컬레이션이 답변에 반응하는가"를 검증할 수 없다. `pipeline/followup_generator.py`/`escalation_hook.py`는 삭제하지 않고 API 없을 때의 폴백 경로로 남겨둠(원래 D48 설계 의도 그대로).

- **D88** ([`feedback/reflection_patterns/*/patterns.json`](./feedback/reflection_patterns/)) — D87 EXIT 실행: `reflection_signal`의 confirmed 패턴을 D51/D52가 확립한 절차(독립 리뷰어 → `record_feedback` → `recursive_update`) 그대로 채움 — 임의로 confirmations를 조작하지 않음
  - WHY: D87이 발견한 대로 4개 서브신호 전부 confirmed 패턴이 0개(candidate만 1개씩, threshold 3)라 risk-type 카테고리는 항상 "표면"만 나왔다. 이걸 정직하게 고치려면 "진짜 다른 출처(source_finding)의 독립 확인"이 threshold(3)만큼 쌓여야 한다(D51의 dedup 규칙) — 그래서 D74~D84에서 이미 확보한 4개 언어(Python/Java/JS/C++)의 실제 finding 각각에 대해, "약한 첫 답변 → L2/L3 반례 → 반성" 시나리오의 reflection 답변을 실제 코드 맥락에 맞게 새로 작성하고(예: Python은 Enum의 등록되지 않은 엔드포인트 처리 누락, Java는 placeholder API_KEY의 배포 시 검증 부재, C++는 벤더링된 라이브러리를 자체 설계로 오인, JS는 테스트 파일을 프로덕션 코드로 오인), 4개 답변 전부를 **codex-judge(독립 에이전트, 이 세션과 무관)**에게 4개 서브신호 각각에 대해 엄격하게(스스로 판단하지 않고) 검증받았다(16개 판정 요청, 실제 정확한 문구 인용 요구).
  - **실제 매칭 결과**: 판정받은 evidence_phrase가 아니라 답변 원문 전체를 기존 regex로 재검사해 실제 매치 여부를 코드로 직접 확인(judge의 판정을 그대로 믿지 않고 regex 매치는 별도 검증) — `self_error_recognition`: `too_trusted_browser`(너무\s*신뢰했) 2건, `naive_assumption`(안일하게\s*생각) 2건 → 각각 기존 1+신규 2=3으로 threshold 도달, **둘 다 confirmed 승격**. `reason_explanation`: `so_connector`(그래서) 4건 전부 매치 → 1+4=5, **confirmed 승격**. `new_judgment`: `now_looking_back`(지금\s*보니) 4건 전부 매치 → 1+4=5, **confirmed 승격**. `should_do_pattern`(해야\s*합니다)는 1건만 매치(어미가 "해야 한다고 생각합니다"라 정확히 안 걸린 케이스가 3건) → 1+1=2, **아직 candidate**(threshold 미달, 정직하게 승격 안 시킴). `concrete_improvement`는 기존 2개 패턴(`backend_limit_pattern`/`sanitize_pattern`)이 전부 특정 finding에 종속된 문구라 새 답변과 매치 자체가 안 됨 → 신규 패턴 `concrete_action_verb`(추가해야|확인해야|개선해야)를 4건 전부 매치로 새로 만들어 곧바로 **confirmed**(threshold 첫 승격에 4/3).
  - **재검증**: `classify_answer()`로 이 4개 reflection 답변을 다시 채점한 결과 전부 `defended`(L1-style/reflection-style 둘 다), 대조군("그냥 그렇게 했습니다")은 전부 `surface` — risk-type 카테고리(tier-b-risk/architecture-diffusion 확인, repeated-pattern은 미검증)가 이제 실제로 표면/부분/방어 3단계를 구분한다.
  - COST: `should_do_pattern`은 여전히 candidate로 남음(정직하게 미승격) — "해야 합니다" 정확한 종결어미가 아니라 "해야 한다고 생각합니다" 같은 변형이 실제 반성 답변에 더 흔할 수 있다는 신호. 5개 신규/승격 패턴 전부 이번에 내가 직접 작성한 4개 답변에서 나온 것이라 표본이 여전히 작음(언어당 1건) — 진짜 다양성은 실제 학생 답변이 쌓여야 확보됨(D64/D84가 이미 반복 지적한 한계와 동일 계보). codex-judge 16개 판정이 전부 true(관대함 우려 — "엄격하게 판단하라"고 명시했음에도 100% 통과율)라 판정 신뢰도 자체는 낮게 잡아야 함, 그래서 judge의 evidence_phrase를 그대로 믿지 않고 regex 매치를 코드로 별도 재검증하는 절차를 거쳤다(judge 판정=verdict만 신뢰, 실제 매치 여부=코드가 별도 확인).
  - EXIT: `should_do_pattern`을 마저 승격하려면 "해야 한다고 생각합니다"류 어미까지 포괄하도록 정규식을 넓히거나(`해야\s*(합니다|한다고)`), 다른 출처에서 정확히 "해야 합니다"로 끝나는 반성 답변이 1건 더 나오면 자연히 넘어감. 7모델 벤치마크(D86/D87이 미룬 단계)는 이제 architecture-diffusion/tier-b-risk 카테고리에서도 의미 있는 에스컬레이션 데이터를 낼 수 있는 상태가 됐다.

- **D89** ([`benchmark_turn_engine_multilang.py`](./benchmark_turn_engine_multilang.py), [`TURN_ENGINE_BENCHMARK_RESULTS.md`](./TURN_ENGINE_BENCHMARK_RESULTS.md)) — D88 EXIT 실행: `turn_engine.py` 기준 7모델 벤치마크를 4개 언어 × risk-type/cognition-isolation 두 판정 경로에 걸쳐 처음으로 라이브 실행
  - WHY: D58~D85 전부가 단발성 후보뱅크 생성기만 테스트했다는 게 D86에서 드러났고, D87(turn_engine.py 구현)/D88(confirmed 패턴 콜드스타트 수정) 이후에도 이 둘을 실제 라이브 모델 호출로 검증한 적이 없었다(D87 스모크테스트는 qwen 1개×cognition-isolation C++ 1건뿐). risk-type 4언어(D85 `TRACK_B_PAIRS` 원문 재사용, 강한 답변에 트리거 문구 1개만 자연스럽게 보정) + cognition-isolation 4언어(신규 저작, 실제 클론 코드 확인 후 작성) 8개 finding × 강/약 스크립트를 API 비용 쓰기 전 `evaluate_reflection()`/`classify_justification()`으로 전부 오프라인 사전검증(2개 이상 confirmed 서브신호 매치=defended 확정)한 뒤에만 라이브 호출했다. REPEATS=1(하니스 최초 실행이라 1차 정찰).
  - **핵심 결과**: job 성공(112건 중 65건) 전부에서 **판정 결과 일치율 100%** — 강한 답변은 전부 `defended`, 약한 답변은 전부 `exhausted_at_cap`, 카테고리별(tier-b-risk 17/17, architecture-diffusion 18/18, cognition-isolation 30/30)·언어별(4개 언어 전부 100%)로 쪼개도 불일치 0건. **D88의 confirmed 패턴 콜드스타트 수정이 라이브 LLM 질문생성→분류→에스컬레이션 전체 파이프라인에서도 정확히 작동함을 처음 확인**. Job 성공률/속도는 모델별로 크게 갈림: `qwen3-next-80b`100%(55.1s, 가장 느림)/`step-3.5-flash`100%(9.3s)/`deepseek-v4-pro`75%(429 단일키 한도, D77/D78 기존 패턴 재현)/`llama-4-maverick`75%(3.5s)/`gpt-oss-120b`38%(tool_choice 미준수, D66/D80 기존 결함 재현)/`mistral-large-3`19%(429 단일키 한도)/`mistral-nemotron`0%(진단 호출로 원인 확인: NVIDIA 서버가 `"DEGRADED function cannot be invoked"` 반환 — 코드 문제 아니라 그 시점 NVIDIA 플랫폼 쪽 서빙 장애).
  - COST: REPEATS=1이라 반복 안정성(재현성)은 미측정. `repeated-pattern` 카테고리는 4언어 전부 finding 0건이라 이번에도 스코프 제외(`score_findings.py`의 `find_repeated_pattern_files()`가 Firebase 전용 `"onSnapshot"` 하드코딩이라 원천적으로 없음, 공유 판단 블록을 건드리는 별개 범위 큰 작업). 레벨별(L1/L2/L3/reflection) 정밀 스키마 준수율은 못 냄(`run_decision_point()`가 중간 레벨 실패 시 그때까지의 transcript를 버리고 예외를 던짐 — job 단위 성공/실패로만 집계). `nvidia-keypool-guard.py` 훅이 이번엔 발동 안 함(커맨드 텍스트 자체엔 flagship 모델명/`ThreadPoolExecutor`가 없고 모듈 내부에만 있어 훅의 정적 텍스트 탐지가 못 잡음 — D83이 이미 명시한 휴리스틱 한계와 같은 종류의 사각지대).
  - EXIT: 여러 API 키로 재검증하면 deepseek-v4-pro/mistral-large-3의 실제 job 성공률을 다시 잴 수 있음(지금 수치는 단일 키 한도 아티팩트). mistral-nemotron은 NVIDIA 플랫폼 상태가 복구되면 재실행. REPEATS를 늘려 반복 안정성까지 보려면 이 스크립트를 그대로 재실행하되 `FINDINGS` 리스트는 무수정 재사용 가능.

- **D90** ([`turn_engine_multilang_results.json`](./turn_engine_multilang_results.json), [`TURN_ENGINE_BENCHMARK_RESULTS.md`](./TURN_ENGINE_BENCHMARK_RESULTS.md)) — D89 EXIT 실행: 429로 실패한 job(deepseek-v4-pro 4건, mistral-large-3 13건)을 같은 단일 키로 순차 재시도(사용자 요청)
  - WHY: D89가 "여러 API 키로 재검증하면 실제 job 성공률을 다시 잴 수 있음"이라고 남긴 EXIT를, 새 키를 구하는 대신 우선 같은 단일 키로 시간을 두고 순차 재시도(모델별 순차 + 8초 간격, 최대 3라운드·라운드 사이 30초 대기, `NVIDIA_SINGLE_KEY_OK=1`로 `nvidia-keypool-guard.py` bypass)해 얼마나 회복되는지부터 확인했다.
  - **결과**: `deepseek-v4-pro`는 4건 전부 라운드 1에서 즉시 성공(75%→**100%**) — D77/D78이 이미 정정한 "즉시 429=접근불가 아니라 일시적 쿼터 소진" 패턴 재확인(D89 실행과 이 재시도 사이 문서 작성·커밋·아티팩트 갱신으로 자연스럽게 수 분 경과, 분당 슬라이딩 윈도우가 풀림). `mistral-large-3`는 13건 중 3건만 회복(19%→**38%**), 나머지 10건은 3라운드 내내 정확히 같은 job이 매번 0.4~0.7초 즉발 실패 — 응답시간이 0에 수렴하고 라운드를 거듭해도 안 풀리는 패턴은 분당 한도가 아니라 `nvidia-keypool-guard.py` 훅이 이미 기록한 "시간 단위로 추정되는 한도"(2026-07-07 최초 발견 당시 40~70분 소요)에 해당 — 이번 재시도는 총 10분이 채 안 걸려 애초에 그 한도가 풀리기엔 부족한 시간이었다. 성공 65→**72건**(112건 중)으로 늘었지만 판정 결과 일치율은 여전히 **100%**(신규 성공분도 전부 기대대로 defended/exhausted_at_cap).
  - COST: `mistral-large-3`의 38%는 여전히 단일 키·짧은 재시도 창 안에서 얻은 하한값이라 이 순위를 최종으로 인용하면 안 됨(D69/D77 원칙 재확인). `gpt-oss-120b`(tool_choice 미준수)·`mistral-nemotron`(서버 DEGRADED)은 429가 아니라 재시도로 해결될 성질이 아니라 대상에서 제외.
  - EXIT: `mistral-large-3`를 더 회복시키려면 (1) 40~70분 이상 대기 후 남은 10건만 재시도, 또는 (2) 팀 키 풀을 확보해 `NVIDIA_API_KEY_2`부터 추가(권장, 이 모델의 시간 단위 한도 자체를 우회 가능). 둘 다 이번 세션 범위 밖.

- **D91** ([`turn_engine_mistral_wait_log.json`](./turn_engine_mistral_wait_log.json)) — D90 EXIT (1)단계 실행: mistral-large-3 남은 10건을 5분 간격 90분 폴링으로 재시도(사용자 요청) — **가설 반증(negative result)**
  - WHY: D90이 "40~70분 이상 대기 후 재시도"를 EXIT로 남겼고, 사용자가 실제로 지금 그 대기를 해보자고 요청했다. 처음엔 55분 블라인드 대기 후 한 번에 몰아서 시도하는 스크립트를 짰으나, 사용자가 "정확한 회복 시점을 못 잡는다"고 지적 — probe job 1개로 5분마다 간을 보다가 성공하는 순간(대기시간)과 그 호출 자체의 처리시간(D90이 이미 분리 설계해둔 `elapsed_s`)을 별도 기록하도록 재설계했다(최대 90분 폴링, 회복되면 나머지 9건 자동 드레인).
  - **결과(반증)**: 18회 폴링(5분×18=90분) 전부 완전히 동일한 즉발 HTTP 429 — **단 한 번도 회복되지 않음**. `nvidia-keypool-guard.py` 훅이 기록한 "40~70분 뒤 재시도하면 풀린다"는 2026-07-07 관측 1건이 보편 법칙이 아니라 그날 그 순간의 특정 관측값이었을 가능성이 이번 실측으로 높아졌다. job 성공률은 38%(6/16)로 D90과 동일, 변화 없음.
  - COST: probe 호출 18회를 더 썼다(전부 실패). 90분의 실시간 세션 시간을 소요. "조금 더 기다리면 풀린다"는 가설에 대한 신뢰도가 낮아졌을 뿐 D89/D90의 경쟁 가설(클라이언트 시간단위 버킷 vs 서버 정책적 차단) 자체를 확정 짓지는 못했다 — 여전히 다중 키 동시 테스트만이 실제로 구분 가능(TURN_ENGINE_BENCHMARK_RESULTS.md "D-cause" EXIT 참고).
  - EXIT: 이 세션 기준 "같은 단일 키로 좀 더 기다려보기"는 반증된 접근이라 재시도 안 함. 다음은 (1) 완전히 다른 시간대(예: 다음날)에 짧게 재확인, 또는 (2) 팀 키 풀 확보(`NVIDIA_API_KEY_2`) 중 하나가 우선순위 — 후자가 이 모델의 근본 원인(시간단위든 정책이든)을 실제로 우회할 가능성이 더 높다.

- **D92** (문서만, 코드 무수정) — 원래 성공했던 요청 재전송(가설 C 반증) + 40rpm 준수 여부 재검토(사용자 질문 2건 연속)
  - WHY: 사용자가 (1) "원래 성공했던 요청 그대로 재전송해서 요청 형식 문제인지 보자", (2) "40 RPM 제한 준수해서 한 거 맞아?" 두 가지를 연달아 질문 — 둘 다 D89~D91이 세운 가설(시간단위 버킷/정책적 차단)을 당연시하지 않고 더 근본적인 원인(요청 자체 문제? 우리 쪽 설계 문제?)을 먼저 배제하려는 질문이었다.
  - **결과 1(재전송)**: 원래 성공했던 6건 중 `c_cpp:architecture-diffusion:UnitTest.h:strong`(원래 2.92초 defended)을 동일 payload로 재전송 → 즉발 429. 동일 payload가 전에는 통과했으니 "그 10건 요청의 형식 문제"(가설 C)는 반증됨 — 동시에 차단이 특정 10건이 아니라 모델+키 조합 전체로 번졌거나 유지되고 있다는 더 나쁜 신호.
  - **결과 2(40rpm 재검토)**: `feedback/nvidia_client.py`의 `chat()`을 재확인 — 429 시 **딜레이 0으로 즉시** 같은 키로 최대 3회 재시도(D56 vendored 코드, 이번에 새로 만든 게 아님). `run_decision_point()`는 실패 시 첫 레벨에서 바로 예외를 던지므로, **실패 job 1개 = 실제 HTTP 요청 최대 3회**. 원래 D89 실행을 이 배율로 재추정하면 `mistral-large-3`≈최대 39회, `deepseek-v4-pro`≈최대 36회로 **둘 다 40rpm 턱밑**이었다 — `max_workers=6` 동시성과 겹쳐 연쇄 실패 구간에서 순간 처리율이 40rpm을 실제로 넘었을 가능성이 높다. 즉 최초 429 폭주는 외부 요인이 아니라 **이 벤치마크 자신의 동시성+무백오프 재시도 설계가 자초했을 가능성**이 새로 발견됨.
  - COST: 두 결과 다 이 세션 데이터로 재구성한 추정이지 HTTP 요청 타임스탬프 실측은 아니다(계측 안 해둠). 또한 "왜 걸렸는가"(자초한 버스트)는 설명해도 "왜 deepseek는 몇 분 만에 풀리고 mistral-large-3는 90분+에도 안 풀렸는가"(회복 시간 차이)는 여전히 설명 못함 — 두 모델 다 비슷하게 한도 근처였는데 회복은 갈렸으므로 모델별 정책 차이(D89 "D-cause" 가설 A/B) 자체는 여전히 미해결.
  - EXIT: (1) `nvidia_client.py`의 429 재시도에 지수 백오프 추가(vendored 코드라 원본 nvidia-build repo 우선 수정 후 재동기화 필요, D56 원칙) — 다음 벤치마크의 자초 버스트를 줄임. (2) `call_one()`에 실제 HTTP attempt 타임스탬프 계측 추가 — 다음엔 추정 아닌 실측 가능. 둘 다 핵심 오케스트레이션/vendored 코드 무수정 원칙과 상충해 이번 세션 범위 밖, 별도로 다룰 사안.

- **D93** ([`benchmark_turn_engine_grading_multilang.py`](./benchmark_turn_engine_grading_multilang.py), [`TURN_ENGINE_GRADING_BENCHMARK_RESULTS.md`](./TURN_ENGINE_GRADING_BENCHMARK_RESULTS.md)) — Track A(질문생성)+Track B(FR-04-01 5축 채점)+turn_engine 적응형을 처음으로 통합(사용자 요청: "지금 셋이 따로 노는 OR 상태다, AND로 합쳐라")
  - WHY: D89~D92는 turn_engine을 4언어×7모델로 돌렸지만 job 성공률/속도(Track A 성격)만 쟀다. Track B(5축 LLM-as-judge, `llm_interview_grader.py`)는 turn_engine과 결합된 적이 없고 애초에 4언어로 재실행된 적도 없었다(D80이 재실행한 건 Track A뿐). D89의 strong/weak 답변(8 findings, 재사용)에 **improving(신규)** 스크립트를 추가 — L1~L3는 weak 재사용, reflection 단계에서만 진짜 자기수정 답변으로 교체(risk-type 4건 신규 저작+오프라인검증, cognition-isolation 4건은 D89 strong 텍스트 재사용, `classify_answer()`가 레벨 무관 분류라 가능). `turn_engine._transcript_text()`(무수정)로 포맷한 전체 transcript를 `grade_answer()`에 전달, 같은 모델이 자기 transcript를 채점(기획명세서 확정 결정 그대로). 8 findings×3 scripts×7 models=168 job, 사용자 확인 하에 축소 없이 전체 진행.
  - **핵심 결과**: 판정 결과 일치율 100%(D89와 동일 재확인). **자기수정 인식이 명확히 갈림** — 데이터 있는 4개 모델 전부 improving(2.38~3.67)이 weak(1.00~1.12)보다 뚜렷이 높고, 다른 축을 인플레이션 안 하고 자기수정 축만 선택적으로 높이는 사례가 흔함(qwen 스모크테스트: 자기수정=4, 나머지=1~2). Track B 정밀도(strong>weak 비율)는 llama-4-maverick/deepseek-v4-pro 100%, qwen 75%(cognition-isolation 2건만 strong=weak=1.00으로 미달, 원인 미확정).
  - **신규 발견**: `step-3.5-flash`/`llama-4-maverick`에서 **Track B 5축 채점 도구 호출 시 tool_calls는 왔지만 arguments가 깨진 JSON**인 실패 모드를 처음 확인(gpt-oss-120b식 "자유서술로 응답"과 다른 유형 — 도구는 호출했는데 인자 문자열 자체가 파싱 불가). `llm_interview_grader.py` D63 COST가 예견했던 "5축 스키마가 커서 tool-calling 실패율이 오를 수 있다"가 실측으로 확인됨. `mistral-nemotron`은 이번엔 HTTP 500(D89 때는 400 DEGRADED) — 증상은 다르지만 서버측 가용성 문제라는 결론은 동일.
  - COST: 실행 시점이 D89/D91과 달라 job 성공률이 전반적으로 낮음(deepseek 42%, gpt-oss 21%, nemotron 13%, mistral-large-3 0% — D91이 확인한 차단 지속). REPEATS=1이라 재현성 미측정. gpt-oss-120b/nemotron/mistral-large-3는 성공 표본이 너무 적어(5/3/0건) Track B 지표를 못 냄(n/a 정직 표시). JSON 파싱 실패의 원본 malformed 응답을 로깅 안 해둬 정확한 재현조건 미확정.
  - EXIT: `call_one()`에 raw tool-call arguments 문자열 로깅 추가하면 JSON 파싱 버그 근본원인 확정 가능. qwen의 cognition-isolation 2건 미달 원인 조사 후보. REPEATS 늘려 재현성 측정은 여러 키 확보 후.

- **D94** ([`benchmark_turn_engine_grading_16models_sonnet.py`](./benchmark_turn_engine_grading_16models_sonnet.py), [`retry_16models_sonnet_40rpm.py`](./retry_16models_sonnet_40rpm.py), [`turn_engine_grading_16models_sonnet_summary.json`](./turn_engine_grading_16models_sonnet_summary.json)) — D93(7모델)을 16개 후보 전체로 확장 + 답변 생성 방식을 고정 텍스트에서 Sonnet 실시간 생성으로 교체(사용자 요청 2건: "16개 후보로 확장", "턴 상태기계 질의응답에서 답변은 Sonnet이 진행")
  - 공유 링크(GitHub Pages): https://popixoxipop-collab.github.io/Code_reviewer_with_feedback/
  - WHY: NVIDIA Build 실제 카탈로그(`/v1/models`, 121개)를 라이브 재조회해 16개 후보(검증 7 + 신규 9: glm-5.2/kimi-k2.6/minimax-m3/qwen3.5-122b-a10b/mistral-medium-3.5-128b/llama-3.3-nemotron-super-49b-v1.5/nemotron-3-super-120b-a12b/llama-3.3-70b-instruct/gpt-oss-20b)를 확정했다(제외 105개 카테고리 크기가 설명과 정확히 일치함을 확인 — 임베딩11/비전15/안전7/번역4/코드전용3/도메인5/초대형4/구형·극소형56). D93까지 강/약/improving 답변이 전부 미리 써둔 고정 텍스트였는데, `turn_engine.run_decision_point()`의 `answer_fn` 시임(D87이 이미 "실제 세션이면 학생에게 묻는 함수로 교체 가능"이라 문서화해둔 지점)에 `claude -p --model sonnet --safe-mode` 서브프로세스 호출을 꽂아 매 턴 페르소나(강하게 방어/얼버무림/reflection 단계에서만 진짜 자기수정)에 맞춰 실시간 생성하도록 교체했다(3-조건 구조는 유지 — Track B 정밀도/자기수정 지표 계산이 이 구조에 의존하므로). `--safe-mode`는 이 머신의 무거운 전역 CLAUDE.md+수십개 MCP서버 로딩 없이 OAuth 인증만 재사용 — 일반 `claude -p`가 트리비얼한 호출에도 2분+ 걸리는 걸 실측 확인, safe-mode는 3.5초.
  - **실행 결과**: 1차 실행(단일 키 + 동시성6, 무제한 순간 처리율) 384job 중 101건(26%) 성공. D92가 이미 진단한 "무백오프 재시도+동시성이 40rpm을 자초한다"를 이번엔 코드로 직접 검증 — 실패분(kimi-k2.6의 HTTP404 24건 제외 259건)만 전역 30rpm 슬라이딩윈도우 레이트리미터(vendored `nvidia_client.py` 무수정, 얇은 래퍼로만 게이팅) + 동시성4로 재시도해 43건 회복, 최종 144/384(38%) 성공. 레이트리밋이 진짜 원인이었던 모델은 크게 회복(minimax-m3 21%→71%, mistral-medium-3.5 67%→96%, llama-4-maverick 63%→88%, deepseek-v4-pro 17%→42%) — D92 진단이 실측으로 확인됨. 신뢰 가능한 표본(20건+/24)은 qwen3-next-80b/step-3.5-flash/mistral-medium-3.5/llama-4-maverick 4개뿐.
  - **방법론적 발견**: Sonnet이 생성한 reflection 답변은 내용상 진짜 자기수정이어도 `reflection_signal.py`의 confirmed 정규식과 정확히 안 맞아 `verdict_matches_expected_rate`(정규식 판정)는 30~40%대로 낮지만, 같은 transcript를 채점하는 LLM-as-judge(`grade_answer`)는 자기_수정 축을 4.5~5.0/5로 정확히 인식했다 — 정규식 채점기의 표현취약성(D34/D37/D87 계보)이 실시간 생성 답변에서도 재현되고, LLM-as-judge 경로는 이 한계에 안 걸린다는 걸 독립 데이터로 재확인.
  - **재시도로도 안 풀린 원인 진단(사용자 요청, D94 후속)**: `llama-3.3-70b-instruct`(24건 전부 "read timed out")와 `nemotron-super-49b-v1.5`(23/24 HTTP500)를 raw urllib으로 직접 진단 호출(vendored client 우회, 응답 body 직접 확인). **llama-3.3-70b-instruct는 모델 결함이 아니다** — 진단 1회차가 124.7초 만에 HTTP 503 `"ResourceExhausted: Worker local total request limit reached (153/16)"`을 반환(NVIDIA 서버가 직접 명시한 워커 큐 과부하), 2회차는 188초 만에 정답 반환 — client 기본 타임아웃(`nvidia_client.py`의 `timeout_s=120.0`)이 지금 이 모델의 실제 지연시간보다 짧을 뿐, 재시도로 해결 안 되는 시간대 의존적 부하 문제(D91의 mistral-large-3 계보와 유사하나 원인이 다름 — 그쪽은 계정/모델 단위 차단, 이쪽은 워커 큐 과부하). **nemotron-super-49b-v1.5는 reasoning 모델**이라는 게 진단으로 확인됨 — `max_tokens`가 작으면 내부 chain-of-thought(`reasoning_content` 필드)를 다 못 쓰고 `finish_reason:"length"`로 끊겨 `content:null`을 반환한다(진단 3회 전부 재현). turn_engine의 `generate_question()`이 쓰는 `max_tokens=512`가 이 모델의 reasoning 트레이스엔 부족해서 tool-calling 응답이 깨지는 것으로 추정(정확한 재현은 tool_choice 강제 조건에서 직접 확인 필요 — 이번 진단은 일반 chat만 확인).
  - COST: 재시도로도 회복 안 된 원인 진단은 위 2개 모델에 한정(나머지 6개: gpt-oss-120b/gpt-oss-20b는 tool_choice 미준수로 D66/D80/D89 계보와 동일해 재진단 불필요, mistral-nemotron/mistral-large-3/kimi-k2.6/glm-5.2는 미진단). REPEATS=1(재현성 미측정).
  - EXIT: `llama-3.3-70b-instruct`는 다른 시간대 재시도나 client timeout을 200s+로 늘리면 회복 가능성 높음(진단으로 확인된 워커 과부하가 상시가 아닐 수 있음). `nemotron-super-49b-v1.5`는 `max_tokens`를 1500~2000 이상으로 늘려 재실행하면 reasoning 트레이스를 다 쓰고 tool call까지 도달할 가능성 있음 — 둘 다 사용자 확인 후 재실행 후보.

- **D95** ([`scripts/java_curriculum_nvidia_pipeline.py`](./scripts/java_curriculum_nvidia_pipeline.py), [`scripts/nvidia_keypool_traffic_test.py`](./scripts/nvidia_keypool_traffic_test.py), [`docs/JAVA_CURRICULUM_NVIDIA_PIPELINE.md`](./docs/JAVA_CURRICULUM_NVIDIA_PIPELINE.md)) — Java 교안 PDF를 10페이지 chunk로 나눠 NVIDIA Build 병렬 호출 + page provenance state + refine loop + graphify-compatible graph + graph-grounded question generation까지 구현.
  - WHY: Claude Workflow에 남아 있던 Java 교안 분석 흐름을 repo에서 재실행 가능한 코드로 고정했다. `NVIDIA_API_KEY_1..N` 로테이션은 기존 `feedback/nvidia_key_pool.py`와 동일한 sliding-window acquire path를 사용하며, 새 wrapper는 키 값 없이 slot별 사용량과 60초 최대치를 `rate_audit.json`에 기록한다.
  - 검증: `docs/java_curriculum_pipeline_run_smoke/`는 실제 NVIDIA Build API로 3개 chunk를 처리해 2개 unit, 35개 concept/code/caution, 65 nodes/108 links graph, 4개 source-page 질문을 생성했다. `docs/java_curriculum_pipeline_rate_smoke/keypool_traffic_test.json`은 로컬 traffic test에서 7 keys × 40RPM = 280개를 같은 60초 창에 즉시 예약하고 281번째를 `KeyPoolExhausted`로 차단함을 확인했다.
  - COST: 251페이지 전체 실행은 NVIDIA 모델/서버 지연과 JSON 응답 안정성에 막혔다. `qwen/qwen3-next-80b-a3b-instruct`는 저병렬에서 대부분 chunk를 처리했지만 refine JSON 파싱 실패로 중단됐고, 고병렬에서는 504/timeout이 발생했다. 즉 현재 병목은 로컬 40×7 RPM 게이트가 아니라 모델 서빙 지연·응답 형식 안정성이다.

- **D96** ([`fix_quota_contaminated_results.py`](./fix_quota_contaminated_results.py)) — D94b 재실행 결과가 Claude 구독 주간 사용량 한도 소진으로 오염된 걸 발견하고 바로잡음(사용자 요청: 원인 파악)
  - WHY: D94b(다른 세션이 `rerun_two_models_fixed_settings.py`를 편집해 timeout/max_tokens를 조정한 버전)가 도는 도중 이 머신의 **Claude 구독 주간 사용량 한도**가 소진됐다. `claude -p --model sonnet --safe-mode`가 한도 초과 시 에러 종료 대신 `"You've hit your weekly limit · resets Jul 11 at 12pm (Asia/Seoul)"`을 stdout에 그대로 출력하는데, `_sonnet_call()`은 "비어있지 않은 문자열=유효한 답변"으로만 검사해서 이 문구를 학생의 실제 답변으로 그대로 받아들였다.
  - **발견 경위**: D94b 커밋(`939b812`)이 nemotron-super-49b-v1.5 job_success=95.8%(23/24), llama-3.3-70b-instruct=12.5%(3/24)로 "회복"됐다고 보고했으나, 실제 grading을 열어보니 **두 모델 다 강/약 답변 구분 없이 5축 전부 정확히 1.0점**이었다(만점 5점 척도의 최저값) — 이건 채점기가 고장난 게 아니라 "You've hit your weekly limit..."이라는 무의미한 텍스트를 정확히 최저점으로 채점한, 채점기가 정상 작동한 증거였다. transcript의 answer 필드를 직접 열어 확인 후 확정. 이 오염된 데이터는 이미 origin/main에 push되고 GitHub Pages(https://popixoxipop-collab.github.io/Code_reviewer_with_feedback/)에 "95.8% 성공"으로 공개 노출된 상태였다.
  - **교정**: `fix_quota_contaminated_results.py`가 transcript의 answer 필드에서 "weekly limit"/"hit your"/"usage limit" 패턴을 검사해 오염된 job 26건(nemotron-super-49b-v1.5 23건 + llama-3.3-70b-instruct 3건, 즉 두 모델의 "성공" job 전부)을 `ok=False`로 되돌리고 `error` 필드에 원인을 명시(조용히 삭제하지 않고 감사 가능하게 남김). 나머지 14개 모델은 오염 없음을 전수조사로 확인(오염 마커 매치 0건) — 재계산 결과 전체 성공률이 원래의 144/384(38%)로 정확히 복원됨. `docs/d94-rerun-status.json`(GitHub Pages가 fetch로 읽는 파일)도 정정된 수치로 갱신.
  - **재발 방지**: `benchmark_turn_engine_grading_16models_sonnet.py`의 `_sonnet_call()`에 `QUOTA_EXHAUSTED_MARKERS` 가드를 추가 — 앞으로 이 문구가 나오면 빈 문자열과 동일하게 즉시 예외로 처리되어 벤치마크 데이터에 섞여 들어갈 수 없다.
  - COST: 두 모델은 이 교정으로 다시 사실상 0%(nemotron 0/24, llama-3.3-70b-instruct 0/24)로 돌아갔다 — D94b가 시도한 설정값 수정(timeout 확대/max_tokens 확대) 자체가 틀렸다는 뜻은 아니다. D94의 raw HTTP 진단(워커 큐 과부하 / reasoning 토큰 부족)은 여전히 유효한 원인 분석이고, 그 시도 도중 완전히 별개의 이유(계정 사용량 한도)로 검증 데이터가 못 쓰게 됐을 뿐이다.
  - EXIT: 주간 한도는 2026-07-11 12:00(Asia/Seoul) 리셋 — 그 이후에 D94b(또는 동등한 timeout/max_tokens 조정)를 재시도하면 된다. `_sonnet_call()` 가드가 있으니 다음번엔 같은 방식으로 오염될 수 없고, 한도 소진 시 그 job은 정직하게 실패로 집계된다.

- **D97** ([`rerun_nemotron_only.py`](./rerun_nemotron_only.py)) — 주간 한도 리셋 후 nemotron-super-49b-v1.5를 실제로 회복시킴, llama-3.3-70b-instruct는 이번 라운드 보류(사용자 결정)
  - WHY: 사용자가 한도 리셋을 확인하고 재시도를 요청. llama-3.3-70b-instruct는 `timeout_s=600`으로도 첫 9개 job이 전부 302~766초 실패(워커 과부하가 하루 넘게 지속)해 시간 대비 실익이 낮다고 판단, 사용자가 이번 라운드는 보류하고 nemotron만 먼저 채우기로 결정.
  - **동시성 재검토(사용자 질문)**: `rerun_two_models_fixed_settings.py`가 `workers=1`(순차)로 설정돼 있었는데, 이건 llama-3.3-70b-instruct의 **워커 큐 과부하**(HTTP 503, D94에서 확정) 문제에 대한 방어적 캐치올이었지 nemotron의 문제(max_tokens 부족, 이미 해결됨)와는 무관했다. `RateLimitedClient`(D94 재시도에서 이미 만든 스레드세이프 슬라이딩윈도우 게이트)가 `workers=4`에서도 정상 작동함이 이전 재시도(D94, minimax-m3 등 회복)로 이미 검증됐으므로, nemotron 재시도는 `workers=4`로 바꿔 진행 — 순차 실행은 근거 없는 과잉 보수였다.
  - **모듈 재로딩 함정(신규)**: `rerun_nemotron_only.py`가 `rerun_two_models_fixed_settings.py`의 `call_one_with_tokens()`를 `importlib.util.spec_from_file_location`으로 재사용했는데, 이 함수가 내부적으로 참조하는 `d94.CLIENT`는 그 파일이 **자체적으로 다시 로드한 별개의 `d94` 모듈 인스턴스**였다(같은 소스 파일이라도 `module_from_spec`을 두 번 호출하면 서로 다른 객체) — 호출부에서 `d94.CLIENT`를 설정해도 반영이 안 돼 24/24가 `'NoneType' object has no attribute 'chat'`로 즉시 실패(0.0초). `rerun2.d94.CLIENT`처럼 대상 모듈 인스턴스에 직접 설정하도록 수정 후 정상화.
  - **실행 결과**: 1차(workers=1 잔재, timeout=300s) 21/24(88%, 실패 3건 중 1건은 300초 타임아웃). 2차 재시도(실패 3건만, workers=4, timeout=600s)로 2건 추가 회복 → **최종 23/24(95.8%)**. Track B 정밀도 1.0, 강한 답변 평균 5.0/약한 답변 1.32, 자기수정 인식 improving 4.5 vs weak 1.12로 뚜렷하게 분리 — D94 COST가 우려했던 "정규식 채점기 표현취약성"과 달리 이번엔 LLM-as-judge 경로가 잘 작동. 언어별로도 Python/Java/JS 6/6, C/C++ 5/6로 고르게 분포. 재오염 여부는 별도로 transcript 전수조사해 0건 확인.
  - COST: llama-3.3-70b-instruct는 여전히 0/24(보류) — 전체 성공률 165/384(43%)→167/384(43%, nemotron 회복분 반영). REPEATS=1 미측정은 동일.
  - EXIT: llama-3.3-70b-instruct는 워커 과부하가 진짜로 시간대 의존적인지(다른 시간대 재시도) 아니면 상시적인지 아직 미확정 — 다음 세션에서 재시도 여부는 사용자 판단.

- **D98** ([`timeout_config.py`](./timeout_config.py), `~/.claude/hooks/scripts/timeout-config-guard.py`) — 프로젝트 전체 타임아웃을 단일 중앙 설정으로 통합 + hook으로 재발 방지(사용자 요청: "타임아웃 600초로 하라"를 세 번 반복 지적한 뒤 "중앙 통제식으로 하자 hook에 걸어놓으라고")
  - WHY: D94b~D97에서 LLAMA_TIMEOUT_S/NEMOTRON_TIMEOUT_S/SONNET_TIMEOUT_S가 스크립트마다 따로 하드코딩되며 값이 어긋나는 일이 반복됨(즉석 진단 스크립트에도 `timeout=120`을 매번 새로 박아넣다 사용자에게 지적받음). `timeout_config.py`에 `DEFAULT_TIMEOUT_S = 600.0` 하나만 두고 `nvidia_client.py`(vendored, D56 예외 처리 — 사용자가 명시적으로 전역 기본값 요청) 및 모든 벤치마크/재시도 스크립트가 여기서 import하도록 통일.
  - **hook 설계**: `timeout-config-guard.py`(PreToolUse Write|Edit, `~/.claude/settings.json`에 기존 `data-first-guard.py` 옆에 등록)가 Code_reviewer_with_feedback 안의 `.py` 파일에서 `timeout_s=`/`timeout=`/`*TIMEOUT_S`/`*TIMEOUT` 패턴에 숫자 리터럴이 직접 대입되면 차단, `DEFAULT_TIMEOUT_S` 참조는 통과, `timeout_config.py` 자기 자신은 예외, `# timeout-guard: allow` 주석으로 개별 예외 가능.
  - **정규식 함정 2건(실측 발견)**: (1) 초안이 "숫자 하나를 `[^=]`로 미리 소비"하는 방식이라 남은 자릿수 앞에 `\b`가 안 걸려 `timeout_s=120.0` 자체를 통째로 놓침 — 값 전체를 파싱하지 않고 "대입 직후 숫자 존재"만 보는 것으로 교체. (2) `TIMEOUT_S`/`TIMEOUT` 패턴에 붙인 선행 `\b`가 밑줄은 `\w`라서 `SONNET_TIMEOUT_S`처럼 접두어가 붙은 상수를 못 잡음(D85 한글 조사 경계 문제와 동일 계열의 함정) — 선행 `\b` 제거, 후행 `\b`만 유지해 `TIMEOUT_STRING` 같은 무관한 이름 오탐만 막음. 10개 케이스(위반 4·정상 3·오탐방지 3) 전부 통과 확인 후 실제 Write 호출로 차단/통과 양쪽 다 실측 검증.
  - COST: 이 hook은 Code_reviewer_with_feedback 전용(다른 프로젝트 파일은 자동 통과) — 프로젝트 범위를 벗어나면 재적용 불필요.
  - EXIT: 값 자체를 바꾸려면 `timeout_config.py`의 `DEFAULT_TIMEOUT_S` 한 줄만 수정.

- **D99** (최종 정리) — llama-3.3-70b-instruct 최종 제외, 15/16 모델로 벤치마크 완료(사용자 결정: "16개 중 저 모델 하나만 호출 문제가 지속되는 거면 그걸 이유로 빼고 밴치마킹 표 완료해")
  - WHY: D97 이후 세 번째 재시도(workers=1, timeout=600s)도 11개 job 시점까지 2승 9패(18%)로 부진 지속. 웹조사로 NVIDIA 개발자 포럼에서 동일 에러 클래스("ResourceExhausted: Worker local total request limit reached")를 다른 모델(DeepSeek V4 Flash)에서도 겪은 스레드를 발견 — 커뮤니티 의견이 "로컬 설정 문제" vs "업스트림 워커 풀 고갈"로 갈리는데, 저희가 이미 확인한 사실(완전히 다른 7개 키로 동시 요청해도 4/7 실패)이 후자를 직접 뒷받침함. 공식 해결책 없이 미해결 상태로 남은, NVIDIA 쪽에서 이미 알려진 이슈로 확인됨(https://forums.developer.nvidia.com/t/resourceexhausted-worker-local-total-request-limit-reached-33-32/375518).
  - **최종 상태**: 16개 후보 중 15개 라이브 벤치마크 완료(167/384, 43%), llama-3.3-70b-instruct 1개는 원인 진단은 확정됐으나(NVIDIA 워커 큐 과부하, 외부 포럼 교차검증) 재시도로 회복 안 돼 최종 제외. 신뢰 가능한 표본(20건+/24) 5개: qwen3-next-80b/step-3.5-flash/mistral-medium-3.5/nemotron-super-49b-v1.5/llama-4-maverick.
  - COST: llama-3.3-70b-instruct는 이 벤치마크 세트에서 순위 데이터 없음(0/24로 표에는 남아있으나 "제외" 명시).
  - EXIT: 나중에 이 모델의 NVIDIA 쪽 상태가 나아지면(포럼 스레드가 언젠가 해결되면) `rerun_llama70b_only.py`(workers=1, timeout=600s 이미 준비됨)로 재시도 가능 — 코드는 남겨둠, 삭제 안 함.

- **D100** ([`docs/index.html`](./docs/index.html), [`docs/d94-rerun-status.json`](./docs/d94-rerun-status.json)) — "15/16 모델, 167/384(43%)" 헤드라인이 실제 분포를 가려서 정정(사용자 질문: "167/384로 모델 하나만 빠졌는데 왜 이렇게 비어")
  - WHY: `turn_engine_grading_16models_sonnet_results.json`을 모델별로 직접 집계해보니 384건은 "15개 모델 대부분 완료 + 1개 제외"가 아니라 16개 모델의 실제 성능 분포였다 — 신뢰 가능(20건+/24) 5개, 부분성공(29~71%) 4개, **0~12.5%인 모델이 7개**(그 중 3개는 완전 0/24: gpt-oss-120b, kimi-k2.6, llama-3.3-70b-instruct). D94b 레이트리밋 재시도 이후 개별 원인진단+전용 재시도를 받은 건 nemotron과 llama-3.3-70b-instruct 딱 2개뿐이고, 나머지 10개는 한 번도 다시 손대지 않은 상태로 "15/16 완료"라는 헤드라인 밑에 가려져 있었다.
  - **추가 발견**: `docs/index.html`(공개 GitHub Pages)은 D97/D99 이후 갱신이 안 된 상태였다 — Top Performers 표에 nemotron 행이 아예 없었고, "Blocked Model 01/02" 섹션은 둘 다 "다음 조정점"이라며 아직 미해결인 것처럼 서술돼 있었다(실제로는 nemotron 회복·llama-3.3-70b-instruct 제외 둘 다 확정된 상태). 히어로 지표도 `144/384`·`4 models`로 D96 시점에 멈춰 있어, 같은 페이지의 동적 JSON 섹션(`167/384`, `final`)과 서로 다른 숫자를 보여주고 있었다.
  - **실행 결과**: 히어로 지표(167/384·5 models) 갱신, Top Performers 표에 nemotron 행 추가, Blocked Model 섹션을 "Excluded — Final / Resolved ✓ / Not Individually Retried" 3카드로 재작성해 나머지 10개 모델의 티어(부분성공 4개 + 미재시도 6개)를 명시, 히어로 아래 티어 요약 footnote 추가. `d94-rerun-status.json`의 headline/message도 "15/16"이 아니라 "5 reliable / 4 partial / 6 excluded-untried / 1 formally excluded"로 재작성.
  - COST: 순위표(Top Performers, 5개 모델)의 데이터 자체는 원래도 정확했음 — 문제는 헤드라인 프레이밍과 공개 페이지 동기화 누락이었지 데이터 오염은 아니었음(D96과는 다른 종류의 문제).
  - EXIT: `mistral-nemotron`(서버 500)·`mistral-large-3`(시간 단위 차단)는 원인이 일시적일 가능성이 있어 nemotron과 같은 방식(전용 재시도)이 통할 수 있음 — 사용자 결정 대기, 아직 재시도 안 함. 나머지 4개(gpt-oss-120b/20b, kimi-k2.6, glm-5.2)는 구조적 원인(tool-choice 미준수, 계정 접근권한)으로 재시도 실익 낮음.

- **D101** ([`docs/pipelines.html`](./docs/pipelines.html), [`pipelines.html`](./pipelines.html)) — 3파이프라인(교안분석/코드분석/질의응답) 구조도를 GitHub Pages로 공개(사용자 요청: "다른 팀원들에게 공유 가능하게 github.io로 만들어줘")
  - WHY: 직전에 claude.ai 아티팩트로 만든 3파이프라인 청사진(각 파이프라인의 단계별 flow·핵심 파일·상태·팀 스펙과의 관계)을 팀원 공유용으로 옮겨달라는 요청. 이 repo는 이미 `docs/` 폴더 기반 GitHub Pages가 살아있어(D94 이후) 새 인프라 없이 같은 곳에 두는 게 최소 비용. `gh api .../pages`로 실제 소스 설정(`branch:main, path:/`)을 먼저 확인했고, 루트 `index.html`이 `./docs/`로 리다이렉트하는 기존 패턴을 그대로 따라 루트에 `pipelines.html` 리다이렉트 스텁도 추가해 팀원에게 깔끔한 짧은 URL을 줄 수 있게 했다.
  - **실행 결과**: `docs/pipelines.html`(청사진 본문, 다크/라이트 테마 대응)과 루트 `pipelines.html`(→`./docs/pipelines.html` 리다이렉트) 신설. `docs/index.html` 상단 액션 버튼에 "Pipeline Map" 링크 추가(양방향 내비게이션). 공유 URL: `https://popixoxipop-collab.github.io/Code_reviewer_with_feedback/pipelines.html`.
  - COST: 이 페이지는 2026-07-10 D100 시점 **정적 스냅샷**이다 — `docs/index.html`의 벤치마크 섹션과 달리 `d94-rerun-status.json`을 fetch하는 라이브 갱신 구조가 없어서, 이후 벤치마크 수치가 바뀌면(예: mistral 페어 재시도 결과) 수동으로 다시 편집+push해야 한다. 관리해야 할 공개 파일이 3개(`docs/index.html`, `docs/pipelines.html`, 루트 리다이렉트 2개)로 늘어남.
  - EXIT: 구조 자체를 바꾸려면 `docs/pipelines.html`을 직접 편집(청사진 소스는 스크래치패드 `pipeline_blueprint.html`과 동일 마크업)하고 push. 페이지를 없애려면 `docs/pipelines.html`+루트 `pipelines.html`+`docs/index.html`의 "Pipeline Map" 링크 3곳을 함께 제거.

- **D102** (`~/.claude/hooks/scripts/timeout-config-guard.py`, [`rerun_mistral_pair.py`](./rerun_mistral_pair.py)) — mistral-nemotron 504 확인 + D98 hook의 경로 스코프 우회 발견/수정(사용자 질문: "타임아웃을 450초로 내가 하드코딩 하지 말고 중앙 통제식 변수로 가고 모두 일괄 600을 쓰도록 강제했는데 어떻게 이게 구조적으로 가능해?")
  - WHY: D100 EXIT를 따라 mistral-nemotron+mistral-large-3 전용 재시도(`rerun_mistral_pair.py`)를 돌렸는데 mistral-nemotron이 16/16 전부 ~302초에서 죽어서, 하니스를 거치지 않고 raw urllib로 직접 1건 진단 호출을 날렸다(클라이언트 타임아웃을 관측된 컷오프보다 넉넉하게 잡아야 우리 쪽 타임아웃이 먼저 안 걸린다는 걸 확인할 수 있어서 `450.0`을 그 스크립트에 직접 대입) — 이 진단 스크립트를 스크래치패드(repo 밖)에 저장했는데, `timeout-config-guard.py`가 `PROJECT_MARKER not in file_path`면 즉시 `sys.exit(0)`하는 경로 문자열 전용 스코프 게이트라 그대로 통과됐다. 사용자가 "D98에서 무조건 600으로 강제하기로 했는데 이게 어떻게 가능하냐"고 정확히 지적.
  - **진단 결과(핵심)**: raw 호출이 `HTTPError after 302.3s: code=504 reason=Gateway Timeout`을 반환 — 우리 쪽에 450초를 요청했는데도 NVIDIA 게이트웨이 자체가 ~300초에서 연결을 끊는다는 뜻. 하니스의 16/16 동일 ~302초 실패와 정확히 일치. **client 설정(timeout_s/workers/max_tokens)으로는 고칠 수 없는 서버측 하드 컷오프**로 확정 — D89/D94 때의 "빠른 500/DEGRADED"와는 다른, 더 나쁜 증상(응답 없이 게이트웨이가 대신 끊음). mistral-nemotron은 이번 라운드에서 재시도 대상에서 제외, `rerun_mistral_pair.py`의 `TARGET_MODELS`에서 뺐다(재추가 조건을 코드 주석에 명시).
  - **hook 수정**: `PROJECT_MARKER` 경로 매칭 OR `NVIDIA_CONTENT_MARKERS`(API URL/vendored client 클래스명·모듈명) content 매칭으로 스코프를 넓힘 — repo 밖 스크래치패드 진단 스크립트라도 이 프로젝트의 NVIDIA 호출 코드를 담고 있으면 이제 걸린다. 8케이스 하네스(경로매칭/content매칭/무관스크립트 오탐없음/기존 in-project 케이스/DEFAULT_TIMEOUT_S 참조/timeout_config.py 자기예외/allow주석) 전수 통과 + 실제 Write 도구로 차단 재현(`hook_proof_should_block.py`) 확인.
  - COST: content 마커 검사가 `.py` 파일 전체를 대상으로 하므로, 이 프로젝트와 무관하지만 우연히 `nvidia_client`라는 문자열을 포함하는 다른 프로젝트 스크립트가 있다면 그것도 걸릴 수 있음(마커 5개가 충분히 특이적이라 실제 오탐 가능성은 낮다고 판단, 발생하면 `# timeout-guard: allow`로 개별 예외).
  - EXIT: mistral-nemotron을 나중에 재시도하려면 `rerun_mistral_pair.py`의 `TARGET_MODELS`에 `"mistralai/mistral-nemotron"`을 다시 추가(코드 주석에 조건 명시: NVIDIA 쪽이 복구됐다는 신호가 있을 때만). hook의 `NVIDIA_CONTENT_MARKERS` 튜플에 새 마커를 추가하면 스코프를 더 넓힐 수 있음.

- **D103** ([`rerun_mistral_pair.py`](./rerun_mistral_pair.py)) — mistral-large-3의 진짜 원인 확정: "시간 단위 차단"(D90/D91)이 아니라 max_tokens=512 tool-arguments truncation — 부분 회복 1/24→7/24, 전체 167→173/384(45%)
  - WHY: mistral-large-3만 남긴 재시도(max_tokens=512)가 6건을 회복시키면서도 17건이 계속 실패해서, 하니스 밖 단계별 진단으로 원인을 좁혔다: (1) 단순 호출 0.6s HTTP 200 — D90/D91의 즉발 429 차단은 이미 풀림. (2) 같은 tool 스키마의 단문 tool-calling 1.4s 정상 — 스키마 문제 아님. (3) 실제 job 1건 재현 → `json.decoder.JSONDecodeError: Unterminated string` — 모델이 `ask_question` tool은 정상 호출하는데 **arguments JSON이 max_tokens=512 캡에 걸려 중간에 잘림**(실제 프롬프트는 코드 컨텍스트가 붙어 질문이 길어짐; 같은 512 run에서 질문이 우연히 짧았던 6건만 통과한 것도 일치). (4) 같은 job을 max_tokens=2048로 → 93.1s 4턴 정상 완료. 실패 17건의 error 필드도 전부 동일한 `Unterminated string ... (char 13)` 한 종류 — nemotron(D97)과 같은 max_tokens 기아의 다른 증상(내부 reasoning 소진이 아니라 tool arguments 서술이 김).
  - **교훈**: "reasoning 모델이 아니면 512면 충분"(D100 가정)이 반증됨 — max_tokens 필요량은 모델 유형이 아니라 그 모델의 출력 장황함(verbosity)에 달려 있다. `verdict_matches_expected` 지표도 주의: mistral-large-3의 verdict는 대부분 exhausted_at_cap으로 나오는데 이는 D34 계보의 정규식 표현취약성 이슈와 얽혀 있어 job 성공률과 별개 축.
  - **2048 재실행 결과(부분 차단)**: 남은 17건을 2048로 돌리자 **17건 전부 HTTP 429** — 직전 1시간 동안의 이 모델 트래픽(512 run 23 job × 멀티턴 ≈ 수십 콜 + 진단 콜들)이 무료 티어 flagship 쿼터(D90이 관찰한 시간 단위 추정 한도)를 소진시킨 것. 즉발(0.8~3.2s) 실패 다수가 즉시 429 반환과 일치. truncation 수정 자체는 단건 재현으로 이미 검증됐으므로, 쿼터 윈도우 해제 후 같은 스크립트 재실행만 남음(스크립트가 이미 성공분을 스킵하므로 그대로 다시 돌리면 됨).
  - COST: 이번 라운드에서 mistral-large-3에 실제로 쓴 콜은 대부분 truncation으로 버려짐(생성은 됐는데 파싱 불가). 결과 수치는 7/24(29%)에서 일단 멈춤 — 아직 "부분 성공" 티어 하단.
  - EXIT: 쿼터 윈도우가 풀린 뒤(대기 ~1시간 추정) `rerun_mistral_pair.py` 재실행(이미 max_tokens=2048, 성공분 스킵 내장). 그 결과로 20건+/24가 되면 신뢰 가능 티어로 승격, 아니면 부분 성공 티어에 남김 — 공개 페이지(docs/index.html·d94-rerun-status.json·pipelines.html)는 그 최종 수치가 나온 뒤 한 번에 갱신.

- **D104** ([`timeout_config.py`](./timeout_config.py), [`feedback/turn_engine.py`](./feedback/turn_engine.py), [`feedback/llm_interview_grader.py`](./feedback/llm_interview_grader.py), rerun 스크립트 4종, `~/.claude/hooks/scripts/timeout-config-guard.py`) — max_tokens도 timeout과 동일한 중앙 통제(사용자 요청: "max_tokens=2048도 중앙 통제형으로 해줘 timeout과 같은 방식으로")
  - WHY: D103이 확정한 대로 max_tokens=512 기아가 nemotron(내부 reasoning 소진→content:null, D97)과 mistral-large-3(tool arguments JSON 잘림→unterminated, D103)를 서로 다른 증상으로 깨뜨렸다 — 모델 유형(reasoning 여부)으로 캡을 추정하는 건 스크립트마다 타임아웃을 따로 추정하던 D98 이전과 같은 함정. `DEFAULT_MAX_TOKENS = 2048`을 `timeout_config.py`에 추가(파일명이 좁아졌지만 8+ 파일이 import 중이라 rename은 3번째 knob이 생길 때로 보류 — 파일 주석에 명시).
  - **실행 결과**: (1) `turn_engine.generate_question`/`run_decision_point` 기본값 512→`DEFAULT_MAX_TOKENS`(2048) — 이제 16모델 본 하니스가 기본으로 2048을 씀. (2) `llm_interview_grader` 채점 경로 1536→`DEFAULT_MAX_TOKENS`(2048은 1536의 strict superset — 생성된 토큰만 과금되므로 캡 상향은 안전). (3) rerun 스크립트 4종의 리터럴 512/2048 전부 참조로 교체 + `rerun_two_models_fixed_settings.py`에 남아있던 D98 이전 `600.0` 리터럴 2건도 함께 마이그레이션. (4) hook을 패턴 패밀리 구조로 재편(timeout 패밀리/max_tokens 패밀리, 각자 자기 중앙상수 참조 줄만 예외) — `max_tokens=512`·`"max_tokens": 16`(dict 키)·`GRADING_MAX_TOKENS = 1536` 전부 차단, `max_tokens=변수`·시그니처 타입힌트·`args.max_tokens_*`는 통과. 18케이스(기존 timeout 회귀 5 + max_tokens 신규 12 + 교차 패밀리 1) 전수 통과 + 실제 Write 차단 재현. 스모크: import 후 `inspect.signature`로 두 함수 기본값=2048 실검증.
  - COST: 레거시 스크립트(track_a/b 원본 1024, meas02 2048, full_survey 1024 등 비활성 계보)는 이력 보존을 위해 값 유지 — 다음에 그 파일을 편집하는 순간 hook이 걸리므로 그때 마이그레이션(D98이 레거시 타임아웃에 취한 방식과 동일). 교차 패밀리 예외는 줄 단위: 한 줄에 `DEFAULT_TIMEOUT_S`가 있어도 같은 줄의 max_tokens 하드코딩은 잡힘(테스트로 확인).
  - EXIT: 값 변경은 `timeout_config.py`의 `DEFAULT_MAX_TOKENS` 한 줄. 특정 호출만 짧은 캡이 필요하면 그 줄에 `# timeout-guard: allow`.

- **D105** ([`docs/pipelines.html`](./docs/pipelines.html), 아티팩트) — 두 공개 페이지에 "왜 16개 후보 중 일부만 동작했나" 감쇠(attrition) 분석 추가(사용자 요청: 공개 pipelines 페이지에 왜 일부만 동작했는지, 아티팩트에 왜 후보가 좁혀졌는지 적어라)
  - WHY: D100~D104 동안 원인 진단이 전 모델에 대해 완료됐는데(모델 결함 2 / NVIDIA 서버측 3 / 계정 1 / 개별진단 미실시 5 / 신뢰 가능 5), 이 원인별 분류가 README에만 있고 팀원이 실제로 보는 공개 페이지 두 곳엔 없었다 — "낮은 성공률 = 나쁜 모델"로 오독될 여지가 그대로 남아있던 상태(D100에서 지적된 것과 같은 계열의 프레이밍 문제).
  - **실행 결과**: `docs/pipelines.html`에 5티어 감쇠 패널(16→5, 원인별 색상 코딩, 모델별 근거 요약 + README 링크) 신설, 파이프라인 03 카드 상태를 D104 기준(173/384, 45%)으로 갱신. 아티팩트에는 "왜 16개가 5개로 좁혀졌나" 배너(D100~D104 실측 종합: 7키 전부 429 vs 같은 키 타모델 200 대조실험, ~302초 게이트웨이 504, tool_choice 미준수 계보 등)를 신설하고 기존 배너 2개의 낡은 문구("15/16 완료", "재시도 없이 최종 제외")를 현재 사실로 정정. 두 파일 다 HTMLParser 구조 검증 통과, 아티팩트 재배포 완료.
  - COST: pipelines.html은 여전히 정적 스냅샷(D101 COST 동일) — mistral-large-3 게이트 러너 결과가 나오면 이 감쇠 패널 수치도 수동 갱신 필요.
  - EXIT: 감쇠 티어가 바뀌면(예: mistral-large-3 회복, 미진단 5개 중 회복 사례 발생) `docs/pipelines.html`의 `.attrition` 섹션과 아티팩트의 해당 배너를 함께 수정.

- **D106** ([`benchmark_4axis_regrade.py`](./benchmark_4axis_regrade.py), [`turn_engine_4axis_summary.json`](./turn_engine_4axis_summary.json), [`turn_engine_4axis_regrade_raw.json`](./turn_engine_4axis_regrade_raw.json)) — 4축(호출 안정성/정밀도/재현성/속도) 벤치마크 재구성(사용자 지시) + **lig.MODEL 방법론 갭 발견**
  - WHY: 4축 중 2축이 결손이었다. (1) 재현성 — D89~D94 내내 REPEATS=1 미측정. (2) 정밀도 — **D93 헤더는 "그 모델이 자기 transcript를 채점한다"(Locked 스펙)고 선언했지만 repo 어디에도 `lig.MODEL`을 후보로 바꾸는 코드가 없어, 지금까지의 모든 Track B 채점이 고정 grader(qwen3-next-80b)로 나갔다** — 모든 모델의 grading_success_rate가 1.0이었던 이유. 신뢰 티어 모델들의 기존 ok transcript(113건)를 재사용해 각 후보가 자기 transcript를 3회 채점(temperature=0, Sonnet 콜 0건)하는 replay 설계로 두 축을 처음 측정.
  - **핵심 발견**: 정밀도(strong>weak 분리)는 채점이 성공한 모델 전원 1.00 — 승부처는 **재현성**(같은 입력 3회 채점의 5축 벡터 완전일치율)이었다. temp=0인데도 모델별 0.44~0.83으로 갈림(서버측 비결정성). NVIDIA 부분 장애(qwen·maverick 단순 호출도 504) 때문에 모델 서브셋 실행+raw 모델단위 병합(D106b) 지원 추가.
  - COST: 재채점 raw에서 채점 실패도 데이터로 남김(재시도 없음). 부분 커버리지 상태의 종합지수는 covered 집합 내 정규화라 모델이 추가되면 재계산 필요.
  - EXIT: `--aggregate-only`로 API 콜 없이 재집계. 신규 모델 추가는 RELIABLE_MODELS에 등록 후 해당 모델만 재실행.

- **D107** ([`benchmark_turn_engine_grading_16models_sonnet.py`](./benchmark_turn_engine_grading_16models_sonnet.py)) — 답변 생성 모델 sonnet→haiku 전환(사용자 지시: "Sonnet 호출 말고 codex 호출하던가 haiku 호출해")
  - WHY: 답변 생성이 Claude 구독 주간 한도를 공유하는데(D96 오염 사고의 배경) 학생 페르소나 답변(1~3문장 역할극)은 haiku로 충분 — 실측 8.6s, 페르소나 준수 확인. codex CLI는 별도 쿼터 풀이라는 장점이 있지만 서브프로세스 규격이 달라 D96 가드(QUOTA_EXHAUSTED_MARKERS)를 재검증해야 해서 최소 변경인 haiku를 기본값으로(`ANSWER_MODEL` env로 오버라이드 가능).
  - COST: 결과 파일에 답변 생성기가 다른 job이 섞이게 됨 — 신규 행에 `answer_model` 필드 추가(기존 행=sonnet). 모델 간 공정 비교는 같은 답변 생성기 job끼리만 유효.
  - EXIT: `ANSWER_MODEL=sonnet`으로 되돌리기 가능. codex 전환이 필요하면 `_sonnet_call()`의 서브프로세스 규격+가드 재검증 필요.

- **D108** ([`timeout_config.py`](./timeout_config.py), [`benchmark_4axis_regrade.py`](./benchmark_4axis_regrade.py)) — max_tokens 2048→4096 + **mistral-large-3 채점기 퇴행 루프 확정** + 안정성 축 통합 산식(사용자 지적 반영)
  - **D108a**: 5축 채점 tool의 arguments(축당 점수+근거인용)가 ask_question보다 훨씬 길어 mistral-large-3가 2048에서 `finish_reason=length`로 잘림(단건 재현) → 중앙값 4096 상향. 캡은 상한이지 목표가 아니라 temp=0에서 캡에 안 닿는 모델은 바이트 동일 — nemotron 채점 준수율 0.783→0.841로 개선(truncation 분 해소), 잔여 11건은 전부 "Extra data"(유효 JSON 뒤 잉여 출력) = 진짜 스키마 미준수 결함.
  - **D108b**: mistral-large-3는 4096으로도 실패 → 토큰 행방 추적 결과 **cap=2048/4096/8192 전부 completion_tokens=캡(예산 전액 소진)인데 가시 출력은 args ~850-907자+reasoning 0자** — 캡 2배에 출력 +60자, 유한한 캡으로 해결 불가한 퇴행 생성 루프. 단순 스키마(질문생성)는 24/24 정상이므로 "복잡한 스키마에서만 터지는" 모델/서빙 결함. `GRADER_ROLE_DEFECTS`로 사유 문서화.
  - **D108c**(사용자 지적: "그럼 그냥 4축 중에 연결 안정성이 낮은 거잖아"): 채점기 결함을 특수 카테고리로 순위 제외하는 대신 **안정성 축 = 질문생성 성공률 × 채점 성공률(end-to-end)**로 통합 — 스펙이 한 모델에 두 역할을 요구하므로 실전 성공확률은 곱. 채점 전멸 모델의 정밀도/재현성은 "측정불가"가 아니라 0점(채점 못하는 채점기의 유효 정밀도는 0). 이전 왜곡 2건(빠진 축 건너뛰고 평균→large-3 가짜 1위, 특수 제외) 모두 폐기.
  - **4축 최종(5/6 커버, llama-4-maverick은 NVIDIA 다운 지속으로 워처 대기)**: step-3.5-flash 0.994(안정성 0.945·재현성 0.818·10.5s) > qwen3-next-80b 0.79(재현성 0.522) > mistral-medium-3.5 0.75(재현성 spread 최소 0.17, 178.9s) > nemotron-super-49b 0.667(채점 준수 0.841) > mistral-large-3 0.229(채점기 결함, 안정성 0).
  - COST: **팀 Locked 모델(qwen3-next-80b)이 재현성 0.522로 2위** — step-3.5-flash가 전 축 우세+9배 빠름. 팀 모델 선정 재검토 근거로 쓸 수 있는 실측.
  - EXIT: maverick 회복 시 워처가 자동 재채점 → `--aggregate-only`로 6모델 완전판 재계산. → D109에서 사용자 결정으로 대기 종료·마감.

- **D109** ([`benchmark_4axis_regrade.py`](./benchmark_4axis_regrade.py), [`turn_engine_4axis_summary.json`](./turn_engine_4axis_summary.json)) — llama-4-maverick "연결 안정성 미달"로 기록하고 4축 벤치마크 최종 마감(사용자 결정: "저 모델도 연결 안정성이 떨어진다고 쓰고 마무리 지어")
  - WHY: NVIDIA가 이 모델 서빙을 10시간+ 복구하지 못함 — 워처 2라운드(3분 간격 80회 + 10분 간격) 총 82회 프로브가 전부 타임아웃(단순 "Say OK"조차 불통). 회복을 무한정 기다리는 대신, D108c의 end-to-end 원칙을 그대로 적용해 마감: 채점기 역할을 아예 수행할 수 없는 모델의 채점 안정성은 0이다. 원인이 모델 결함이 아니라 NVIDIA 서빙이라는 사실은 `serving_outage` 필드로 명시(억울한 탈락이 아니라 감사 가능한 판정).
  - **4축 최종 (6모델 완전판)**: step-3.5-flash **0.994** > qwen3-next-80b 0.79 > mistral-medium-3.5 0.75 > nemotron-super-49b 0.667 > llama-4-maverick 0.248(서빙 장애, 안정성 0.875×0=0) > mistral-large-3 0.229(채점기 퇴행 루프, 안정성 1.0×0=0). 아티팩트·GitHub Pages(index/pipelines) 모두 완전판으로 동기화.
  - COST: maverick의 정밀도/재현성은 영구 미측정(합성 0점) — NVIDIA 서빙이 복구된 뒤 재채점하면 실측으로 대체 가능하나, 사용자 결정으로 이 벤치마크 라운드는 여기서 확정.
  - EXIT: 나중에 maverick을 실측으로 채우려면 `python3 benchmark_4axis_regrade.py "meta/llama-4-maverick-17b-128e-instruct"` 후 `--aggregate-only` — SERVING_OUTAGE의 합성 엔트리는 raw 행이 생기면 자동으로 실측이 우선한다(`m not in summary` 조건).

- **D110** ([`rerun_partial_five.py`](./rerun_partial_five.py)) — "개별 진단 미실시 5개" 병렬 진단+재실행: **60/69 회복, 전원 신뢰 티어 진입** (사용자 지시: "병렬로 개별 진단")
  - WHY: 감쇠 분석의 "개별 진단 미실시" 티어 5개(minimax-m3 71%/qwen3.5-122b 58%/deepseek-v4-pro 42%/nemotron-3-super-120b 29%/glm-5.2 13%)는 D94b 일괄 재시도만 받고 nemotron식 개별 진단이 없었다. 로컬 error 분포 분석(콜 0건)으로 실패 69건이 3클래스로 정확히 갈림: (a) HTTP 429 31건(minimax·deepseek·glm — D94b 버스트 시대 잔재), (b) content=None 10건(qwen3.5 전부 — D97 nemotron-49b와 동일한 reasoning 512 기아 시그니처), (c) content에 추론 독백/JSON 25건(nemotron-3·glm — 512가 tool 호출 전에 끊었는지 진짜 미준수인지 재실행이 판별 실험).
  - **실행 결과**: 현재 설정(중앙 4096/600s, 전역 12rpm, workers=4, 답변=haiku D107)으로 69 job 재실행 → **60건 회복**. deepseek-v4-pro 42%→**24/24(100%)** · minimax-m3 71%→**23/24(96%)** · nemotron-3-super-120b 29%→**23/24(96%)** (미준수로 보였던 17건이 실제론 512 기아) · glm-5.2 13%→**21/24(88%)** · qwen3.5-122b 58%→**20/24(83%)**. 전체 190→**250/384(65%)**, "부분 성공" 티어 소멸 — 신뢰 티어 6→**11개**.
  - **잔여 9건(정직한 잔차)**: 인프라 노이즈 2(503/504) · qwen3.5의 지속성 content=None 3(4096으로도 소진 — 이 모델 고유 한계) · glm의 "정확한 JSON을 content 채널에 출력" 4(간헐적 tool-API 미준수).
  - COST: 회복 job의 답변은 haiku 생성(기존 ok 행은 sonnet) — `answer_model` 필드로 감사 가능, 모델 간 비교 시 주의(D107). 세션 통산 교훈의 스케일 확정: "나쁜 모델" 점수 대부분이 우리 발사 패턴(job당 5~8 HTTP콜 × 무백오프 재시도 × 동시성이 40rpm 초과)+512 캡의 아티팩트였지 모델 품질이 아니었다.
  - EXIT: 승격 5개를 RELIABLE_MODELS에 추가(D110b), 4축 재채점(candidate-as-grader ×3) 실행 → 11모델 4축 완전판으로 재집계. → D111에서 완료.

- **D111** ([`turn_engine_4axis_summary.json`](./turn_engine_4axis_summary.json), [`benchmark_4axis_regrade.py`](./benchmark_4axis_regrade.py)) — 승격 5개 4축 재채점 완료, **11모델 완전판 최종 순위** + minimax DEGRADED 진단
  - **결과**: step-3.5-flash **0.984** > qwen3-next-80b 0.779 > **deepseek-v4-pro 0.776**(안정성 1.0 유일 만점 — 질문생성 24/24 × 채점 72/72) > mistral-medium-3.5 0.74 > qwen3.5-122b 0.701 > nemotron-3-super-120b 0.694 > nemotron-49b 0.658 > glm-5.2 0.652 > maverick 0.248 > mistral-large-3 0.229 > minimax-m3 0.1.
  - **신규 발견 2건**: (1) nemotron-3-super-120b는 채점 준수율 0.928인데 **재현성 0.0(총점 spread 4.41) + 범위 밖 점수(0점·9점) 출력** — 질문생성기론 96%지만 채점기론 극도로 불안정. (2) minimax-m3의 채점 콜 69건 전멸은 **전부 동일한 HTTP 400 "DEGRADED function cannot be invoked"**(라이브 단건 재현 확인) — 측정 시간대에 NVIDIA가 서빙 함수를 강등한 것으로, 1시간 전 질문생성 23/24를 통과한 모델이라 결함이 아니라 인프라(annotation `grader_measurement_outage`로 명시, 복구 후 재측정 가능).
  - **채점기 역할까지 무결한 모델**: step-3.5-flash·deepseek-v4-pro·mistral-medium-3.5·glm-5.2(채점 준수 0.98+). 질문생성기 역할은 11개 전원 합격 — 스펙(단일 모델 양역할) 기준 실질 후보군은 4개로 좁혀짐.
  - COST: minimax·maverick의 정밀도/재현성은 서빙 장애로 미측정(0점 처리, 원인 annotation 구분) — NVIDIA 복구 시 해당 모델만 재실행하면 자동 대체.
  - EXIT: `python3 benchmark_4axis_regrade.py "<model>"` 후 `--aggregate-only` — minimax/maverick 재측정용. 벤치마크 라운드는 여기서 확정.

- **D112** ([`benchmarks/test_keypool_280rpm.py`](./benchmarks/test_keypool_280rpm.py), [`benchmarks/live_burst_keypool.py`](./benchmarks/live_burst_keypool.py)) — 키풀 280rpm 능력 검증(사용자 지시: "키가 7개면 이론상 7×40=280회/min이어야 하는데 코드가 그렇게 되어 있는지 검증")
  - WHY: minimax·maverick의 측정 실패를 "NVIDIA측"으로 판정했는데, 사용자가 "우리가 40rpm을 못 지킨 것 아니냐"는 대안 가설을 제기 — 키풀 코드가 실제로 키당 40rpm × 7키를 올바르게 구현·집행하는지 실증이 필요했다.
  - **오프라인 검증(가짜 시계, HTTP 0건) — 5항목 전부 PASS**: ① 한 윈도우(60s)에서 280 grant 무블로킹 발급 ② 281번째는 정확히 윈도우 슬라이드(~60s)까지 대기 ③ 키 분배 공정(키당 정확히 40) ④ 모델별 예산 격리(모델A 포화가 모델B에 무영향) ⑤ 280 acquire 실시계 <1s(인위적 직렬화 없음).
  - **라이브 검증 — PASS**: 단일 키 한도(40/min)를 넘는 120/min 발사 페이스로 step-3.5-flash에 84콜 실발사 → **84/84 전부 HTTP 200, 429 제로, 키 분배 완벽(7키 × 정확히 12콜)**, 실효 68/min(단일 키 한도의 1.7배, 응답 지연이 벽시계를 늘림).
  - **결론**: 풀 코드는 결백 — 280/min 능력을 정확히 구현. 역사적으로 40rpm을 어긴 건 키풀 도입 전 D94 최초 실행(단일 키+동시성6+무백오프 재시도)뿐이고, 이후로는 오히려 전역 12rpm 캡이 풀 능력의 4%만 사용. **minimax의 400 "DEGRADED function"은 검증 직후 같은 키로 재현(레이트리밋이면 429여야 함) — NVIDIA 함수 상태 문제 확정**, maverick도 여전히 타임아웃(14시간+).
  - COST: 라이브 버스트에 step-3.5-flash 트리비얼 콜 84건 소비. 12rpm 캡이 과도하게 보수적이라는 것도 함께 확정 — 다음 대규모 실행부터는 REGRADE_RPM 상향 여지(단, mistral-large-3류 시간 단위 버킷 모델은 예외).
  - EXIT: minimax(채점 페이로드 프로브)·maverick(단순 프로브) 회복 감시 워처 가동(10분 간격, ~12h) — 회복 즉시 재채점+재집계 자동 실행.

- **D113** ([`benchmarks/keypool_reproducibility_10x.json`](./benchmarks/keypool_reproducibility_10x.json)) — D112 검증 전 과정 10회 반복 재현성 실증(사용자 지시: "재현성 검증을 위해 최소 10번은 반복해라")
  - **실행**: 라운드마다 오프라인 5항목 스위트 + 라이브 버스트(84콜, 120/min 발사 페이스) — 총 라이브 840콜, 라운드별 원자료 전부 JSON 보존.
  - **검증 대상 속성(키풀이 키당 40rpm을 지키며 로테이션으로 40rpm 초과 총처리량 달성)은 10/10 재현**: 840콜 전체에서 **HTTP 429 = 0건**, **키 분배 매 라운드 정확히 12×7**, 실효 처리량 매 라운드 40/min 초과(52.7~98.7, 평균 71.0/min). 오프라인 스위트도 10/10 PASS.
  - **엄격 기준(84/84 전부 200)은 4/10**: 6개 라운드에서 각 1콜(합계 6/840 = 0.7%)이 프로브의 60초 소켓 타임아웃(status -1, latency_max 60.1s)에 걸림 — 레이트리밋이면 429여야 하고(0건), 해당 라운드에서도 키 분배는 완벽 유지. 오늘 하루 종일 측정된 NVIDIA 서빙 꼬리지연(504/타임아웃)과 같은 클래스로, 검증 대상인 레이트리밋 로직과 무관. 두 층 판정을 JSON `summary.interpretation`에 명시.
  - COST: 라이브 트리비얼 콜 840건. 엄격 기준의 6실패는 "NVIDIA 무료 티어의 평상시 꼬리지연이 콜당 ~0.7% 존재한다"는 부수 실측이기도 함 — 벤치마크류 파이프라인은 콜 단위 재시도 1회만 있어도 이 노이즈를 흡수 가능(현재 파이프라인은 의도적으로 무재시도 설계라 이 노이즈가 그대로 드러남).
  - EXIT: 재실행은 `benchmarks/` 스크립트 그대로(온라인 부하 상황이 다르면 실효 rpm 분포만 달라짐). 콜 타임아웃을 60s→`DEFAULT_TIMEOUT_S`로 늘리면 -1 클래스는 대부분 사라질 것으로 예상(꼬리지연이 60s 근처라는 게 이번 실측).

- **D114** ([`docs/index.html`](./docs/index.html), 아티팩트, [`benchmark_4axis_regrade.py`](./benchmark_4axis_regrade.py)) — 응답이 실제로 오는 11개 모델의 **정식 4축 벤치마크 표** 공개 + minimax 실측 자동 합류(사용자 질문: "11개 모델 벤치마킹 표 만들어줬어?" — 그동안 프로즈로만 있었음)
  - WHY: 4축 최종 결과가 공개 3면에 문장으로만 있었고 열 정렬된 표가 없었다. 마침 채움 워처가 minimax의 DEGRADED 해제를 감지해 자동 재채점(채점 68/69, 재현성 0.318)을 완료 — 합성 0점(0.1, 11위)이 실측(0.682, **7위**)으로 대체된 상태라 표 생성 시점이 맞았다. 표 값은 전사 오류 방지를 위해 `turn_engine_4axis_summary.json`에서 스크립트로 직접 생성.
  - **수정**: (1) `docs/index.html`의 낡은 "Top Performers"(D94 시점 구지표 5행) 표를 11행 4축 표로 교체 — 열: 안정성(질문생성×채점 분해 표기)/정밀도/재현성(±spread)/속도/종합/비고. (2) 아티팩트에 동일 표 추가(기존 `table.raw` 스타일 재사용), 배너의 낡은 순위 프로즈 정리. (3) 두 페이지의 순위 문장에서 minimax 위치 갱신. (4) `GRADER_MEASUREMENT_OUTAGE` annotation을 채점 성공률 0일 때만 달도록 조건화 — 실측이 채워졌는데 "69콜 전멸" 문구가 계속 붙는 낡음 방지.
  - COST: 표는 정적 스냅샷 — maverick이 회복돼 실측이 들어오면(워처 감시 중) 표 3곳+순위 문장 수동 갱신 필요. minimax의 재현성(0.318)은 DEGRADED 회복 직후 측정이라 평상시보다 낮게 나왔을 가능성 존재(재측정으로 확인 가능).
  - EXIT: 표 재생성은 summary JSON→행 변환 스크립트 패턴 재사용(D114 커밋의 생성 코드 참고).

- **D115** ([`benchmark_4axis_regrade.py`](./benchmark_4axis_regrade.py)) — 4축 벤치마크 재현성 축을 REPEATS 3→100으로 대규모 재측정(사용자 지시: "재현성 엄밀성을 위해 100번 반복 밴치마킹") + **집계 지표 함정 발견/반증**
  - WHY: "100번 반복"이 D112/D113의 키풀 인프라 검증(가벼운 "Say OK" 호출)과 실제 4축 벤치마크의 재현성 축(진짜 채점 콜) 중 어느 쪽인지 비용이 최대 33배(2.5시간 vs 31.5시간) 차이나 AskUserQuestion으로 확인 → **4축 벤치마크의 재현성 축**으로 확정. 대상 9개 모델(mistral-large-3는 채점기 자체 결함으로 100번 반복해도 전부 실패만 반복해 제외, llama-4-maverick은 transcript 0건이라 재측정 대상 자체가 없어 자동 제외) × 203 transcripts × 100 = **20,300 채점 콜**.
  - **집계 함정 발견 + 반증(진짜 소득)**: REPEATS를 env로 설정 가능하게 바꾸는 김에 "재현성 판정 기준(len(ok_reps)==REPEATS 완전성공만 인정)이 REPEATS가 커질수록 커버리지가 (1-p)^REPEATS로 급락한다"는 문제를 미리 고치려고 판정 기준을 ">=2회 성공"으로 완화했다가, **`--aggregate-only`로 기존 REPEATS=3 데이터에 재적용해보니 순위 4-5위·8-9위가 실제로 뒤바뀜을 발견**(qwen3.5-122b 재현성 0.5→0.733, composite 0.701→0.772 등). 원인 규명: qwen3.5-122b는 coverage=0.667(대부분 2/3 성공)이라, "2개 비교"가 "3개 비교"보다 통계적으로 우연히 다 일치하기 쉬워서 **coverage 낮은(=인프라 노이즈 많이 겪은) 모델일수록 재현성이 역설적으로 부풀려지는 편향**이었다 — 실측으로 자가 검증해 반증하고 원래 기준(정확히 REPEATS개 성공)으로 되돌림, 이미 공개된 identical_rate/composite 수치는 완전히 무손상 확인(`turn_engine_4axis_summary.json.bak_repeats3`와 바이트 비교로 재검증 완료). 대신 REPEATS가 클 때를 위한 신규 참고지표 2개를 별도 추가: `reproducibility_mode_agreement_rate`(성공한 반복 중 최빈 5축 벡터 점유율, 연속값이라 부분 커버리지에도 상대적으로 안정) + `reproducibility_coverage_rate`(모델 일관성과 인프라 노이즈를 분리해서 노출) — 둘 다 랭킹 산식(composite_4axis)에는 반영 안 함, 순수 진단용.
  - **실행**: 9모델 순차 실행(레이스 방지 — RateLimitedClient가 프로세스 내부 상태라 병렬 프로세스는 각자 독립적으로 rpm을 세어 합산 시 진짜 한도를 넘길 위험, D112에서 확인한 사실을 여기 설계에 직접 반영). 페이싱은 D112/D113가 실측 증명한 안전범위 안에서 기존 12rpm/4workers 기본값보다 상향(60rpm/24workers) — 채점 콜은 trivial 호출보다 지연이 커서(모델별 평균 30~180초) workers 수가 실제 병목이 될 수 있음을 인지하고 진행하며 조정.
  - COST: 실행 전 REPEATS=3 raw/summary를 `.bak_repeats3`로 백업(대조군 보존, 드리프트 없음을 재검증하는 근거로도 사용). 20,300콜은 오늘 하루 여러 차례 겪은 NVIDIA DEGRADED/서빙장애 패턴을 감안하면 실행 중 일부 모델에서 재현될 수 있음 — 모델 단위 순차+raw 병합 설계라 중간에 한 모델이 전멸해도 이미 끝난 모델의 데이터는 안전.
  - EXIT: 결과는 완료 후 표+README 갱신. 재현성 판정 기준을 identical_rate 대신 mode_agreement_rate로 바꾸고 싶으면(통계적으로 더 안정적) `composite_4axis` 계산부의 `repr_` 라인 하나만 교체.

- **D116** ([`benchmark_4axis_regrade.py`](./benchmark_4axis_regrade.py), [`turn_engine_4axis_summary.json`](./turn_engine_4axis_summary.json)) — 100회 재현성 완주(총 12시간 39분) + **"모델별 총량 쿼타 버킷"이 mistral-large-3만의 특성이 아니었음을 확인**, 사용자 결정으로 그대로 마감
  - **완주 결과(9모델 순차, 23:36~08:22)**: 6개는 신뢰 가능한 재측정 — nemotron-3-super-120b는 채점 성공률 92.8%→76.1%로 하락했는데 원인이 범위 밖 점수(0점·8점) 출력과 tool_choice 미준수라 **100회가 이 모델의 진짜 결함률을 작은 표본(3회)보다 정확히 잡아낸 것**(의도한 효과가 실현된 사례). 나머지 5개(step/medium/qwen3-next/qwen3.5/nemotron-49b)는 REPEATS=3 대비 값이 합리적 범위에서 이동 — 재현성이 낮을수록(0.27~0.62) 표본이 커질 때 값이 더 크게 흔들리는 것 자체가 통계적으로 정상.
  - **3개는 인프라 붕괴, 재현성 문제 아님**: minimax-m3(2300/2300 전부 HTTP 400 DEGRADED — D111 사건 재발, 종료 직후 라이브 프로브로 정상 복구 확인) · glm-5.2(2100건 중 1883건 HTTP 429, 98.4%→10.2%) · deepseek-v4-pro(2400건 중 1719건 HTTP 429, **100%→28.4%**, 몇 시간 전 유일한 완전무결 모델이었음). glm/deepseek 둘 다 **런 종료 직후에도 라이브 단발 프로브가 여전히 429** — 이건 D103에서 mistral-large-3 하나에서만 확인했던 "천천히 재충전되는 모델별 총량 쿼타 버킷"이 **최소 2개 모델 더 있다는 새 발견**이다. D112/D113가 증명한 "60rpm 안전"은 step-3.5-flash 한 모델로만 검증한 것이라 전 모델에 일반화되지 않는다는 게 실측으로 확정됨 — 대량 단일모델 벤치마크를 다시 설계할 때는 모델별로 낮은 rpm을 기본값으로 잡아야 한다.
  - **사용자 결정**: AskUserQuestion으로 "3개 모델을 어떻게 처리할지"(재시도 대기 8~12시간 추가 vs 즉시 마감) 확인 → **3개 다 지금 상태로 마감, 추가 실행 없음**. `GRADER_MEASUREMENT_OUTAGE`(minimax) + 신규 `VOLUME_QUOTA_BURST_INCIDENT`(glm-5.2·deepseek-v4-pro) 딕셔너리로 원인을 summary에 명시하되 점수 자체는 실측 그대로 반영(annotation은 설명이지 면죄부가 아님, D109/D111 원칙 재사용).
  - **최종 11모델 순위**: step-3.5-flash 0.866 > mistral-medium-3.5 0.749 > qwen3-next-80b 0.742 > nemotron-3-super-120b 0.663 > qwen3.5-122b 0.589 > nemotron-super-49b 0.531 > deepseek-v4-pro 0.487(인프라) > llama-4-maverick 0.248 > mistral-large-3 0.229 > glm-5.2 0.104(인프라) > minimax-m3 0.1(인프라). REPEATS=3 대비 큰 순위 이동: deepseek(3위→7위)·glm(9위→10위)·minimax(7위→11위)는 전부 인프라 원인, nemotron-3-super(6위→4위 상승은 다른 모델들이 인프라로 떨어진 상대효과)는 절대 성공률 자체는 하락(진짜 결함).
  - COST: REPEATS=3 raw/summary(`.bak_repeats3`)와 REPEATS=100 run1 raw/summary(`.bak_repeats100_run1`) 둘 다 보존 — 대조/재현 가능. `--aggregate-only` 재실행 시 `REGRADE_REPEATS=100`을 반드시 같이 지정해야 함(env 없이 돌리면 기본값 3으로 떨어져 REPEATS=100 데이터의 `len(ok_reps)==REPEATS` 판정이 전부 깨짐 — 이번에 실제로 한 번 겪고 즉시 재수정).
  - EXIT: minimax(이미 복구)·glm/deepseek(쿼터 버킷 해제 대기 필요)를 나중에 재측정하려면 `benchmark_4axis_regrade.py "<model>"`을 D103 mistral-large-3 패턴(REGRADE_RPM=6, REGRADE_WORKERS=2, 필요시 게이트 러너로 회복 감시)으로 재실행. 재실측 raw가 생기면 annotation은 그대로 남지만(과거 사건 기록), 점수는 새 데이터로 자동 갱신됨.

- **D117** ([`docs/pipelines.html`](./docs/pipelines.html)) — 파이프라인 페이지의 4축 결과가 (D114/D116으로 index.html·아티팩트는 표가 됐는데도) 여전히 `.lesson` 안 프로즈였던 것 발견·수정, D116 11행 표를 그대로 이식해 3개 공개 표면(아티팩트/index.html/pipelines.html) 표기를 통일. 커밋 `520ca26`.

- **D118~D125** ([`EXECUTION_PLAN_4AXIS_HOOKFILE.md`](./EXECUTION_PLAN_4AXIS_HOOKFILE.md)) — 파이프라인 01/02 벤치마크 등가화 + Hook File 재귀 루프 실험 전체 계획. fable 모델에 위임해 초안 작성(사용자 지시: "fable 모델 호출해서... 세 가지 파이프라인 모두에 대해 계획을 짜달라고 해") → 팩트체크(D-번호 충돌을 D117 실사용과 대조해 D118~D124로 재번호, `judgment/reflection_hook.py`가 실제로는 `feedback/`에 있고 파이프라인 03 소속이라는 §0 오귀속 수정) → 사용자가 §7.5 열린 질문 11건(원 10건 + 검증 중 발견된 P02-T1 포함여부) 전부 확정(D125): P01 REPEATS 청크100/qgen50, P01-T1·P02-T1·P02-T2 전부 실행, Hook File 그릇=정적파일(Claude-Code-Hooks-JSON 모티브), 과제=실제 커리큘럼, **회차수 k=3→4**(재발률이 델타 아니라 회차별 감소 곡선+정착률로 보여야 한다는 사용자 요구로 5.2/5.3 재설계), γ 잠정보고 가능, **P03도 hook 루프 인터뷰 채널로 통합**, 루브릭 출처=사용자 제공 zip. 커밋 `b2def4a`+push.
  - 축 재정의 공통 원칙(D118): 축 이름은 유지하되 정의는 파이프라인 실제 산출물에 맞게 재정의, REPEATS 다른 identical_rate끼리 비교 금지, 인프라 원인은 annotation으로 명시하되 점수는 실측 그대로 반영(D109/D111/D116 계보 상속), 공개 3면 동기화를 마일스톤 종료조건에 포함(D100 재발방지).

- **D119** ([`benchmarks/judgment_4axis_benchmark.py`](./benchmarks/judgment_4axis_benchmark.py), [`benchmarks/p02t2_static_vs_llm.py`](./benchmarks/p02t2_static_vs_llm.py), [`benchmarks/prepare_precision_labels.py`](./benchmarks/prepare_precision_labels.py)) — 파이프라인 02(cognition/judgment) 4축 벤치마크 실측(M0/M1, 사용자 지시 "계획대로 진행하자"). 사람 라벨링이 필요 없는 3.5축(안정성/재현성/속도 + T1/T2 구조 데이터)을 전부 실측, 정밀도(핵심 축)만 사람 라벨링 스프린트 대기.
  - **표본**: `examples/{c_cpp,java,javascript,python}`의 39개 repo — `PROVENANCE.json`의 git_url+고정 commit으로 재클론(`examples/`는 frozen 출력만 보존하고 원본 소스는 없었음, 이번에 처음 재현 확인). `examples/{lms,shadowbroker,study_match}` 3개는 `PROVENANCE.json`이 없어(팀 내부 fixture, 원본 위치 미기록) 재현 불가 — 제외를 결손으로 명시.
  - **안정성**: 39/39 = 100%(스캔+판단 crash-free + 스키마 유효).
  - **속도**: 평균 0.192초/repo, `cost_saved_ratio` 평균 0.998(Tier B "deep read"를 거의 안 탐 — 2계층 스캔 설계의 비용절감이 실측으로 확인됨).
  - **재현성(a) 고정상태 100회**: 언어당 2개 표본(8 repo) × 100회 = 800회 전부 **identical_rate=1.0**. "결정론이 이 방법론의 셀링 포인트인데 실측 증명이 없었다"(3.1 WHY)는 주장이 이번에 처음 실증됨 — os.walk/dict 순회 순서 버그 없음 확인.
  - **재현성(b) 상태 민감도**: empty_state vs current_state(팀이 자체 프로젝트에서 쌓은 idiom/tier_b/subrubric 누적 상태) 비교 결과, 8개 표본 전부 finding 수 delta=0. **팀이 Study-Match-/LMS 등에서 쌓은 보정 상태가 이번 39개 임의 외부 OSS repo에는 하나도 매치되지 않음** — idiom pattern_key/tier_b trigger가 특정 코드 패턴에 정확히 키가 걸려 있어 우연 일치 확률이 낮기 때문(버그가 아니라 상태의 도메인 특이성을 보여주는 정직한 null 결과).
  - **P02-T1(ablation, 확정 트랙, 실행 완료)**: idiom_filter/tier_b_suppression/subrubric_weights 3개 보정장치를 개별 off해도 (b)와 같은 이유로 이 표본에서는 구조적 효과가 관측되지 않음(4개 설정 전부 41 findings/8 repo로 동일) — 상태 백업/복원 메커니즘 자체는 무사고로 검증됨. **진짜 기여도 정량화("좋아졌는가")는 정밀도 라벨 없이는 판정 불가** — 지금은 "무엇이 달라지는가"의 메커니즘 검증까지만.
  - **P02-T2(정적 vs 순수 LLM, 확정 트랙, 14/14 콜 성공)**: D65/D69 재검증 — qwen3-next-80b로 39-repo 코퍼스에서 7개 대표 케이스(단일파일 신호 3, cross-file 신호 4) × run1/run2. **single-file 신호 2/3 커버, cross-file 신호 2/4 커버** — D69의 "cross-file은 원천적으로 0%"라는 단정보다 완만한 결과(2/4는 0%가 아님). **방법론 한계를 정직히 기록**: cross-file 커버리지 판정 키워드 중 일부("wrapper" 등)가 파일명 자체에 있어, 진짜 cross-file 추론과 우연한 키워드 일치를 이 판정 방식으로는 구분 못 함 — D66이 이미 못박은 대로 "reference-set coverage"이지 gold-standard recall이 아님. `benchmarks/meas02_run_benchmark.py`(D65~D69 원본)는 수정하지 않음 — 원본 CASES가 가리키던 이전 세션 scratch 파일이 이미 사라져 그 파일 자체는 현재 재실행 불가 상태임을 확인(별도 버그, 이번 케이스는 새 corpus로 새로 만듦).
  - **정밀도(핵심 축)**: 사람 라벨링 스프린트 미착수(라벨러 2인 확보는 사용자 몫, 3.1 EXIT). `judgment_precision_labels.jsonl`에 코퍼스 전체 100개 finding 중 언어×priority 계층화 표집 50개 준비 완료 — 라벨러 배정만 되면 바로 시작 가능.
  - WHY: 사람 개입 없이 측정 가능한 축을 전부 먼저 확보해 정밀도(유일한 사람-병목 축)가 나머지를 막지 않게 함.
  - COST: (b)/T1의 null 결과는 이번 8-repo 표본의 특성일 수 있음 — 팀 자체 프로젝트급(Study-Match-/LMS류)으로 표본을 넓히면 다른 결과가 나올 가능성이 있음.
  - EXIT: 라벨러 2인 확보 시 `judgment_precision_labels.jsonl`의 `labeler_a/b_label`을 채우고 kappa 계산 → 정밀도 축 확정. 팀 자체 프로젝트를 표본에 추가하려면 `judgment_4axis_benchmark.py`의 `discover_corpus()`에 `PROVENANCE.json`만 추가하면 재클론 로직이 그대로 재사용됨.


## 다음 단계 (미해결)

1. ~~판단 블록에 "프레임워크 관용 패턴 목록" 대조 필터 추가~~ — D5~D7로 완료(javascript만 실증, 나머지 언어는 빈 상태)
2. ~~Tier B 트리거 오탐/이중계산 로그를 쌓아 hook 재귀 업데이트로 자동 보정~~ — D14(`tier_b_hook.py`)로 재귀 억제 루프 신설·검증 완료. 단, `sk-`/`eval(` 오탐 자체는 이미 코드로 직접 고쳤고(D12/D17), 이 훅은 *앞으로 발견될* 새 오탐용
3. ~~피드백 블록의 7단계 질문 생성을 수기가 아니라 LLM 호출로 자동화~~ — D11로 코드 구현 완료, D56으로 기본 제공자를 NVIDIA Build로 전환, D58로 라이브 검증+모델 교체 완료(2026-07-06). **Anthropic 경로는 여전히 라이브 미검증**(ANTHROPIC_API_KEY 필요)
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
14. ~~판단 블록 3축을 LLM-as-Judge 수준으로 정량화(EVALUATION.md의 "열위(인정)" 항목)~~ — D27~D30(`judgment/subrubric.py`)으로 규칙기반 서브루브릭 구현·Study-Match-/LMS 재검증 완료. ~~서브축 construct 대표성의 외부 검증~~ — D35로 웹서치 기반 문헌 근거(SATD 탐지, CVSS/FindBugs confidence-severity 분리, 고전 검사이론 변별도 지수, Haladyna item-writing guideline, item exposure control) 확보, `location_signal`→`rationale_signal()` 교체·`risk` 공식 게이팅 구조로 변경 완료. **단, "이 문헌들이 이 도메인(레포 리뷰)에 그대로 전이되는가"는 논문 자체의 실증이지 이 시스템에서 실증된 게 아님 — 사람이 직접 채점한 것과 비교하는 검증은 여전히 안 함(D119: 라벨링 인프라는 준비 완료 — `judgment_precision_labels.jsonl` 50건 계층표집 — 라벨러 2인 배정만 남음)**. `exposure_client`의 "server" 문자열 휴리스틱 등 나머지 도메인 특화 서브축은 이번 라운드에서 손대지 않음(대체할 문헌을 못 찾음, `SUBRUBRIC_DRAFT.md`에 정직하게 기록). LLM-as-Judge 자체(자연어 논증 평가)로의 전환도 여전히 안 함, 규칙기반의 정량화 버전일 뿐
15. ~~Reflection 판정이 너무 쉽게 확정됨(POC_TEST.md 문제4)~~ — D32~D34로 완료. AND-4(너무 엄격, B안 모범 예시도 탈락) → "self_error_recognition 필수 + 나머지 2/3"으로 재보정, B안 모범 예시=True/피상적 답변=False/자기오류인식 없는 프로브=False 3건 전부 실측 확인. **단, 4개 서브신호 각각의 confirmed 패턴은 아직 예시 1건씩만 시드됨**(다양한 실제 답변으로 더 채워야 재현율이 오름)
16. ~~D38 발견에 대응해 cognition-isolation용 재귀 hook 신설~~ — D39~D41로 완료. `isolation_hook.py`/`isolation_classifier.py`가 4개 카테고리(role_separation/perf_optimization/alt_storage_or_scope/domain_irrelevance)로 6개 실제 Codex 답변 중 5건을 "타당한 근거"로 정확히 분류, 근거 부족한 1건(authToken.js)은 성급히 확정 안 함. **단, 이 6건은 카테고리 패턴을 도출한 바로 그 데이터라 held-out 검증이 아니다** — 다른 repo의 새 답변으로 재검증해야 진짜 일반화 여부를 알 수 있음. `score_findings.py`에도 아직 연결 안 함(학생 답변 입력 자체가 정적 스캔 파이프라인엔 없음)
17. ~~서브루브릭 4서브축의 고정 가중치를 재귀적으로 조정 가능하게~~ — D49(`subrubric_hook.py`)로 완료. 실측 데모로 `mitigation_present` 가중치를 discounted로 내린 뒤 실제 finding 2건의 버킷이 서로 다른 방향으로 바뀌는 것까지 확인. **신규**: discounted→trusted로 되돌리는 로직(aligned 누적 기반 복귀)이 아직 없어 한쪽 방향으로만 조정됨. 서브루브릭 가중치 조정과 idiom_hook/isolation_hook/reflection_hook의 재귀 로직 4개가 이제 전부 병렬로 존재하는데, 이들 사이의 실행 순서·상호작용(예: idiom_filter가 question_value를 덮어쓴 뒤에 subrubric 가중치가 다시 조정되면 어떤 순서로 재계산해야 하는지)은 아직 검토 안 함
18. ~~`NVIDIA_API_KEY_1`을 확보해 라이브 실행~~ — **2026-07-06 완료(D58)**: 87개 모델 전수조사, 19개 모델이 tool_choice 100% 준수 확인. `nemotron-3-nano-omni-30b-a3b-reasoning`은 실제로 산문 응답(예견된 실패 경로가 라이브로 확인됨), `nemotron-3.3-super-49b-v1.5`는 tool_calls는 왔지만 arguments가 깨진 JSON(신규 실패 유형). Anthropic 대비 품질 비교는 여전히 미확인(ANTHROPIC_API_KEY 필요). 상세: [`SURVEY_RESULTS.md`](./SURVEY_RESULTS.md)
19. **신규(D57)**: 새로 만든 "설계_논리"·"자기_수정" 2축은 아직 실제 학생/지원자 답변으로 단 한 건도 채점해본 적이 없음 — `auto_score_self_correction()`을 D37 실측 케이스(Bookshelf.jsx XSS 답변)에 돌려본 결과 1/5점(오류를 전혀 인정하지 않음)으로 나온 것도 그 케이스가 애초에 `reflection_signal.py` 재현율 문제의 예시였기 때문(D34 COST와 동일한 한계 — self_error_recognition confirmed 패턴이 1개뿐이라 과소탐지). 실제 다양한 답변으로 자동 초안과 사람 판정이 얼마나 어긋나는지 비교하는 게 다음 검증 순서
20. **신규(D59)**: Depth Ladder 7단계 → FR-5.7의 L1~L5 이해단계 압축 규칙이 어디에도 정의돼 있지 않음(L1=What·L5=Transfer만 명명, L4=Trade-off는 예시로만 등장, L2·L3는 공백). 5축 채점 프레임워크도 FR스펙/`interview_rubric.py`/팀 ROAF 문서(`코드이해도_평가_질문및채점기준.md`) 3곳이 서로 다름(축 이름·척도 1~5 vs 1~3 모두 불일치). A안(김만서)/B안(박진용) 원본 문서도 로컬에 없어 팀 자체 하이브리드 권고(`TEAM_POC_SUMMARY.md`)를 당장 착수할 수 없음. 상세 근거와 회의 안건은 [`METHODOLOGY_AUDIT_HANDOFF.md`](./METHODOLOGY_AUDIT_HANDOFF.md) 참고 — 전부 팀 결정 필요, 코드로 해소 불가

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
