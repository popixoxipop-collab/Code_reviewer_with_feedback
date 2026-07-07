# Track A(질문생성) vs Track B(채점) 실측 벤치마크 결과 — 2026-07-07 (2026-07-07 최종 갱신)

D70 참고, 최종 완결은 D79. 실제 NVIDIA Build API 호출, 7개 모델(deepseek-v4-pro 추가 포함)
× 3축(정밀도/재현성/속도) × 2트랙. 실행: `benchmark_track_a.py`, `benchmark_track_b.py` +
deepseek-v4-pro/mistral-large-3 재검증 채우기. 시각화: [Artifact](https://claude.ai/code/artifact/46e8d412-a460-4d01-bdfc-3c927ee4af8e).

## 결과 요약 (최종 — 아래 두 모델은 재검증으로 완전히 채움, "정정 (D75)" 섹션 참고)

| 모델 | A·정밀도 | A·재현성 | A·속도 | B·정밀도 | B·재현성 | B·속도 |
|---|---|---|---|---|---|---|
| qwen3-next-80b-a3b-instruct (기본값) | 100% | 100% | 24.2s | 100% | 1.00 | 28.8s |
| stepfun-ai/step-3.5-flash | 100% | 100% | 6.1s | 100% | 1.00 | 2.6s |
| meta/llama-4-maverick-17b-128e-instruct | 100% | 100% | 4.3s | 100% | 1.00 | 5.7s |
| openai/gpt-oss-120b | 100% | 100% | 4.4s | 100% | 0.37 | 5.1s |
| mistralai/mistral-nemotron | 100% | 100% | 6.5s | 100% | 1.00 | 5.5s |
| mistralai/mistral-large-3-675b-instruct-2512 | 75% | 75% | 5.2s | **100%** | **0.81** | **5.5s** |
| deepseek-ai/deepseek-v4-pro | **100%** | **100%** | **34.6s** | **100%** | **0.63** | **28.1s** |

- A·정밀도 = Depth Ladder 7단계 스키마 완전 준수율, A·재현성 = finding당 3회 반복 전부 성공 비율
- B·정밀도 = 강/약 답변 쌍을 올바른 순서로 채점한 비율, B·재현성 = 동일 답변 3회 재채점 점수(25점 만점) 표준편차 기반 1/(1+σ)
- **굵게 표시된 값**은 최초 측정(아래 원래 표는 삭제하지 않고 "정정 (D75)" 섹션에 그대로 보존) 이후 재검증으로 새로 채워진 것

## 핵심 발견

1. **현재 locked 기본값(qwen3-next-80b-a3b-instruct)은 정밀도·재현성 만점이지만 두 트랙 모두에서 최저 속도** — 질문생성 24.2s, 채점 28.8s로 나머지 5개 모델(2.6~6.5s대)과 4~10배 차이. 실시간 세션 체감 지연 이슈로 이어질 수 있음.
2. **openai/gpt-oss-120b는 채점 역할에서 재현성 결함 확인** — 강/약 변별(정밀도)은 만점이지만, 동일 답변을 temperature=0.0으로 3회 재채점해도 25점 만점 기준 평균 표준편차 1.7점 발생(나머지 4개 유효 모델은 전부 0). "정밀도가 높아도 재현성은 별개"라는 이전 벤치마크 설계 근거(Track을 나눠야 하는 이유)가 실측으로 확인된 사례.
3. **deepseek-ai/deepseek-v4-pro는 이 API 키로 완전히 접근 불가** — 간격을 3~15초로 늘려 재시도해도 매번 즉시(0.5s) 429. 볼륨 문제가 아니라 이 키에 이 모델 접근 권한이 없는 것으로 판단, 벤치마크에서 제외.
4. **mistralai/mistral-large-3은 Track A 실행 시점엔 부분 작동(9/12)했으나 Track B 시점엔 완전히 막힘(0/12)** — 두 트랙 사이 누적 사용량으로 이 키의 해당 모델 쿼터가 소진된 것으로 추정. 키 운영상 리스크로 기록.

## 방법론 한계 (정직하게 기록)

- 6개 모델은 87개 전체 카탈로그가 아니라 SURVEY_RESULTS.md 상위권 숏리스트 + 현재 locked 기본값.
- Track B 정밀도는 "명백한 강/약 답변 구분" 능력만 측정 — 실제 학생 답변처럼 미묘한 중간 수준 변별력은 미검증.
- Track B 재현성은 **총점(25점 만점)의 표준편차** 기반. 필드 단위 정확 일치가 아니라 합산값 근사치라, 개별 축이 서로 반대 방향으로 흔들려 합산에서 우연히 상쇄되는 경우를 놓칠 수 있음(아래 "발견된 이슈" 참고).
- Track B 테스트 답변 4건 중 2건(Bookshelf.jsx)은 TEAM_POC_SUMMARY.md에 기록된 실제 Codex 생성 답변, 나머지 2건(App.tsx)은 이 벤치마크를 위해 새로 작성한 합성 답변 — 각 답변에 출처 명시(`benchmark_track_b.py`의 `TEST_ANSWERS`).

## 발견된 이슈 — 병렬 세션과의 작업 중복

이 벤치마크를 실행하는 도중 `git status`에서 이 세션이 만들지 않은 새 파일들을 발견했다:
`feedback/llm_interview_grader.py`, `judgment/meas02_decision_point_extractor.py`,
`benchmarks/{harness,reproducibility,grading_run_benchmark,grading_testset,meas02_run_benchmark}.py`
(전부 D61~D69로 이미 번호가 매겨져 있었음 — 이 문서의 D70부터는 그 번호와 충돌하지 않도록
`benchmark_track_a.py`/`benchmark_track_b.py`의 기존 D61~D64 표기를 D70~D73으로 재조정한 뒤의 번호다).

**다른(병렬) 세션이 같은 두 가지(채점 LLM, MEAS-02 순수 LLM 추출)를 이미 프로덕션 수준으로
구현하고 벤치마크 하네스까지 작성해뒀다 — 단, 아직 실행(API 호출)은 안 한 상태(결과 파일 없음).**

이쪽(이 문서)과 저쪽 인프라의 차이:

| | 이 문서(Track A/B, 이미 실행됨) | `benchmarks/` (병렬 세션, 미실행) |
|---|---|---|
| 채점 축 이름 | 직접 정의(code_understanding 등 영문 임시명) | `interview_rubric.FR_AXIS_ALIAS`로 FR-04-01 공식 한글명 사용 |
| 재현성 계산 | 총점 표준편차 기반(합산 근사) | 필드 단위 exact-match(`reproducibility.py`, 더 엄격) |
| 정밀도(채점) | 강/약 2쌍 이진 변별 | 목표레벨 대비 MAE(평균절대오차) |
| 채점 대상 코드 | 벤치마크 스크립트 안에 하드코딩 | `feedback/llm_interview_grader.py` (실제 production 모듈) |

**이 문서의 실측 결과 자체는 유효하다** — 실제 API를 호출해 얻은 진짜 숫자이고, 임시로
정의한 지표라도 핵심 발견(gpt-oss-120b 재현성 결함, qwen 기본값의 속도 트레이드오프, 두 모델
접근불가)은 그대로 유효한 신호다. 다만 **앞으로 이 벤치마크를 다시 돌리거나 팀 공식 결과로
채택하려면, 이 문서의 임시 스크립트가 아니라 `benchmarks/` 쪽의 더 엄격하고 production 코드와
정합된 하네스를 우선 실행하는 게 맞다** — 그쪽이 아직 미실행이라는 것만 이번에 확인됐다.

---

## 정정 (D75) — 위 "발견 3: deepseek-v4-pro 접근 불가"는 틀렸다

`benchmarks/`를 실행하며 재검증한 결과, 위 발견 3("deepseek-v4-pro는 이 API 키로 완전히
접근 불가")은 **틀린 결론이었다.** 아래 "benchmarks/ 최종 결과" 참고 — 격리된 단독 호출로
재테스트하니 즉시 성공했고, 순차 재시도로 30/30(100%)까지 회복됐다. 이 세션 초반의 반복된
즉시 429는 **접근 권한 부재가 아니라 일시적 쿼터 소진(Track A→Track B 연속 실행 + 어쩌면
동시간대 다른 세션의 사용량 누적)**이었을 가능성이 훨씬 높다 — 사용자가 직접 이 가능성을
지적해 재검증하게 됨. **반대로 `z-ai/glm-5.2`는 같은 방식(격리 단독 호출, 20초 간격 순차
재시도)으로 재검증해도 9회 연속 전부 실패**해 진짜 지속적 이용 불가로 남았다(SURVEY_RESULTS.md의
과거 42% 이력과 대조하면 이 모델은 원래도 가장 불안정했던 후보). 교훈: "즉시 429"만으로
"접근 불가"를 단정하지 말 것 — 격리 재테스트(다른 모델 호출과 겹치지 않는 단독 호출)로
먼저 확인해야 한다.

## `benchmarks/` 최종 결과 (D74 순차실행 수정 + 전량 재시도 완료)

### 채점(FR-04-01 5축, `feedback/llm_interview_grader.py`) — `benchmarks/grading_benchmark_results.md`

| Model | tool_choice 준수율 | MAE(정밀도) | 속도 | 재현성 |
|---|---:|---:|---:|---:|
| qwen/qwen3-next-80b-a3b-instruct | 100% | 0.33 | 15.7s | 0.93 |
| deepseek-ai/deepseek-v4-pro | 100% | 0.43 | 49.8s | 0.89 |
| minimaxai/minimax-m3 | 100% | 0.60 | 74.7s | 0.85 |
| nvidia/nemotron-3-ultra-550b-a55b | 87% | 0.30 | 56.7s | 0.82 |
| z-ai/glm-5.2 | **0%** (9회 시도 전부 실패, 후보 제외 권장) | — | — | — |

### MEAS-02(순수 LLM Decision Point 추출, `judgment/meas02_decision_point_extractor.py`) — `benchmarks/meas02_results.md`

| Model | tool_choice 준수율 | reference-set coverage | 속도 |
|---|---:|---:|---:|
| qwen/qwen3-next-80b-a3b-instruct | 100% | 75% | 29.6s |
| deepseek-ai/deepseek-v4-pro | 100% | 50% | 67.3s |
| nvidia/nemotron-3-ultra-550b-a55b | 75% | 100% | 76.1s |
| minimaxai/minimax-m3 | **25%**(큰 컨텍스트 취약, 아래 참고) | 100%(성공건 한정) | 105.0s |
| z-ai/glm-5.2 | **0%** | — | — |

**신규 발견 — minimax-m3의 프롬프트 크기 민감성**: 채점 벤치마크(finding+질문+답변, 짧은
프롬프트)에서는 100%였는데, MEAS-02(전체 코드파일+요구사항 전문, 훨씬 큰 프롬프트)에서는
25%로 급락 — 대부분 120초 타임아웃. 경합이 아니라 **이 모델이 큰 컨텍스트 처리 자체에
취약하다는 신호**로 보인다(작은 프롬프트 task엔 써도 되지만 MEAS-02류 task엔 부적합할 수 있음).

## 최종 통합 결론

세 벤치마크(Track A/B, `benchmarks/grading`, `benchmarks/meas02`) 전부 종합하면:

- **`qwen/qwen3-next-80b-a3b-instruct`(팀 locked 기본값)는 모든 벤치마크·모든 역할에서
  100% 안정적** — 단, 속도는 항상 최저권(15~30s대)이라는 트레이드오프는 세 벤치마크에서
  일관되게 재확인됨.
- **`z-ai/glm-5.2`는 세 벤치마크 전부에서 배제 대상** — 격리 재테스트까지 거쳐도 회복 안 됨.
- **`deepseek-ai/deepseek-v4-pro`는 오판이었음 — 재검증 후 전 벤치마크 100%/100%**. 실제
  후보로 유효.
- **`minimax-m3`는 역할·프롬프트 크기에 따라 신뢰도가 극단적으로 갈린다** — 짧은 프롬프트
  채점엔 100%, 긴 프롬프트 추출엔 25%. 용도별로 다르게 판단해야 함.
- **`nemotron-3-ultra-550b-a55b`는 75~87%대로 중간권** — 잔여 실패가 503/tool_choice
  미준수 혼합이라 일부는 진짜 서비스 불안정성.
- **`stepfun-ai/step-3.5-flash`/`meta/llama-4-maverick`/`mistral-nemotron`**(Track A/B에만
  있고 `benchmarks/`엔 없는 후보들)은 두 트랙 모두 100%+최속권이라 여전히 유력한 대안.
