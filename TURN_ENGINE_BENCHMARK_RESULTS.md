# turn_engine.py 7모델 적응형 벤치마크 결과 (D89)

`feedback/turn_engine.py`(D87)가 구현한 스펙 04시트 턴 상태기계(①코드종속질문→②답변평가→
③표면/부분/방어 분류→④L2 트레이드오프 반례→⑤L3 극단시나리오→⑥reflection)를 실제 라이브
모델 호출로 4개 언어(Python/Java/JS/C++) × risk-type/cognition-isolation 두 판정 경로에 걸쳐
처음으로 실측했다. 이전의 모든 Track A/B 벤치마크(D58~D85)는 `generate_questions.py`의 단발성
후보뱅크 생성기를 테스트한 것이었다(D86이 발견) — 이번이 진짜 적응형 루프의 첫 라이브 벤치마크.

## 방법론

- **모델**: D77/D82에서 확정된 7개(qwen3-next-80b-a3b-instruct/step-3.5-flash/
  deepseek-v4-pro/llama-4-maverick/gpt-oss-120b/mistral-large-3/mistral-nemotron)
- **finding**: 8개 = risk-type 4언어(D85 `TRACK_B_PAIRS` 원문 재사용, 강한 답변만 트리거 문구
  1개 자연스럽게 보정) + cognition-isolation 4언어(신규 저작, 실제 클론 코드 확인 후 작성)
- **답변 스크립트**: 강한 답변(레벨 불문 고정 텍스트, 로컬에서 `evaluate_reflection()`/
  `classify_justification()` 직접 호출해 2개 이상 confirmed 서브신호 매치=defended 사전
  확정) / 약한 답변(D87 스모크테스트와 동일하게 "잘 모르겠습니다, 그냥 그렇게 했습니다"를
  매 레벨 반복) — **API 비용을 쓰기 전에 두 답변 모두 오프라인으로 검증 완료**
- **REPEATS=1** — 하니스 자체가 이번에 처음 실행되므로 1차 정찰. 재현성(반복 안정성)은 이번
  라운드에서 측정 대상이 아니다.
- **중요한 설계상 전제**: `classify_answer()`는 답변 텍스트에 대한 순수 정규식 판정이라 모델과
  무관하게 결정론적이다. 즉 이 벤치마크가 모델별로 실제로 갈라지는 축은 (a) 매 레벨
  `ask_question` 툴콜 스키마 준수(job 성공 여부), (b) 소요시간이다. **"판정 결과"는 모델
  비교 축이 아니라 "D88의 confirmed 패턴 콜드스타트 수정이 실제 라이브 환경에서도 작동하는가"를
  보는 회귀체크 축**이다.

## 결과

| Model | Job 성공률 | 판정 결과 일치율 | 평균 소요시간 | 평균 턴수 |
|---|---:|---:|---:|---:|
| `qwen/qwen3-next-80b-a3b-instruct` | 100% (16/16) | 100% | 55.1s | 2.5 |
| `stepfun-ai/step-3.5-flash` | 100% (16/16) | 100% | 9.3s | 2.5 |
| `deepseek-ai/deepseek-v4-pro` | 75% (12/16) | 100% | 57.7s | 2.0 |
| `meta/llama-4-maverick-17b-128e-instruct` | 75% (12/16) | 100% | 3.5s | 2.0 |
| `openai/gpt-oss-120b` | 38% (6/16) | 100% | 2.1s | 1.0 |
| `mistralai/mistral-large-3-675b-instruct-2512` | 19% (3/16) | 100% | 5.1s | 1.0 |
| `mistralai/mistral-nemotron` | 0% (0/16) | n/a | n/a | n/a |

**"판정 결과 일치율"은 job이 성공한 65건(112건 중) 전부에서 100%** — 강한 답변은 전부
`defended`, 약한 답변은 전부 `exhausted_at_cap`이 나왔다. 카테고리별(tier-b-risk 17/17,
architecture-diffusion 18/18, cognition-isolation 30/30)·언어별(4개 언어 전부 100%)로 쪼개도
불일치가 0건이다 — **D88이 채운 confirmed 패턴이 라이브 LLM이 생성한 질문에 대한 실제 학생
답변 시나리오에서도 표면/부분/방어를 정확히 가른다는 것을, 정규식 유닛테스트 수준이 아니라
전체 파이프라인(질문생성→분류→에스컬레이션)으로 처음 확인**했다.

