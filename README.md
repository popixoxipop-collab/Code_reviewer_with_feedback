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
| [`judgment/idiom_filter.py`](./judgment/idiom_filter.py) | 판단 | finding의 `pattern_key`가 confirmed 관용 패턴과 일치하면 질문가치를 낮춤 (언어별 저장소 참조) |
| [`judgment/idiom_hook.py`](./judgment/idiom_hook.py) | 판단 | 관용 패턴 재귀 업데이트 훅 — 피드백 로그 적재(`feedback`) + threshold 도달 시 candidate→confirmed 승격(`update`) |
| [`judgment/idioms/<lang>/`](./judgment/idioms/) | 판단 | 언어별(javascript/python/java/c/cpp/swift) 관용 패턴 상태(`idiom_patterns.json`)와 피드백 로그(`idiom_feedback_log.jsonl`) |
| [`judgment/tier_b_hook.py`](./judgment/tier_b_hook.py) + [`tier_b_suppression_filter.py`](./judgment/tier_b_suppression_filter.py) | 판단 | Tier B 오탐을 (trigger, matched_text) 단위로 재귀 억제(idiom_hook과 동일 패턴). "인지 블록용"으로 요청됐지만 신뢰도 판단이라 판단 블록에 위치(D14) |
| [`feedback/depth_ladder_template.md`](./feedback/depth_ladder_template.md) | 피드백 | What→How→Why→Alternative→Trade-off→Constraint→Reflection 7단계 강제 템플릿 |
| [`feedback/generate_questions.py`](./feedback/generate_questions.py) | 피드백 | 판단 블록 출력을 받아 Anthropic tool-use로 7단계 질문을 실제 LLM 호출로 자동 생성(스키마 강제, 필드 누락 시 예외) |
| [`examples/study_match/`](./examples/study_match/) | 전체 | 실제 공개 repo(Study-Match-)에 3블록 전부를 돌린 실행 결과, 관용 패턴 필터 데모 포함 |
| [`pipeline/run_pipeline.py`](./pipeline/run_pipeline.py) | 전체 | 인지→판단 실행 + `injections.json`에 명시된 재귀 hook(idiom/tier_b)을 순차 주입하며 단계마다 before/after 비교표 자동 생성 |
| [`examples/lms/`](./examples/lms/) | 전체 | 두 번째 실제 공개 repo(jxxnixx/LMS, JS/TS 51파일)에 파이프라인 전체를 돌린 실행 결과 |

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
