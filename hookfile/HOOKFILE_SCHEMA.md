# Hook File 스키마 (D121)

> 용어 고정(§0 계보): 이 문서가 정의하는 "Hook File"은 `judgment/`의 "루브릭 보정 훅"(idiom_hook.py 등, 시스템 자기교정)과 무관하다. Hook File은 **교육생 개인**의 측정·질의응답·시행착오 누적 결과를 수료 시점에 남기는 개인화 처방 자산(RPT-02 산출물)이다.

## 그릇(container) — 확정(D125)

1차 그릇은 **정적 규칙 파일**이다. Claude-Code-Hooks-JSON을 그대로 쓰지 않는 이유는 교육생의 실제 개발 환경(Claude Code 사용 여부)에 의존하지 않기 위해서다 — 대신 스키마 자체를 Claude Code Hooks의 event→matcher→handler 구조에 맞춰 설계해서, 나중에 실제 Claude Code 사용자에게는 같은 스키마를 그대로 실행 가능한 Hooks JSON으로 2차 렌더링할 수 있게 한다(`render_targets.py`).

| Hook File 필드 | Claude Code Hooks 대응 개념 |
|---|---|
| `trigger` | matcher (이 규칙이 언제 적용되는가) |
| `checkable_condition` | handler의 판정 로직 (지켰는지 기계로 확인 가능한 조건) |
| `지침_본문` | handler가 하는 일 (사람이 읽는 지시문) |

## 파일 레벨 스키마

```json
{
  "student_id": "string -- 익명화된 교육생 식별자",
  "version": "int -- 회차별 증분(R1 처방=1, R2 처방=2, ...)",
  "generated_at": "ISO8601 -- 결정론적 타임스탬프, args로 주입(Date.now() 금지 원칙과 동일 이유: 재현성)",
  "source_round": "int -- 이 버전을 만든 측정 회차 번호(R1, R2, ...)",
  "canary_uuid": "string -- 파일마다 고유. 5.4 오염 감시용, 절대 재사용 금지",
  "coverage": "float 0~1 -- 진단된 취약축(ENG-01) 중 처방(rule)이 존재하는 비율",
  "provenance_commit": "string -- 이 버전의 근거가 된 측정 raw 커밋 해시(temporal firewall이 검사)",
  "deferred_rules": "array -- 규칙 예산(<=10) 초과로 이번 버전엔 안 들어간 후보(우선순위 순 보존)",
  "rules": "array of Rule -- 아래 규칙 레벨 스키마"
}
```

## 규칙(Rule) 레벨 스키마

```json
{
  "rule_id": "string -- {axis}-{seq} 형태, 예: 코드_이해-01",
  "channel": "\"code\" | \"interview\" -- P02(코드) 또는 P03(인터뷰) 출처 채널(D125 Q9: 두 채널 합산 예산)",
  "취약축": "FR-04-01 5축 중 하나 -- 코드_이해 | 설계_논리 | 대안_비교 | 반례_대응 | 자기_수정 (feedback/interview_rubric.py의 FR_AXIS_ALIAS 값과 정확히 일치해야 함)",
  "tech_area": "string -- DASH-15 기술영역 분류 태그",

  "finding_refs": [
    {
      "source": "judgment_4axis_benchmark.py 또는 실제 판단 블록 실행 결과",
      "finding_id": "judgment/score_findings.py의 finding[\"id\"] 그대로 (예: cognition-isolation:Foo.tsx)",
      "priority": "finding[\"priority\"] 그대로",
      "subrubric_axis": "design_intent | question_value | risk 중 근거가 된 서브루브릭 축"
    }
  ],
  "transcript_refs": [
    {
      "round": "int -- 어느 회차 인터뷰인지",
      "turn_index": "int -- feedback/turn_engine.py transcript 리스트 내 위치(0-based)",
      "level": "turn_engine의 level 값(L1~L3)",
      "fr_axis": "feedback/interview_rubric.py score_card()의 fr_axis 값",
      "score": "score_card()의 score(1~5)"
    }
  ],
  "curriculum_refs": {
    "unit": "P01 unit_map의 unit_id (예: \"01\")",
    "unit_title": "P01 unit_map의 unit_title",
    "source_pages": "P01 unit_map concept의 source_pages 배열 그대로 -- CUR-02 매핑, curriculum_4axis_benchmark.py의 provenance-precision 검증을 통과한 concept만 인용 가능(§4.1 선행 게이트)"
  },

  "trigger": "string -- 이 규칙이 적용되는 조건(작업 설명 유사도 또는 파일 패턴). Hooks matcher 대응",
  "지침_본문": "string -- 실행 가능한 지시문. LLM(Locked qwen)이 finding_refs/transcript_refs/curriculum_refs의 근거 텍스트만 보고 문장화(생성 방식 참고)",
  "checkable_condition": "string -- 다음 회차 산출물에서 기계로 확인 가능한 조건. audit_checklist.py가 이 필드를 파싱해 자동 감사",
  "provenance_hash": "string -- 이 규칙의 근거가 된 개별 측정 산출물(raw json)의 파일 해시"
}
```

## 생성 방식 (결정론 조립 + 최소 LLM)

1. **증거 필드는 결정론적으로 조립**한다: `finding_refs`/`transcript_refs`/`curriculum_refs`는 이미 존재하는 측정 산출물(JSON)에서 파이썬 코드로 직접 채운다. LLM은 이 조립에 관여하지 않는다.
2. **LLM은 `지침_본문` 문장화에만 사용**한다(학생/회차당 1콜 수준) — 근거 필드(1번)를 프롬프트에 그대로 넣고, "이 근거로 실행 가능한 지시문 1개를 써라"만 요청한다. 근거 없이 지침을 만들 수 없다(프롬프트 설계 자체가 강제).
3. 모델은 **Locked qwen3-next-80b**(팀 확정 단일 모델, 이 계획 전체가 그 원칙을 상속) — 별도 모델 선택 없음.

## 규칙 예산 (D125 확정: P02+P03 두 채널 합산 ≤10)

- 상위 취약축 3개 × 축당 규칙 최대 3~4개, 코드(P02)/인터뷰(P03) 두 채널 합산 상한 10개.
- 채널별 배분은 인위적 반반이 아니라 ENG-01이 지목한 축 심각도로 자연 결정.
- 예산 초과분은 `deferred_rules`로 보존(수치 조작 없이 결손 명시, maverick/glm 처리 원칙과 동일).

## 측정기 불변식 (5.2 원칙, 반드시 코드로 강제)

Hook File은 **학생의 개발 환경에만** 존재한다. 채점·스캔·인터뷰 질문생성의 어떤 프롬프트/입력에도 이 파일의 내용이 섞이면 안 된다. `canary.py`/`hookfile-isolation-guard.py`/temporal firewall이 이 불변식을 코드 레벨에서 강제한다(§5.4, `generate_hook_file.py`/`canary.py`에서 구현).
