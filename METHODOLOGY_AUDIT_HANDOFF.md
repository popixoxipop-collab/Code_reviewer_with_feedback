# AI 파이프라인 구현 현황 감사 핸드오프 — 6문항 전수 확인

> **대상 독자**: 17조 팀 전체, 특히 "AI 기능 처리 로직"을 실제로 작성해야 하는 사람.
> **범위**: 모델/데이터/Decision Point 추출/GitHub 연동/방법론 정합성/채점 방식 6개 질문을
> 코드·문서 전수 grep+read로 확인한 결과. 채팅에만 남기지 않는다는 원칙(decision-externalizer)에
> 따라 문서화. 처음엔 방법론 정합성(5번)만 다뤘으나 이번에 1~4·6번까지 범위를 넓혔다(D60).

## TL;DR

| # | 질문 | 답 |
| --- | --- | --- |
| 1 | 질문생성 LLM / 채점 LLM, 같은 모델? | **채점용 LLM 자체가 없음.** 질문생성만 외부 API(NVIDIA Build 기본, Anthropic 대체) LLM 사용. 채점(judgment)은 100% 규칙 기반, LLM 미사용 |
| 2 | CodeSearchNet 활용 방식 | **코드에 0건.** 과제정의서(pptx) "활용 데이터"란에만 이름이 있고, 파인튜닝·RAG·벤치마크 참조 어느 용도로도 실제 사용된 흔적 없음 |
| 3 | Decision Point 추출 방법 | **(b)에 가깝지만 정확히는 "순수 정적분석 → 그 결과에 LLM이 질문만 얹음".** 추출 자체는 LLM 관여 0%, 정적분석 100% |
| 4 | GitHub API 실연동 여부 | **미연동.** 로컬 파일 경로(`sys.argv[1]`)만 받음. 대시보드·기여분석 데이터는 100% 합성(과제정의서 자체가 "자체 생성 POC 데이터"라고 명시) |
| 5 | 3단계/L1~L5/5축의 관계 | 별도 상세 — 아래 "5. 방법론 정합성" 섹션(기존 감사 그대로 유지) |
| 6 | 채점 방식(LLM-as-judge/루브릭/컷오프) | **LLM-as-judge 아님(규칙기반).** 5축 루브릭은 코드로 존재(`interview_rubric.py`)하나 실답변 검증 0건. 최종등급명("소유/표면/미흡")은 스펙에 있으나 **컷오프 수치는 스펙·코드 어디에도 없음** |

---

## 1. 실제 사용 모델 — 질문생성용 vs 채점용

**질문생성용**: `feedback/generate_questions.py`. 기본값 NVIDIA Build `qwen/qwen3-next-80b-a3b-instruct`(D58, 2026-07-06 87개 모델 전수조사로 확정), `FEEDBACK_PROVIDER=anthropic` 환경변수로 Claude 전환 가능(D56). **둘 다 외부 API 호출**이지 자체 파인튜닝·자체 서빙이 아니다(`nvidia_client.py`가 `https://integrate.api.nvidia.com/v1/chat/completions`를 그대로 호출).

**채점용**: **존재하지 않는다.** `judgment/*.py` 전체를 `anthropic|openai|nvidia|api_key|urllib.request|requests.get|requests.post`로 grep한 결과 **0건** — 판단(채점) 블록은 LLM을 아예 호출하지 않는다. `judgment/subrubric.py`가 규칙 기반으로 0~12점을 합산해 상/중/하로 매핑하고, `feedback/interview_rubric.py`의 5축 자동채점(`auto_score_self_correction()` 등)도 `reflection_signal.py`의 정규식 매칭 결과를 그대로 승격하는 방식 — **LLM 호출이 코드 어디에도 없다.**

→ **"둘이 같은 모델인가"라는 질문 자체가 성립하지 않는다** — 하나(질문생성)만 LLM이고 하나(채점)는 애초에 LLM이 아니다. `POC_TEST.md`도 이걸 설계 철학으로 명시: *"LLM에게 '몇 점 줘'라고 묻는 대신 ... 규칙식"*.

---

## 2. CodeSearchNet 실제 활용 방식

**세 옵션(파인튜닝/RAG/벤치마크) 중 어느 것도 아니다 — 코드에 전혀 없다.**

