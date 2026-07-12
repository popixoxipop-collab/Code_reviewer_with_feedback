# γ(에이전트 시뮬레이션) 설계 (D122)

M4의 첫 단계. 실제 학생 모집 없이 "학생 역할 에이전트"로 종단 루프 기계(회차 구조/측정기 불변식/오염방지 4중)를 먼저 검증한다(plan §5.2). 여기서 나오는 효과 크기는 **잠정보고 가능**(D125 Q8) — 최종 주장은 β(실학생) 전용.

## 페르소나

**"3주차 AIVLE 부트캠프 학생"** — 실존 학생을 흉내내지 않고, 이 실험이 감지 가능한 신호를 낼 만한 현실적인 특성만 명시:

- 과제를 빠르게 "돌아가게만" 만드는 데 집중 — 클래스 간 통합(누가 누구를 쓰는지)은 사후에 신경 씀
- 왜 이렇게 설계했는지 먼저 설명하지 않음(질문받으면 답함)
- 반례를 지적받으면 이해는 하지만 즉석에서 해결책을 내는 데 서투름

student-agent(코딩)와 answer-agent(인터뷰 답변) 둘 다 이 특성을 공유해야 채널 간 일관성이 생긴다. **명시적으로 "isolation finding을 만들어라" 같은 지시는 절대 하지 않는다** — 그건 시뮬레이션을 게임하는 것이지 hook 효과를 재는 게 아니다. 대신 과제 프롬프트 자체가 여러 클래스 통합을 요구하도록 설계하고(아래 과제 세트), 페르소나는 "빠르게, 통합은 나중에" 정도의 자연스러운 태도만 준다.

**D122 정정(라운드1 실측 교훈, 2차)**: 1차 라운드1 프롬프트가 "여러 클래스로 나눠도 되고 한 파일에 몰아써도 됩니다 - 편한 대로"라고 파일 분리를 **선택사항**으로 둔 채 실행했더니, student-agent가 실제로 2파일(Student+Main)만 만들었고 P02 finding이 **0건**이었다(P02의 cognition-isolation/architecture-diffusion은 3+파일의 허브 구조가 있어야 신호가 나는데, 2파일 직접참조 구조는 애초에 "고립"이라는 개념이 성립 안 함). **파일 분리는 요구사항으로 고정**(구체적 클래스 이름까지 명시)하되, **그 클래스들을 얼마나 잘 통합하는지는 여전히 페르소나에 맡긴다** — 이렇게 하면 구조적 복잡도(P02가 볼 게 있음)는 보장하면서, 통합 품질(측정 대상)은 게임하지 않는다. 라운드1 재실행 + 라운드2~4 프롬프트에 전부 반영.

**D122 정정(라운드1 실측 교훈, 3차 — 사용자 선택)**: 2차 수정(4클래스 구조 요구)까지 반영해도 finding 0건이었다 — fan_in/hub 계산 버그 2건을 고친 뒤 실제로 확인해보니 원인은 버그가 아니라 **"Main→헬퍼3개→Student"라는 완전한 별 모양 구조엔 애초에 고립·2차 확산점이 성립할 구조적 여지가 없다**는 것(README D122 참고). 사용자가 "과제를 더 복잡하게 재설계"를 선택 — 4클래스에 **2차 계층 클래스 2개**를 추가해(각각 중간 계층 클래스 하나에 의존) 구조적으로 "2차 확산점" 또는 "라우팅되지만 허브 미연결" 패턴이 나올 여지를 만든다. **여전히 어느 쪽이 될지, 얼마나 깔끔하게 연결할지는 지시하지 않는다** — 클래스 이름과 각자의 역할만 고정하고 연결 방식은 student-agent 판단에 맡김(게임 방지 원칙 유지).

## 과제 등가성 (β의 엄밀한 P02 사전 스캔 대신 γ 축소판)

β처럼 참조 solution으로 사전 스캔할 순 없다(학생 역할 자체가 아직 solution을 안 만들었으므로) — 대신 **형태 등가성**으로 대체: 4과제 전부 (a) AI_JAVA_교안.pdf의 실제 유닛에서 유도, (b) 6클래스 구조(모델 1 + 1차 로직 2 + 2차 로직 2 + Main)를 요구사항으로 명시, (c) 개념 범위가 유닛 하나로 국한. 실제 finding 밀도 대조는 β로 미룸(EXIT 참고).

