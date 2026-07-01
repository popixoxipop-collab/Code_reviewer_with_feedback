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
| ~~위치 신호(파일명 힌트)~~ → **설계근거 신호(rationale)** (D35로 교체) | 코드 내 코멘트에 명시적 설계 설명 언어가 있는가(있으면 상, 부채 시인 언어면 하) | `subrubric.rationale_signal()`(파일 내용 스캔) | 0~3 |
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
| 트리거 신뢰도 (D35로 게이팅 방식 변경) | 오탐 억제 필터(`tier_b_suppression_filter`)를 통과했고 매치 조건 자체 신뢰도가 높은가 | suppression 통과 여부 | 0~3, **낮으면(0) 아래 3개 서브축 합산과 무관하게 총점을 "하" 구간으로 제한** |
| 노출 범위 | 문제 코드/데이터가 외부 접근 가능 경로에 있는가 (client vs server) | 파일 위치 | 0~3 |
| 시나리오 구체성 | `matched_text`만으로 구체적 공격/오류 상황을 즉시 서술 가능한가 | matched_text 내용 | 0~3 |
| 확산 범위 | 동일 위험 패턴이 몇 개 파일에 반복되는가 | repeated-pattern 파일 수 | 0~3 |

각 축 0~12점 → 기존 파이프라인과의 하위호환을 위해 **상(9~12)/중(5~8)/하(0~4)**로
재매핑해서 `priority` 산출 로직(`idiom_hook.py` threshold 등)은 그대로 재사용 가능하도록
설계했다. (위험도 축만 D35 이후 단순 합산이 아니라 신뢰도가 심각도를 게이팅하는 공식 —
아래 문헌 근거 참고)

## 문헌 근거 (D35)

POC_TEST.md가 D31 검증 과정에서 "이 4개 서브축이 정말 해당 construct를 대표하는 분해인지
외부 검증이 없다"고 지적한 데 대한 응답으로 각 축을 웹서치로 재검토했다. 근거가 없던
서브축은 교체했고, 근거가 있던 서브축은 인용을 남기고 그대로 유지했다.