`grep -rn "CodeSearchNet" --include="*.py" --include="*.md" .` → **0건**. 유일한 등장 위치는
`AI_17조_조별_과제_정의서.pptx`의 "활용 데이터" 칸: *"CodeSearchNet : 코드 분석·질문 생성"* — 이건
**의도 선언**일 뿐 구현이 아니다. `feedback/generate_questions.py`는 CodeSearchNet 없이도 finding별
실제 코드 스니펫(cognition 블록이 읽은 것)을 프롬프트에 직접 삽입해 질문을 생성한다 — 즉 **CodeSearchNet
없이 이미 동작하는 파이프라인**이라, 지금 상태로는 MEAS-02(Decision Point 추출)에 CodeSearchNet이
필요한 지점 자체가 없다.

→ **MEAS-02 방법론에 영향**: 만약 CodeSearchNet을 파인튜닝용으로 쓰기로 하면(자체 모델 학습) 지금의
"정적분석 100%" 구조(3번 답 참고)를 상당 부분 대체해야 하고, RAG로 쓰기로 하면 임베딩 인덱스·검색
레이어를 처음부터 추가해야 한다 — 둘 다 **현재 코드에 훅(hook) 자체가 없어 어느 쪽이든 신규 구현**이다.

---

## 3. Decision Point 추출 — 실제로 어떻게 하는가

**(a) 순수 LLM도 아니고, 흔히 말하는 "(b) 결합"도 정확히는 아니다. 더 정확히는: 추출은 100% 정적분석, LLM은 이미 추출된 결과에 대한 질문 문구만 생성한다(순차적 분업, 상호 개입 없음).**

- **인지 블록** (`cognition/two_tier_scan.py`): Tier A(구조 — import 그래프 fan-in/fan-out, `isolation`/`diffusion`/`repeated-pattern` 탐지) + Tier B(위험 키워드 트리거 시에만 발동하는 내용 스캔 — `dangerouslySetInnerHTML`, 시크릿 패턴 등). **전부 regex/그래프 알고리즘, LLM 미사용.**
- **판단 블록** (`judgment/score_findings.py`, `subrubric.py`): 인지 블록이 뽑은 finding 후보에 우선순위·심각도를 규칙으로 매김. **여기도 LLM 미사용.**
- **여기까지가 "Decision Point 추출"의 전부**다 — 어떤 파일의 어떤 지점이 "검증할 가치가 있는가"는 이 두 블록이 100% 결정한다.
- **피드백 블록** (`feedback/generate_questions.py`)에 가서야 LLM이 처음 등장하는데, 이때 LLM은 "이 지점이 Decision Point인가"를 판단하지 않는다 — **이미 확정된 finding을 받아 그것에 대한 자연어 질문 문구만 생성**한다(Depth Ladder 7단계 필드 채우기).

→ 굳이 셋 중 고르라면 **(b) 정적분석+LLM 결합**에 가장 가깝지만, 이 표현이 오해를 줄 수 있는 지점은
"결합"이 아니라 **"직렬 파이프라인"**이라는 것 — 정적분석과 LLM이 같은 판단을 나눠 갖거나 서로
검증하는 구조가 아니라, 정적분석이 100% 결정한 뒤 LLM은 그 결과를 절대 건드리지 않고 표현만
바꾼다. (b)로 문서화한다면 이 순서·경계를 명시해야 오해가 없다.

---

## 4. GitHub API 실연동 여부 + 구현/설계 경계

**미연동. POC 목(mock)도 아니고, 아예 호출 코드 자체가 없다.**

- `grep -rn "PyGithub|api.github.com|octokit|GITHUB_TOKEN|Github(" --include="*.py" .` → **0건**
- `cognition/two_tier_scan.py:210`: `repo_root = sys.argv[1] if len(sys.argv) > 1 else "."` — **로컬 파일시스템 경로**를 받는다. GitHub URL을 받아 클론하거나 API로 커밋/PR/이슈를 가져오는 코드가 없다(사람이 미리 `git clone`해서 로컬 경로를 넘겨야 함).
- 대시보드(`frontend/mockups/dashboard.html`)의 학생/팀/개입 데이터는 **전부 제가 손으로 채운 합성 데이터**다. 과제정의서(`AI_17조_조별_과제_정의서.pptx`) "활용 데이터"란도 스스로 *"자체 생성 POC 데이터: 운영 대시보드"*라고 명시하고 있어, 이건 이 프로젝트가 처음부터 인지하고 있던 경계다.