| 회차 | 과제 | 근거 유닛(unit_map) | 요구 클래스(6개) |
|---|---|---|---|
| R1 | 학생 3명 점수 입력받아 평균/최고점/등급(A·B·C) 계산+입력 이력 저장 | 03 사용자로부터입력받기 (p.59,114,118...) | Student(모델) · GradeInputHandler(입력) · ScoreCalculator(평균/최고점) · **GradeRanker(등급판정, ScoreCalculator 결과 사용)** · **InputHistory(입력 이력, GradeInputHandler 결과 사용)** · Main |
| R2 | 온도 섭씨/화씨 변환+변환 이력 저장+단위 유효성 검사 | 04 Java의 연산자 (p.72,74,75...) | TemperatureConverter(변환) · ConversionRecord(모델) · ConversionHistory(이력) · **UnitValidator(단위 유효성 검사, Converter가 사용)** · **ConversionReport(이력 요약 출력, History가 사용)** · Main |
| R3 | 근무시간×시급 급여계산(주40h 초과분 1.5배)+세금 공제+급여명세서 저장 | 05 조건문 (p.102,104,105...) | Employee(모델) · PayrollCalculator(조건부계산) · PayrollReport(출력) · **TaxDeduction(세금 공제, Calculator가 사용)** · **PayslipArchive(명세서 저장, Report가 사용)** · Main |
| R4 | 상품 목록 순회, 총액+재고부족(5개 미만) 리스트+할인 적용+주문 이력 | 06 반복문 (p.108,110...) | Product(모델) · Inventory(반복 로직) · InventoryReport(출력) · **DiscountPolicy(할인 적용, Inventory가 사용)** · **OrderHistory(주문 이력, Report가 사용)** · Main |

## 회차 구조 (k=4, D125 확정)

| 단계 | 내용 |
|---|---|
| R1 개발 | student-agent(신규, meta-정보 없음)가 과제 1 수행 → **격리된 scratchpad 작업공간**(아래 "경로 오염 사고" 참고), 완료 후 오케스트레이터가 `experiments/hook_loop/students/gamma_s1/round1/src/`로 복사 |
| R1 측정 | P02(스캔+판단, 콜 0) → P03(turn_engine, answer-agent=haiku가 D107 계보로 답변) → FR-04-01 5축 채점 |
| R1 동결 | 측정 raw 커밋(temporal firewall이 확인할 대상) |
| R1 처방 | `generate_hook_file.py` → v1 (코드+인터뷰 두 채널 합산, canary 발급) |
| R2 개발 | 같은 persona의 student-agent(신규 컨텍스트, v1 Hook File을 "당신의 개발 환경에 있는 개인 체크리스트"로만 제공 — 실험 설계는 안 알려줌)가 과제 2 수행 |
| R2 측정~처방 | R1과 동일 절차 → v2(증분 병합) |
| R3 | 과제 3, v2 장착 → v3. 이전 회차에서 checkable_condition 통과한 항목의 **정착(재발 안 함)** 확인 시작 |
| R4 | 과제 4, v3 장착 → v4 |

## 측정기 불변식 재확인

student-agent에게 주는 프롬프트는 과제 설명 + (R2부터) Hook File 텍스트만 포함 — "이것은 실험입니다", "P02/P03가 측정합니다" 같은 메타 정보 절대 금지(에이전트가 알면 자연스러운 행동이 아니라 "시험 대비 행동"으로 왜곡됨, 측정 타당도 파괴). answer-agent(인터뷰 답변)도 동일 원칙.

## 지표 5종 계측 방법 (plan §5.3)

1. 재발 곡선+정착률 — 코드채널: 과제가 회차마다 달라 finding_id 자체는 다르지만, `FINDING_KIND_TO_FR_AXIS`로 정규화한 취약축 단위 재발률을 추적(파일명이 아니라 축 단위 비교가 맞음, 과제가 바뀌므로). 인터뷰채널: fr_axis 점수 시계열.
2. FR-04-01 추세 — 3회 중앙값(plan 확정) 대신 γ는 시간/비용 제약으로 **1회 채점 + 명시적 한계 기록**(EXIT 참고, β는 3회 중앙값 필수 유지).
3. Hook 체크리스트 통과율 — `audit_checklist.py`를 R2→R1-hook, R3→R2-hook, R4→R3-hook에 순차 적용.
4. 교안 출처 매핑 정확도 — curriculum_refs가 실제로 그 유닛의 페이지를 가리키는지(현재 generate_hook_file.py의 `_find_curriculum_ref`는 1차 구현이라 유닛 전체 페이지를 그대로 씀 — 이 축은 D121 COST에 이미 기록된 한계 그대로 상속).
5. 인터뷰 방어 도달률 — turn_engine verdict(`defended`/`partial`/`surface`) 비율 추이.

## D122 정정 — 실측으로 발견한 경로 오염 사고 (라운드1 1차 시도, 코드 미채택)

