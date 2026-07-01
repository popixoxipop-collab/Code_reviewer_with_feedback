# 판단 블록 서브루브릭 초안 (LLM-as-Judge 정량화 확장)

`score_findings.py`가 현재 산출하는 3축(`design_intent`/`question_value`/`risk`)은 전부
규칙 기반 상/중/하 단일 판정이다. [`EVALUATION.md`](../EVALUATION.md)의 방법론 비교표는
이 지점을 스스로 이렇게 인정한다:

> 판단 | LLM-as-Judge(Rubric) | 논증 품질 1~5점 정량화 가능 | — | 규칙기반(상/중/하) |
> **열위(인정)** — 정량 점수화·자연어 논증 평가는 우리가 아예 못함

이 문서는 그 빈칸을 메우기 위한 초안이다. 3축을 코드에 이미 존재하는 필드(`fan_in`,
`pattern_key`, `matched_text`, `trigger` 등)를 근거로 삼는 서브축으로 쪼갠다 — 대화형
답변이 아니라 **코드 자체(=finding)를 채점 대상으로 삼는다**는 점에서, 면접 답변을
채점하는 Ownership Score(팀 Notion 문서, 2026-07-01)와는 별개의 루브릭이다.

## Axis 1 — 설계의도 (Design Intent): 이 구조가 의식적 설계 결정인가, 방치/누락인가

| 서브축 | 판정 질문 | 근거로 삼을 기존 필드 | 배점 |
| --- | --- | --- | --- |
| 반복성/일관성 | 동일 패턴이 repo 내 다른 위치에서도 일관되게 나타나는가 (1회성 실수 vs 반복된 설계) | `find_repeated_pattern_files` hit count | 0~3 |
| 관용패턴 정합성 (역채점) | 프레임워크 공식 컨벤션과 일치하는가 — 일치할수록 "생각해서 짠 것"이 아니라 "그냥 따라간 것" | `idiom_filter`의 `pattern_key` + `status`(candidate/confirmed) | 0~3 |
| 위치 신호 | 파일명/디렉토리 구조 자체가 의도적 분리를 암시하는가 | 파일명 힌트(`*service*` 등), entry point 인접도 | 0~3 |
| 대응 조치 존재 | 위험성 finding일 경우, 완화 시도(에러처리·검증)가 주변 코드에 보이는가 | Tier B 매치 주변 컨텍스트 | 0~3 |

## Axis 2 — 질문가치 (Question Value): 이 finding을 물었을 때 이해도 격차가 실제로 드러나는가

| 서브축 | 판정 질문 | 근거 필드 | 배점 |
| --- | --- | --- | --- |
| 트레이드오프 존재 | "왜 이렇게 했나"에 정답이 하나로 안 정해지고 대안이 실재하는가 | fan_in/fan_out 비율, hub 여부 | 0~3 |
| 레포 종속성 | 범용 지식으로는 답 못 하고 반드시 이 코드를 직접 봐야 답할 수 있는가 | edge 구조의 repo-specific성 | 0~3 |
| 관용패턴 오염도 (역채점) | 과거 유사 finding이 idiom_hook에서 "그냥 컨벤션"으로 몇 번 강등됐는가 | `idiom_feedback_log.jsonl` 누적 횟수 | 0~3 |
| Depth Ladder 확장성 | Depth Ladder 7단계(What~Reflection)를 다 채울 만큼 정보가 충분한가 | finding 텍스트 길이·연관 파일 수 | 0~3 |

## Axis 3 — 위험도 (Risk): 실제 보안/신뢰성 문제인가

| 서브축 | 판정 질문 | 근거 필드 | 배점 |
| --- | --- | --- | --- |
| 트리거 신뢰도 | 오탐 억제 필터(`tier_b_suppression_filter`)를 통과했는가 | suppression 통과 여부 | 0~3 |
| 노출 범위 | 문제 코드/데이터가 외부 접근 가능 경로에 있는가 (client vs server) | 파일 위치 | 0~3 |
| 시나리오 구체성 | `matched_text`만으로 구체적 공격/오류 상황을 즉시 서술 가능한가 | matched_text 내용 | 0~3 |
| 확산 범위 | 동일 위험 패턴이 몇 개 파일에 반복되는가 | repeated-pattern 파일 수 | 0~3 |

각 축 0~12점 → 기존 파이프라인과의 하위호환을 위해 **상(9~12)/중(5~8)/하(0~4)**로
재매핑해서 `priority` 산출 로직(`idiom_hook.py` threshold 등)은 그대로 재사용 가능하도록
설계했다.

## 설계 결정

```
# D23: 판단 블록 3축(설계의도/질문가치/위험도)에 서브루브릭 4항목씩 도입
#   WHY: 현재 규칙기반 상/중/하는 판정 근거가 한 줄 설명뿐이라 감사 불가 —
#        EVALUATION.md가 스스로 인정한 "LLM-as-Judge 정량화 열위"를 메우는 지점.
#        서브축은 기존 인지 블록 출력 필드(fan_in/pattern_key/matched_text/trigger)만
#        재사용해 새 스캔 로직 없이도 근거 기반 채점이 가능함
#   COST: finding당 채점 항목이 3개→12개로 늘어 규칙/프롬프트 유지보수 부담 증가,
#        3분위 컷오프(9/5)가 아직 실측 데이터 없이 임의로 잡은 값
#   EXIT: 과하면 축당 서브항목 2개로 축소. 컷오프는 상수로 분리해 실측 후 재보정.
#        LLM 호출 없이도 규칙기반 그대로 서브축 값만 로그로 남기는 감사 트레일
#        용도로 축소 운용 가능

# D24: 서브축 총점(0~12) → 기존 상/중/하 문자열로 재매핑해 하위호환 유지
#   WHY: idiom_hook.py/priority 로직이 이미 "상/중/하" 문자열에 의존 —
#        서브루브릭 도입이 기존 판단 블록 소비자 코드를 깨면 안 됨
#   COST: 9/5 컷오프가 임의적 — 데이터 쌓이기 전까진 근거 없는 임계값
#   EXIT: 컷오프를 SCORE_THRESHOLDS 상수로 분리해두면 idiom_feedback_log류
#        데이터가 쌓인 뒤 자동 재보정 가능
```

## 상태

**초안 — 아직 `score_findings.py`에 코드로 구현되지 않음.** 이 문서는 서브루브릭
구조에 대한 팀 합의를 먼저 굳히기 위한 문서이며, 합의 후 다음 단계는:

1. `score()` 함수의 각 `findings.append(...)` 블록에 서브축 점수 계산 로직 추가
2. `SCORE_THRESHOLDS` 상수 분리 (D24)
3. 최소 1개 실제 repo(Study-Match- 또는 jxxnixx/LMS)로 재실행해 기존 상/중/하 출력과
   회귀 비교