**구현됨 vs 설계만 — 경계표**:

| 구분 | 상태 | 근거 |
| --- | --- | --- |
| 인지 블록 정적 스캔(fan-in/fan-out/위험트리거) | ✅ 구현+로컬실행 검증(Study-Match-/LMS/RunPod_Deploy_Agent/Shadowbroker 4개 공개 repo) | `cognition/two_tier_scan.py` |
| 판단 블록 규칙 채점 + 재귀 hook(idiom/tier_b/isolation/reflection) | ✅ 구현+검증 | `judgment/*.py` |
| 피드백 블록 LLM 질문생성(Depth Ladder 7단계) | ✅ 구현, 실제 API 호출 검증(87모델 전수조사, `SURVEY_RESULTS.md`) | `feedback/generate_questions.py` |
| 5축 인터뷰 채점 루브릭 | ✅ 코드로 존재(D57), ❌ 실답변 검증 0건 | `feedback/interview_rubric.py` |
| GitHub API 연동(PR/Issue/commit 실시간 수집, "기여 범위 분석") | ❌ 미구현, 로컬 경로만 | 위 grep 결과 |
| CodeSearchNet 활용 | ❌ 미구현 | 2번 항목 |
| 운영 대시보드 실데이터 연결(FR-5.x) | ❌ 100% 합성 | `frontend/mockups/dashboard.html` |
| 개입 관리 워크플로우 백엔드(FR-6, 상담기록/멘토링요청/보강세션) | ❌ 미구현(화면 목업만) | 저장/조회 API 없음 |
| L1~L5 이해단계 히트맵(FR-5.7) 실데이터 집계 | ❌ 미구현, 매핑 규칙 자체도 미정의(5번 참고) | — |
| 최종등급(소유/표면/미흡) 산출 | ❌ 미구현, 컷오프 미정의(6번 참고) | — |

**7주 안에 실제로 구현되는 부분/설계로만 두는 부분의 경계**는 팀이 정할 문제지만, 지금 코드 기준으로는
"✅"가 곧 **이미 실제로 동작이 검증된 범위**이고, "❌"는 **아직 착수 자체를 안 한 범위**다 — 중간
단계(부분구현·미검증)는 없다.

---

## 5. 방법론 정합성 (가장 헷갈리는 지점)

### 5.1 "3단계 고정 구조"란 정확히 무엇인가

**확정 답: 인지(Cognition) → 판단(Judgment) → 피드백(Feedback) 3블록 파이프라인.** 세션 진행
단계가 아니라 **시스템 아키텍처**를 가리키는 말이다.

**근거**:
- `README.md:1` — 저장소 제목 자체가 `"Code Review with Feedback — 인지 · 판단 · 피드백 3블록 리뷰 시스템"`
- `README.md:18` `## 왜 3블록으로 나눴는가` — "기존 코드리뷰 도구는 '사실 파악'과 '판단(채점)'을 한
  단계에서 처리해 경계가 불분명했다. 이 프로젝트는 세 단계를 명시적으로 분리"
- `POC_TEST.md:1` — `"# POC 테스트 — 인지·판단·피드백 3블록 파이프라인 (ROAF-B 형식)"`, 이어서
  6단계 프로세스를 3블록에 명시적으로 매핑(Step1=인지, Step2~3=인지 raw출력, Step4=판단 Rule+재귀hook,
  Step5=`subrubric.py`의 `bucket()`, Step6=Evidence Log)

**왜 "고정"인가**: 인지·판단 두 블록은 LLM을 전혀 안 쓰는 순수 regex/rule 로직이라 같은 입력엔 항상
같은 출력(재현성 100%, `TEAM_POC_SUMMARY.md:40`). **"동적 질문 생성"은 이 고정 파이프라인의
3번째 블록(피드백) 안에서만** 일어난다 — `generate_questions.py`가 고정 evidence를 근거로 LLM을
호출해 질문 문구를 그때그때 생성(1번 항목 참고).