**사고**: `GAMMA_DESIGN.md`를 `experiments/hook_loop/`에, `persona.txt`를 `students/gamma_s1/round1/`에 두고 student-agent에게 `.../round1/src/`에 코딩하라고 시켰다. student-agent가 "디렉터리 관례를 확인"하려고 상위 폴더를 둘러보다가 **이 두 메타 파일을 실제로 발견**했다 — GAMMA_DESIGN.md는 이게 실험이라는 것 자체를, persona.txt는 인터뷰 답변자용 페르소나 지시문을 노출했다. 다행히 이 회차는 아직 동결(git commit)되지 않은 상태였고(temporal firewall이 어차피 미커밋 상태에선 Hook File 생성 자체를 막았을 것), 코드도 채택 전에 폐기하고 재시작했다 — 실측 데이터로 남기지 않음.

**근본원인**: D123(hookfile-isolation-guard.py)이 막는 대상은 "측정 스크립트가 hookfile을 읽는 것"이었지, "student-agent가 실험 메타문서를 읽는 것"은 애초에 위협 모델에 없었다 — Hook File(처방)만 오염 대상으로 여기고, 실험 설계 문서·페르소나 지시문 자체도 동일한 등급의 오염원이라는 걸 놓쳤다. coding agent는 광범위한 파일시스템 접근권을 가진 채로 동작하고, 상위 디렉터리 탐색은 정상적이고 흔한 행동이라(이 agent도 "악의"가 아니라 "관례 확인" 목적으로 그랬다) 디렉터리 배치만으로는 막을 수 없다.

**수정(즉시 적용, 재시도 전)**:
- **작업공간을 repo 밖 세션 scratchpad로 이전**: student-agent의 실제 작업 디렉터리는 `/private/tmp/.../scratchpad/gamma_workspaces/<sid>/<round>/src/` — 이 경로엔 코드 파일 말고 아무것도 없다(GAMMA_DESIGN.md도, persona.txt도, 다른 회차 기록도 전혀 없음). 상위 디렉터리를 아무리 둘러봐도 발견할 메타정보가 구조적으로 없다.
- **완료 후 오케스트레이터(나)가 최종 코드만 repo의 `experiments/hook_loop/students/<sid>/<round>/src/`로 복사** — 측정(P02/P03)은 이 복사본을 대상으로 하고, 원본 scratchpad는 코딩 단계 종료 후 더는 참조하지 않음.
- **메타 파일은 `experiments/hook_loop/_lab/`로 격리**(GAMMA_DESIGN.md, personas/) — student-agent에게 주는 프롬프트 어디에도 이 경로를 언급하지 않고, student-agent의 작업 디렉터리(scratchpad)와는 공통 조상 디렉터리가 아예 없음(repo vs /private/tmp).

WHY: D96 계보(가드 없던 경로로 오염 전파)의 재발 — 이번엔 Hook File이 아니라 **실험 설계 문서 자체**가 그 경로였다는 게 새로운 교훈. COST: 매 회차 코드를 scratchpad→repo로 복사하는 단계가 추가됨(사소함). EXIT: β(실학생) 단계에선 애초에 학생이 자기 컴퓨터에서 작업하므로 이 구체적 위협(같은 repo 안 메타문서 노출)은 사라지지만, "학생에게 실험 세부사항을 알리지 않는다"는 동일 원칙은 동의서/브리핑 설계에서 다시 지켜야 함.

## WHY / COST / EXIT

- WHY: 실제 학생 모집(β) 전에 4중 오염방지 장치·temporal firewall·규칙 예산·병합 로직이 실제 다회차 데이터에서 깨지지 않는지 싸게 먼저 검증한다. 코드 작성은 Claude 구독 비용(NVIDIA 콜 아님)이라 M1/M2보다 오히려 NVIDIA 예산 부담이 적다.
- COST: 과제 형태 등가성은 β 수준(실측 finding 밀도 대조)에 못 미침. FR-04-01은 1회 채점(β의 3회 중앙값 원칙 미적용) — 회차 간 차이가 노이즈인지 진짜 추세인지 γ 결과만으로는 약하게만 말할 수 있음. student-agent는 실제 3주차 학생의 심리/시간압박을 진짜로 재현하지 못함(에이전트 시뮬레이션의 근본적 외적 타당도 한계, plan 7.4에 이미 명시).
- EXIT: β 설계 시 (1) 실제 과제 4개를 P02로 사전 스캔해 finding 밀도 정합 확인, (2) FR-04-01을 3회 중앙값으로 승격, (3) `_find_curriculum_ref`를 curriculum_provenance_audit.json과 교차하는 정밀 매칭으로 교체.
