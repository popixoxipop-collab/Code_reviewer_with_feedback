# Track A + Track B + turn_engine.py 통합 벤치마크 결과 (D93)

`feedback/turn_engine.py`(D87)의 적응형 턴 상태기계 안에서 **Track A(질문생성)와 Track B(FR-04-01
5축 LLM-as-judge 채점)를 처음으로 동시에**, 4개 언어(Python/Java/JS/C++) 전부에 대해 측정했다.
이전까지 Track A만 4개 언어로 재실행됐고(D80) Track B는 원본 JS/TS 세트에만 머물러 있었으며,
turn_engine 자체(D89~D92)는 job 성공률/속도만 쟀지 실제 5축 채점과는 결합된 적이 없었다 —
이번이 그 세 갈래(Track A × 4언어 / Track B × 4언어 / turn_engine 적응형)를 처음으로 합친
벤치마크다.

## 방법론

- **답변 스크립트 3종** (D89의 8 findings 재사용): strong(즉시 방어)/weak(4턴 내내 불변,
  둘 다 D89 그대로) + **improving(신규)** — L1~L3는 weak와 동일한 제네릭 답변, reflection
  단계에서만 실제 자기수정 답변으로 교체. risk-type 4건은 신규 저작(D51 confirmed 트리거
  문구로 오프라인 검증), cognition-isolation 4건은 D89의 strong 텍스트를 reflection 답변으로
  재사용(이 카테고리의 `classify_answer()`는 레벨 무관 분류라 그대로 재사용 가능). **8개
  finding 전부 API 호출 전 `classify_answer()`를 직접 호출해 "weak는 L1~L3 전부 surface,
  improving은 reflection에서 defended"를 오프라인으로 확정**했다(전부 통과).
- **Track B 결합**: `run_decision_point()`가 만든 실제 multi-turn transcript를
  `turn_engine._transcript_text()`(기존 헬퍼, 무수정)로 포맷 → `llm_interview_grader.
  grade_answer()`(FR-04-01 공식 5축: 코드_이해/설계_논리/대안_비교/반례_대응/자기_수정)에
  그대로 전달. 기획명세서 확정 결정("질문생성기·채점기 동일 모델")대로 **turn_engine을 실행한
  그 모델이 자기 transcript를 스스로 채점**(별도 채점 전용 모델 없음). 성공한 job만 채점(실패한
  job은 transcript가 불완전해 채점 대상 아님).
- **Track B 정밀도** = 기존 Track B와 동일 정의("strong 평균점수 > weak 평균점수인 비율",
  finding 단위로 짝지어 비교) — 재사용, 새 지표 발명 안 함.
- **자기수정 인식(신규 지표)** = improving과 weak 각각의 자기_수정 축 평균 점수 비교 — 이번에
  처음 결합되는 부분이라 별도로 명시.
- REPEATS=1(1차 정찰, D89와 동일 이유). 8 findings × 3 scripts × 7 models = 168 turn_engine
  job(실제 호출 최대 504회) + 성공 job당 채점 1회.

## 결과

| Model | Job 성공률 | 판정 결과 일치율 | Track B 정밀도 | 자기수정(improving/weak) | 평균 속도 |
|---|---:|---:|---:|---:|---:|
| `qwen/qwen3-next-80b-a3b-instruct` | 100% (24/24) | 100% | 75% | 2.38 / 1.12 | 45.9s |
| `meta/llama-4-maverick-17b-128e-instruct` | 88% (21/24) | 100% | 100% | 2.67 / 1.00 | 7.6s |
| `stepfun-ai/step-3.5-flash` | 83% (20/24) | 100% | 71% | 3.00 / 1.00 | 8.1s |
| `deepseek-ai/deepseek-v4-pro` | 42% (10/24) | 100% | 100% | 3.67 / 1.00 | 29.6s |
| `openai/gpt-oss-120b` | 21% (5/24) | 100% | n/a(표본 부족) | n/a | 2.5s |
| `mistralai/mistral-nemotron` | 13% (3/24) | 100% | n/a(표본 부족) | n/a | 2.5s |
| `mistralai/mistral-large-3-675b-instruct-2512` | 0% (0/24) | n/a | n/a | n/a | n/a |

**판정 결과 일치율은 데이터가 있는 모든 모델에서 여전히 100%** — D89가 확인한 핵심 발견
(강=defended/약=exhausted_at_cap 규칙이 실제 라이브 환경에서 정확히 작동)이 이번 확장
벤치마크에서도 그대로 재확인됐다.

**자기수정 인식이 명확하게 갈린다** — 데이터가 있는 4개 모델 전부에서 improving(2.38~3.67)이
weak(1.00~1.12)보다 뚜렷하게 높다. 특히 qwen 스모크테스트 사례(자기수정=4, 나머지 축은
1~2점)처럼 **다른 축을 인플레이션하지 않고 자기수정 축만 선택적으로 높게 준 사례**가 흔했다 —
5축 채점기가 "그럴듯해 보이니 전체적으로 후하게"가 아니라 축별로 실제로 분별하고 있다는 신호.