**기각한 후보들**:

| 후보 | 실체 | 기각 근거 |
| --- | --- | --- |
| `subrubric.py` risk축 상/중/하 | 서브루브릭 총점(0~12)의 최종 압축 등급 | "세션 구조"가 아니라 **점수 버킷** |
| Depth Ladder D1 EXIT의 3단계 축소판 | "7단계 과하면 What/Why/Reflection 3단계로 다운그레이드" | **미사용 fallback**, 라이브는 7단계 전부 |
| "A/B/C 3안" | 방법론 제안 3개 묶음 | "단계"가 아니라 "제안 개수" |
| D안의 "질문 깊이: 2단계" | 오프닝→적응형 후속 | 원문에 명시적으로 **2단계** |

### 5.2 3단계(세션) 답변 → L1~L5 환산 규칙이 있는가

**없다. 질문의 전제 자체가 category error다.** "3단계"는 시스템 아키텍처(위 5.1), L1~L5는
학생 이해도 진행도 — 서로 다른 층위라 매핑 대상이 아니다. 실제 세션은 3단계가 아니라 **Depth
Ladder 7단계**(What→How→Why→Alternative→Trade-off→Constraint→Reflection)로 진행되고, 이
전체가 3블록 중 피드백 블록 하나에 들어있다.

FR-5.7 원문(`요구사항명세서 v2.0`, table5 row7) 재확인: *"세션 응답을 이해 단계(**L1 What ~ L5
Transfer**) 기준으로 집계 ... (예: **L1·L2 통과, L4 트레이드오프에서 급락**)"* — 스펙이 이름
붙인 건 L1(What)·L5(Transfer)·L4(Trade-off, 예시로만)뿐, **L2·L3는 정의가 없다.** 저장소 전체+팀
ROAF 문서를 `L1|L2|L3|L4|L5|이해.?단계|heatmap|히트맵`로 grep해도 **0건** — 7단계→L1~L5 압축
규칙 자체가 코드 어디에도 없다.

### 5.3 5축 채점과 L1~L5는 별개 축인가, 파생인가

**완전히 독립. 코드 연결 0건.** 5축(`interview_rubric.py`)은 인터뷰 전체를 놓고 5개 역량을 채점하는
벡터, L1~L5는 FR-5.7에만 등장하는 단일 스칼라 진행도. 게다가 **"5축"이란 이름을 쓰는 프레임워크가
3곳(FR스펙/코드/팀 ROAF문서)에서 전부 다르다**:

| 출처 | 축 이름 | 척도 |
| --- | --- | --- |
| FR-4.1 | 코드이해/설계논리/대안비교/반례대응/자기수정 | 1~5 |
| `interview_rubric.py`(D57) | 구조_인지도/트레이드오프_인지도/대안_탐색_능력/설계_논리/자기_수정(FR 별칭 매핑 있음) | 1~5 |
| 팀 ROAF 문서 | 구조적이해/행위적이해/설계추론/반성적사고/**AI활용능력** | 1~3 |

### 부가 발견 — 이 저장소는 "구현체"가 아니라 5개 경쟁안(A~E) 중 하나

`TEAM_POC_SUMMARY.md`에 따르면 `Code_reviewer_with_feedback`는 팀 5명 각자의 방법론 비교 중
노경천이 맡은 **C안(정적분석)/D안(evidence_bridge)/E안(Reflection Hook)**뿐이다. A안(김만서,
Viva 100점)/B안(박진용, ROAF-B)은 **이 저장소 밖의 별개 문서이고, 원본을 이번 세션에서 찾지
못했다**(`~/Downloads`, scratchpad 전체 검색 완료, 무관한 별개 미니프로젝트 회의록 1건만 발견).

팀 자체 결론(`TEAM_POC_SUMMARY.md:329-336`): *"C안 단독으론 Ownership 검증 불가 → C안을 1차
필터로 두고 A/B안류의 실제 대화형 인터뷰를 붙이는 하이브리드가 다음 단계."* 지금 `generate_questions.py`
(실 LLM 호출)는 이 방향으로 POC 때보다 발전했지만, **실제 학생과의 라이브 세션은 아직 0건**이다.

---

## 6. 채점 방식 — LLM-as-judge? 루브릭 존재? 컷오프?

**LLM-as-judge가 아니다.** `judgment/*.py` 전체에 LLM 호출 0건(1번 항목과 동일 grep 근거).
`POC_TEST.md`가 스스로 명시: *"LLM에게 '몇 점 줘'라고 묻는 대신 ... 규칙식."* 채점은 100%
결정론적 규칙(서브루브릭 0~12점 합산 → 상/중/하 매핑, 또는 정규식 서브신호 개수 → 1~5점).

**5축 루브릭(척도·기준) 존재 여부**: **코드로 이미 존재한다.** `feedback/interview_rubric.py`의
`RUBRIC` 딕셔너리가 5개 축 × 1~5점 각 레벨별 서술을 전부 담고 있다(D57). 단, **실제 학생/지원자
답변으로 단 한 건도 검증된 적이 없다**(README "다음 단계" 19번) — 특히 새로 만든 "설계_논리"·
"자기_수정" 2축은 `reflection_signal.py`의 알려진 재현율 문제(D37, 정성적으로 우수한 답변도
정규식 불일치로 0/4 처리됨)를 그대로 물려받는다.

**최종 등급(소유/표면/미흡) 컷오프**: 등급 **이름은 스펙에 있다** — 요구사항명세서 v2.0 table4
row2: *"등급(소유/표면/미흡)은 최종 회차에만 부여"*(중간 회차는 등급 없이 추이·시그널만). 하지만
**이 세 등급을 가르는 점수 컷오프는 스펙에도 코드에도 전혀 없다** — `소유|미흡`을 저장소 전체에서
grep해도 0건(코드), 스펙에서도 이름만 나오고 수치 기준은 안 나온다. 5축 점수(1~5×5개)를 어떻게
합산해서 이 3등급 중 하나로 떨어뜨릴지가 완전히 미정 상태다.

---

## 팀이 실제로 결정해야 할 것 (회의 안건)

1. **채점 아키텍처**: 지금처럼 판단(판단블록)=규칙기반, 피드백(질문생성)=LLM인 비대칭 구조를
   유지할지, 팀의 하이브리드 권고대로 A/B안류 LLM-as-judge를 5축 최종채점에 도입할지.
2. **CodeSearchNet·GitHub API를 실제로 구현할지, 스펙에서 뺄지**: 둘 다 지금 코드에 훅이 전혀
   없어 "이미 있는데 안 쓰는" 게 아니라 "처음부터 새로 만들어야" 하는 작업량이다.
3. **Depth Ladder 7단계 → L1~L5 압축 규칙, 5축 프레임워크 3종 통일, 최종등급(소유/표면/미흡)
   컷오프 수치** — 셋 다 팀 회의에서 사람이 정의해야 코드로 옮길 수 있다. 지금은 셋 다 완전 공백.
4. **A안/B안 원본 확보**: 하이브리드 권고를 착수하려면 A안(김만서)/B안(박진용) 원본 코드·프롬프트가
   필요한데 로컬에 없다.

## 감사 방법론 (재현 가능하도록 기록)

- 모델/채점: `judgment/*.py`를 `anthropic|openai|nvidia|api_key|urllib.request|requests.get|requests.post`로 grep → 0건
- CodeSearchNet: 전체 `*.py`+`*.md`를 `CodeSearchNet`으로 grep → 0건(pptx 텍스트에만 존재)
- GitHub API: 전체를 `PyGithub|api.github.com|octokit|GITHUB_TOKEN|Github(`으로 grep → 0건, `cognition/two_tier_scan.py:210`에서 `sys.argv[1]`이 로컬 경로임을 직접 확인
- 3단계/L1~L5: `README.md`/`POC_TEST.md`/`TEAM_POC_SUMMARY.md` 원문 대조 + 전체를 `L1|L2|L3|L4|L5|이해.?단계|heatmap|히트맵`로 grep → 0건
- 최종등급 컷오프: 전체를 `소유|표면|미흡`으로 grep(코드 0건) + `요구사항명세서 v2.0.docx`를 python-docx로 재파싱해 table4 row2에서 등급명만 확인(수치 없음)
- A안/B안 원본: `~/Downloads`, scratchpad 전체를 "박진용"/"김만서" 파일명으로 검색 → 없음