**Design Intent**
- 반복성/일관성, 관용패턴 정합성 → Miltiadis Allamanis & Charles Sutton, ["Mining Idioms
  from Source Code"](https://arxiv.org/abs/1404.0417) (FSE 2014) — 빈도 기반 코드 관용구
  탐지(FREQTALS)가 표준 방법론임을 확립
- 설계근거 신호(구 위치 신호) → Aniket Potdar & Emad Shihab, "An Exploratory Study on
  Self-Admitted Technical Debt"(ICSME 2014); Maldonado & Shihab(2015) — 의도성의 근거는
  코드 코멘트의 명시적 시인/설명 언어라는 게 SATD 탐지 연구의 핵심 방법론. **위치 신호(파일명
  힌트)는 이 문헌들과 무관한 근거 없는 휴리스틱이었어서 rationale_signal()로 교체**
- 대응 조치 존재 → 대체할 문헌을 찾지 못함, 약한 보조 신호로 유지(정직하게 기록)

**Question Value** (재설계 없이 근거만 보강, 변경 없음)
- 트레이드오프 존재 → 고전 검사이론의 변별도 지수(discrimination index, point-biserial
  correlation) — [Classical Test Theory](https://en.wikipedia.org/wiki/Classical_test_theory)
- 레포 종속성 → Thomas Haladyna & Steven Downing, item-writing guideline(1989, 2002 개정;
  Rodriguez & Albano 2017 22-rule 축약판) — construct-irrelevant variance 최소화 원칙
- 관용패턴 오염도(역채점) → Computerized Adaptive Testing의 item exposure control 문헌 —
  반복 노출/확인된 문항은 변별력을 잃고 시험 보안 문제가 된다는 원칙
- Depth Ladder 확장성 → Haladyna guideline의 단일 인지수준 출제 원칙 + Bloom's Taxonomy의
  고차 인지 요구 원칙(팀 원 Notion 문서, 손진원/김만서 방법론 비교에서 이미 검토)

**Risk**
- CVSS(Common Vulnerability Scoring System)는 Exploitability 지표와 Impact 지표를
  애초에 분리해서 다룸
- FindBugs/SpotBugs 문헌 — confidence(신뢰도)는 rank/severity(심각도)와 별개 축으로 다룸,
  "confidence was originally called priority" 등 신뢰도·심각도 분리가 정착된 관행임을 확인
- **적용한 변경**: 기존엔 trigger_confidence를 나머지 3개 심각도 서브축과 단순 합산했다 —
  두 문헌 모두 이걸 하지 말라고 한다(신뢰도 낮은데 그럴듯한 finding이 신뢰도 높은 경미한
  finding과 동점이 되는 문제). `score_risk()`를 신뢰도가 심각도 총점을 게이팅하는 구조로
  변경(신뢰도=0이면 심각도 무관하게 "하" 구간으로 제한)

## 설계 결정

```
# D27: 판단 블록 3축(설계의도/질문가치/위험도)에 서브루브릭 4항목씩 도입
#   WHY: 현재 규칙기반 상/중/하는 판정 근거가 한 줄 설명뿐이라 감사 불가 —
#        EVALUATION.md가 스스로 인정한 "LLM-as-Judge 정량화 열위"를 메우는 지점.
#        서브축은 기존 인지 블록 출력 필드(fan_in/pattern_key/matched_text/trigger)만
#        재사용해 새 스캔 로직 없이도 근거 기반 채점이 가능함
#   COST: finding당 채점 항목이 3개→12개로 늘어 규칙/프롬프트 유지보수 부담 증가,
#        3분위 컷오프(9/5)가 아직 실측 데이터 없이 임의로 잡은 값
#   EXIT: 과하면 축당 서브항목 2개로 축소. 컷오프는 상수로 분리해 실측 후 재보정.
#        LLM 호출 없이도 규칙기반 그대로 서브축 값만 로그로 남기는 감사 트레일
#        용도로 축소 운용 가능

# D28: 서브축 총점(0~12) → 기존 상/중/하 문자열로 재매핑해 하위호환 유지
#   WHY: idiom_hook.py/priority 로직이 이미 "상/중/하" 문자열에 의존 —
#        서브루브릭 도입이 기존 판단 블록 소비자 코드를 깨면 안 됨
#   COST: 9/5 컷오프가 임의적 — 데이터 쌓이기 전까진 근거 없는 임계값
#   EXIT: 컷오프를 SCORE_THRESHOLDS 상수로 분리해두면 idiom_feedback_log류
#        데이터가 쌓인 뒤 자동 재보정 가능

# D35: 4서브축 분해를 문헌 근거로 재검토(POC_TEST.md D31의 "외부 검증 없음" 지적 응답)
#   WHY: 근거 없는 휴리스틱(design_intent.location_signal)을 SATD 탐지 문헌(Potdar &
#        Shihab 2014) 기반 rationale_signal()로 교체. risk 축은 CVSS/FindBugs 문헌이
#        "신뢰도와 심각도는 별개 축"이라 명시하는데 기존 구현은 단순 합산해서 위반하고
#        있었음 — 신뢰도가 심각도를 게이팅하는 구조로 변경. question_value 4축은 문헌
#        검토 결과 이미 근거가 있어(변별도 지수/Haladyna/item exposure control) 재설계
#        없이 인용만 보강
#   COST: rationale_signal()이 repo_root 파일 I/O를 요구해 cognition-isolation/
#        tier-b-risk finding에도 파일 읽기가 추가됨(이전엔 diffusion만 읽었음).
#        risk 축은 여전히 최종 3단계(상/중/하) 하나로 뭉개져서 신뢰도·심각도 두
#        construct를 최종 사용자에게 완전히 분리해 보여주진 못함(subrubric.sub에는 남음)
#   EXIT: rationale_signal의 인디케이터 정규식은 영어/한국어 일부만 커버 —
#        오탐/누락이 쌓이면 idiom_hook류 재귀 학습 루프로 교체 검토. risk를
#        confidence/severity 두 필드로 완전 분리하려면 apply_subrubric() 반환
#        스키마만 바꾸면 됨(score_risk 내부 로직은 이미 분리돼 있음)
```

## 상태

**구현 완료 — `judgment/subrubric.py`(D27~D30) + `judgment/score_findings.py`에 연결됨.
D35로 문헌 근거 재검토·일부 서브축 교체까지 완료.**

1. ~~`score()` 함수의 각 `findings.append(...)` 블록에 서브축 점수 계산 로직 추가~~ — 완료
2. ~~`SCORE_THRESHOLDS` 상수 분리~~ — `subrubric.py`의 `THRESHOLDS`로 분리 완료(D28)
3. ~~최소 1개 실제 repo로 재실행해 기존 상/중/하 출력과 회귀 비교~~ — Study-Match-(4 findings)
   + jxxnixx/LMS(8 findings, `run_pipeline.py` 전체) 재실행 완료, 크래시 없음. **위험도 축은
   전 findings에서 기존 값과 100% 일치**(risk가 사용자 대면 가장 민감한 축이라 우선 보존).
   질문가치 축은 4건 중 1건(`tier-b-risk:firebase.ts`, 중→상)이 재계산으로 값이 바뀜 —
   근거: `mitigation_present`/`scenario_specific` 등 4개 서브축이 전부 높게 나와 원래 단일
   추정값(중)보다 근거가 두꺼워졌기 때문. 설계의도 축은 전 findings에서 자유서술 텍스트
   → 상/중/하 정량값으로 형식이 바뀜(의도된 변화, 값 자체의 정오 비교 대상 아님). 상세
   비교는 [`examples/study_match/judgment_output.json`](../examples/study_match/judgment_output.json)
   git 히스토리 참고
4. ~~Signal→Construct 매핑의 외부 검증(POC_TEST.md D31 지적)~~ — D35로 웹서치 기반 문헌
   근거 확보 완료. `design_intent.location_signal`(근거 없음) → `rationale_signal()`
   (SATD 탐지 방법론 근거)로 교체, `risk` 축 공식을 CVSS/FindBugs 원칙(신뢰도≠심각도)에
   맞게 게이팅 구조로 변경. Study-Match-/LMS 재검증 완료, 크래시 없음. **단, 여전히
   "이 문헌들이 실제로 이 도메인(레포 리뷰)에 그대로 전이되는지"는 논문 자체의 실증이지
   이 시스템에서 실증된 게 아님** — 사람 채점과의 직접 비교(원래 다음 단계 항목)는 아직
   남아있음
5. ~~서브축을 고정 가중치가 아니라 재귀적으로 신뢰도를 조정 가능하게~~ — D53
   (`judgment/subrubric_hook.py`)로 완료. idiom_hook과 동일한 candidate→threshold→조정
   구조를 "패턴"이 아니라 "서브축 가중치"에 적용. 가중치 기본값(1.0)에서는 정규화가
   항등함수라 D27~D35 출력과 100% 하위호환(Study-Match- 재실행으로 확인). 아래 "재현
   가능한 데모"에 실제 가중치 조정이 버킷을 바꾸는 것까지 실측했다.

## 재현 가능한 데모 — 서브축 가중치 재귀 조정 (D53)

`design_intent.mitigation_present`는 문헌 근거가 가장 약한 서브축이라고 D35에서 이미
표시해뒀다. 이 서브축에 "misaligned" 피드백을 3회(threshold) 기록하면 무슨 일이 일어나는지
그대로 재현 가능하다.

```bash
python3 judgment/subrubric_hook.py feedback design_intent mitigation_present misaligned \
  "architecture-diffusion 계열엔 mitigation 개념 자체가 성립 안 하는데 중립값 1이 노이즈로 얹힘" \
  "architecture-diffusion:App.tsx"
python3 judgment/subrubric_hook.py feedback design_intent mitigation_present misaligned \
  "동일 사례 재확인" "architecture-diffusion:App.tsx"
python3 judgment/subrubric_hook.py feedback design_intent mitigation_present misaligned \
  "repeated-pattern 계열도 동일 문제" "repeated-pattern:onSnapshot"
python3 judgment/subrubric_hook.py update design_intent   # → mitigation_present: trusted(1.0)→discounted(0.3)

python3 judgment/score_findings.py <scan.json> <repo_root>   # 재실행
```

**실측 결과** (Study-Match- 4 findings, design_intent total 기준):

| Finding | 가중치 적용 전(1.0) | 적용 후(0.3) | 변화 |
| --- | --- | --- | --- |
| `cognition-isolation:Competitions.tsx` | 5(중) | 5(중) | — (mitigation_present가 중립값 1이라 영향 작음) |
| `architecture-diffusion:App.tsx` | 5(중) | 5(중) | — |
| `tier-b-risk:firebase.ts` | 7(중) | 6(중) | **하락** — mitigation_present가 3(강한 긍정 신호)이었는데 할인됨 |
| `repeated-pattern:onSnapshot` | 8(중) | **9(상)** | **상승, 버킷 경계 넘음** — 정규화 분모가 줄면서 나머지 서브축의 상대 비중이 커짐 |

**교훈**: 서브축 하나를 할인하는 게 "그 축만 조용히 빠지는" 게 아니다. 정규화(`_normalize`)가
가중치 합계 기준 상대값이라, 할인된 서브축의 원래 값(neutral=1 vs 강한 신호=3)에 따라
남은 findings이 서로 다른 방향으로 움직인다. 데모 상태는 재현 후 초기화했다
(`judgment/subrubric_weights/design_intent/weights.json`을 `{"promotion_threshold": 3,
"sub_axes": {}}`로 복원, `feedback_log.jsonl` 삭제) — 커밋된 상태는 전부 가중치 1.0
기본값이다.