## 실패 원인 분석 (전부 실측, 이번에 새로 발견된 것 포함)

| Model | 실패 원인 |
|---|---|
| `deepseek-v4-pro` | 429×12, timeout×2 — D77/D90이 이미 문서화한 단일 키 쿼터 패턴 재현 |
| `mistral-large-3` | 429×18, 키 풀 즉시 소진×6 — D91이 90분 폴링으로도 못 푼 바로 그 차단이 이번 실행 시점에도 여전히 걸려있음(재현) |
| `gpt-oss-120b` | tool_choice 미준수×18 — D66/D80 기존 결함 재현(자유서술 응답) |
| `mistral-nemotron` | **HTTP 500 Internal Server Error×21** — D89 때의 HTTP 400 "DEGRADED"와는 다른 에러 코드. 둘 다 서버측 가용성 문제라는 결론은 같지만, 증상이 시점마다 다르게 나타난다는 새 데이터포인트 |
| `stepfun-ai/step-3.5-flash` | **"Unterminated string starting at..." JSON 파싱 에러×4 — 신규 발견** |
| `meta/llama-4-maverick` | **"Invalid \\uXXXX escape..." JSON 파싱 에러×3 — 신규 발견** |

**신규 발견(중요)**: step-3.5-flash와 llama-4-maverick에서 **Track B 5축 채점 도구 호출 시
tool_calls의 `arguments` 필드가 유효하지 않은 JSON으로 온 사례**를 처음 확인했다. 기존
tool_choice 미준수(모델이 아예 자유서술로 응답, gpt-oss-120b 패턴)와는 다른 실패 모드 —
이번엔 모델이 tool_choice는 지켰지만(도구를 호출하긴 함) 그 인자 문자열 자체가 깨진 JSON이다.
`llm_interview_grader.py`의 D63 COST가 이미 예견했던 것과 정확히 일치한다: "5축×{score,evidence}
스키마가 7필드 DEPTH_LADDER보다 커서 일부 모델의 tool-calling 실패율이 오를 수 있다(미검증)" —
이번 실측으로 검증됨. `evidence` 필드(자유서술 텍스트, 근거 인용 강제)가 길어지면서 이스케이프
처리가 깨지는 것으로 추정되나, 원본 malformed 응답 문자열 자체를 로깅하지 않아(`call_one()`이
에러 메시지만 저장) 정확한 재현 조건은 이번 데이터로 확정 못함 — 계측 추가가 필요한 한계로
아래에 기록.

**qwen의 Track B 정밀도가 75%(6/8)에 그친 이유**: cognition-isolation 2건
(`java:Book.java`, `c_cpp:EasyQtSql_DeleteQuery.h`)에서 strong 답변이 weak와 동일하게
최저점(평균 1.00)을 받았다 — 다른 6건은 전부 strong이 weak보다 확실히 높았다. 이 2건만
유독 낮게 나온 원인(그레이딩 프롬프트가 cognition-isolation류 방어논리를 FR-04-01
5축과 잘 매칭 못하는지, 아니면 이 2개 답변 텍스트 자체의 특성인지)은 이번 데이터만으로는
구분 불가 — 후속 조사 후보.

## 알려진 한계

- REPEATS=1이라 재현성 미측정. 이번 실행은 D89 이후 시간이 흘러 쿼터/서버 상태가 그때와
  달라져 있었다(예: deepseek/gpt-oss/nemotron의 성공률이 D89 최종치보다 낮음, mistral-large-3는
  D91에서 확인한 차단이 그대로 지속) — **모델별 순위를 이 1회 실행만으로 최종 판단하지 말 것**
  (D69/D77 원칙 재확인, 이번엔 특히 더 중요 — 시점 의존성이 실측으로 재확인됨).
- 표본이 작다(모델당 finding 8개 × variant 3개 = 24건, Track B는 이 중 성공한 job만) —
  gpt-oss-120b/mistral-nemotron/mistral-large-3는 성공 표본이 너무 적어(5건, 3건, 0건)
  Track B 정밀도/자기수정 지표를 아예 못 냄(n/a로 정직하게 표시, 억지로 계산 안 함).
- JSON 파싱 실패의 정확한 원인(어떤 텍스트 패턴이 이스케이프를 깨뜨리는지)은 원본 응답을
  로깅하지 않아 미확정 — `call_one()`에 raw arguments 문자열 저장을 추가하면 다음 실행에서
  근본 원인 확정 가능(이번 범위 밖).
- 429 계열 실패(deepseek/mistral-large-3)는 단일 키 한도 아티팩트로 이미 잘 알려진 원인 —
  이 모델들의 진짜 성능과 무관.

## 원본 데이터

- `turn_engine_grading_multilang_results.json` — 168건 전체 raw(turn_engine 결과 + grading 결과)
- `turn_engine_grading_multilang_summary.json` — 모델별 집계
- `benchmark_turn_engine_grading_multilang.py` — 실행 스크립트(재실행 가능, `NVIDIA_API_KEY_1` 필요)