## 실패 원인 분석 (전부 원인 규명 완료, 추측 아님)

- **`deepseek-v4-pro`/`mistral-large-3`(429 Too Many Requests)**: D77/D78/D83이 이미 문서화한
  "개인 키 1개로 flagship 모델을 버스트 호출하면 재시도가 같은 키로 돌아가 매번 즉시 같은
  429로 끝난다"는 알려진 한계가 그대로 재현됨. `mistral-large-3`는 raw 로그에서 여러 건이
  0.4~0.5초 만에 즉발 실패(키 풀 즉시 소진) — 모델 자체 결함이 아니라 순전히 단일 키 한도
  문제. 참고: `nvidia-keypool-guard.py` 훅이 이 상황을 사전 경고하도록 설계돼 있으나, 이번
  명령(`benchmark_turn_engine_multilang.py` 단일 파일 실행)에는 flagship 모델명이나
  `ThreadPoolExecutor`가 커맨드 텍스트 자체엔 없어(모듈 내부에 있을 뿐) 훅이 실제로 발동하지
  않았다 — 훅의 알려진 탐지 사각지대(D83이 "휴리스틱으로 충분"이라고 명시한 한계와 같은 종류).
- **`gpt-oss-120b`(38%, tool_choice 미준수)**: D66/D80이 이미 발견한 "tool_choice를 안 지키고
  자유서술로 응답" 결함이 이번엔 4개 언어 전부에서 산발적으로 재현됨(raw 로그에서 실제로
  `content`에 질문처럼 보이는 자유 텍스트가 옴 — 모델이 이해를 못한 게 아니라 스키마 강제를
  안 지킨 것). 새로운 발견이 아니라 기존 결함의 재확인.
- **`mistral-nemotron`(0%, HTTP 400)**: 원인을 진단 호출로 직접 확인 — 응답 본문이
  `{"status":400,"detail":"Function id '...': DEGRADED function cannot be invoked"}`.
  **NVIDIA Build 플랫폼이 이 모델의 서빙 함수를 벤치마크 시점에 DEGRADED 상태로 내려둔 것**이지,
  코드/답변/스키마 문제가 아니다. D82에서 이 모델이 100% 성공했던 것과 모순되지 않음(그때는
  정상 서빙 중이었을 뿐). 재검증하려면 나중에 다시 호출해볼 것.

## 알려진 한계

- REPEATS=1이라 반복 안정성(재현성)은 이번 라운드에서 측정하지 않았다. `job_success_rate`가
  낮은 모델(특히 429 계열)은 시점에 따라 결과가 달라질 수 있다 — 여러 키로 재검증 전까지
  순위로 인용 금지(D69/D77이 이미 확립한 원칙과 동일).
- `repeated-pattern` 카테고리는 이번에도 스코프 밖이다 — 4개 언어 전부 finding 0건
  (`judgment/score_findings.py`의 `find_repeated_pattern_files()`가 Firebase 전용
  `"onSnapshot"` 패턴만 하드코딩돼 있어 원천적으로 없음, 공유 판단 블록을 건드리는 별개 범위
  큰 작업이라 이번엔 손대지 않음).
- 레벨별(L1/L2/L3/reflection) 정밀 스키마 준수율은 못 낸다 — `run_decision_point()`가 중간
  레벨에서 실패 시 그 지점까지의 transcript를 버리고 예외를 던지므로(핵심 오케스트레이션
  무수정 원칙), job(finding×variant) 단위 성공/실패로만 집계했다. 약한 답변은 4레벨 전부
  통과해야 성공이므로 오히려 다회 연속 준수를 요구하는 더 엄격한 지표가 된다.
- 강한 답변 8건 모두 이번 세션에서 직접 작성(risk-type 4건은 D85 원문 보정, cognition-isolation
  4건은 신규)한 것이라 표본이 작다(finding당 1건) — D64/D74/D84가 이미 반복 지적한 "실제 학생
  답변 다양성 부족" 한계와 동일 계보.

## 원본 데이터

- `turn_engine_multilang_results.json` — 112건(8 findings × 7 models × 2 variants) 전체 raw
- `turn_engine_multilang_summary.json` — 모델별 집계
- `benchmark_turn_engine_multilang.py` — 실행 스크립트(재실행 가능, `NVIDIA_API_KEY_1` 필요)
