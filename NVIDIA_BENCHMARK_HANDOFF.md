# NVIDIA 모델 벤치마크 핸드오프 — Track A/B + benchmarks/ 통합 최종 결과

D85. 이 문서는 "질문생성용·채점용 벤치마크를 나눠야 하나 단일로 가나"라는 질문에서 시작해,
독립적으로 진행된 두 벤치마크 인프라(이 세션의 Track A/B, 병렬 세션의 `benchmarks/`)를
서로 재검증·보완하고 하나의 결론으로 합친 전체 과정의 인덱스다. 상세 원본은 각 문서를
참고하고, 여기서는 **최종적으로 무엇을 믿어야 하는가**만 명확히 정리한다.

## 한눈에 보는 결론

| 모델 | 질문생성 | 채점 | 종합 판정 |
|---|---|---|---|
| **qwen/qwen3-next-80b-a3b-instruct**(기본값) | 정밀도·재현성 만점 | 정밀도·재현성 만점 | ✅ 팀 결정 지지됨. 단, **두 역할 모두 최저속**(24~35s) — 실시간 세션 지연 리스크 |
| **deepseek-ai/deepseek-v4-pro** | 정밀도·재현성 만점 | 정밀도 만점, 재현성 0.63~0.89(측정마다 편차) | ✅ 유효한 대안. 속도는 qwen과 비슷하게 느림(28~50s) |
| **mistralai/mistral-nemotron** | 정밀도·재현성 만점 | 정밀도·재현성 만점 | ✅ 가장 무난한 대안 — 빠르고(5~7s) 전부 만점 |
| **meta/llama-4-maverick-17b-128e-instruct** | 정밀도·재현성 만점 | 정밀도·재현성 만점 | ✅ 무난한 대안, 최속권(4~6s) |
| **stepfun-ai/step-3.5-flash** | 정밀도·재현성 만점 | 정밀도·재현성 만점 | ✅ 최속 후보(2.6~6.1s) |
| **openai/gpt-oss-120b** | 정밀도·재현성 만점 | 정밀도는 만점인데 **재현성 결함**(같은 답변 재채점 시 25점 만점 기준 σ 1.7) | ⚠️ 질문생성엔 써도 되지만 **채점 역할엔 부적합** |
| **mistralai/mistral-large-3** | 정밀도 75%(finding 1건 반복 실패) | 정밀도·재현성 양호(1.0/0.81~0.85) | ⚠️ 짧은 프롬프트(채점)엔 강함, 정적 finding 처리엔 약간 불안정 |
| **minimaxai/minimax-m3**(benchmarks/만 테스트) | — | 짧은 프롬프트 100%, **긴 프롬프트(전체 코드파일) 25%** | ⚠️ **프롬프트 크기에 극단적으로 민감** — 용도별 분리 판단 필요 |
| **nvidia/nemotron-3-ultra-550b-a55b**(benchmarks/만 테스트) | — | 75~87%, 잔여 실패는 503/timeout 혼재 | ⚠️ 중간권, 서비스 불안정성 일부 실재 |
| **z-ai/glm-5.2**(benchmarks/만 테스트) | — | **0%** — 격리 단독 호출 3회, 경합 제거 순차실행, 20초 간격 재시도 7연속까지 총 9회 시도 전부 실패 | ❌ **후보에서 제외 권장(단, 아래 "미해결 의문" 참고 — 확정은 아님)**. SURVEY_RESULTS.md 이전 조사(5/12)에서도 최하위였음 — 일관된 이력 |

> 이 표는 **JS/TS(Study-Match-/LMS) 코드 기준**이다. 병렬 세션이 이후 4개 언어(Python/Java/JS/C·C++)로 확장한 결과(D80~D84, 아래 "관련 진행중 작업")는 아직 이 표에 반영되지 않았다 — 다국어 결과가 다를 수 있는 모델(특히 gpt-oss-120b)은 그쪽 문서를 같이 볼 것.

## 진행 과정 (짧은 타임라인)

1. **Track A/B 설계+실행** — "질문생성 vs 채점, 벤치마크를 나눠야 하나" 질문에 대한 답으로 6개 모델 숏리스트 자체 벤치마크 실행 → [`TRACK_AB_BENCHMARK_RESULTS.md`](./TRACK_AB_BENCHMARK_RESULTS.md), Artifact(아래).
2. **병렬 세션의 `benchmarks/` 발견** — 같은 목적(채점+MEAS-02)의 더 엄격한(FR-04-01 공식 축 이름, 필드단위 exact-match 재현성) 인프라가 이미 존재했으나 미실행 상태로 발견됨.
3. **`benchmarks/` 실행 + D77 동시성 버그 수정** — 최초 실행은 5모델 동시 제출로 경합 발생, 모델별 순차 실행으로 재검증 → [`benchmarks/grading_benchmark_results.md`](./benchmarks/grading_benchmark_results.md), [`benchmarks/meas02_results.md`](./benchmarks/meas02_results.md).
4. **"즉시 429=접근불가" 오판 정정** — 사용자가 "다른 세션도 같은 키를 쓰고 있어서 막힌 거 아니냐"고 반증 가설 제기 → 격리 재테스트로 deepseek-v4-pro는 정상 작동 확인, glm-5.2만 진짜 지속 불가로 확정.
5. **Artifact 최종 완성** — deepseek-v4-pro를 Track A/B 방법론으로 직접 재호출, mistral-large-3의 Track B 빈 데이터 채움 → 6모델→7모델로 확장, 재배포.

## 방법론적 교훈 (다음에 벤치마크할 때 반드시 참고)

1. **"즉시 429"만으로 "접근 불가"를 단정하지 말 것 — 근본 원인이 코드에서 확정됨(D80).** `feedback/nvidia_client.py`의 `chat()`은 429를 받으면 "풀의 다음 키로 재시도"(`max_retries=3`)하도록 설계돼 있는데, 이건 팀 전체 키 풀(`.env.example`이 `NVIDIA_API_KEY_1~7`, 7명분 가정)을 전제로 한다. **개인 키 1개만 등록하면 "다음 키"가 사실상 같은 키라, 재시도 3번이 전부 즉시 같은 429로 끝난다**(실패 응답이 매번 0.3~0.7초로 즉발이었던 이유). deepseek-v4-pro/mistral-large-3는 이 패턴으로 "접근불가"처럼 보였다가 **수십 분 뒤 같은 키로 재시도하니 100% 성공**했다 — 진짜 원인은 무료 티어의 짧은 시간창 한도이지 접근 권한 문제가 아니었다. **격리된 단독 호출 + 충분한 시간 간격으로 재확인**하는 게 핵심.
2. **5모델을 하나의 스레드풀에 동시 제출하면 순서상 먼저 스케줄된 모델만 신뢰할 수 있다.** 모델별로 순차 실행(모델 내부는 동시성 유지)해야 공정한 비교가 된다(D77).
3. **정밀도와 재현성은 별개 축이다.** gpt-oss-120b는 정밀도(강/약 구분)는 만점이지만 재현성(같은 입력 재실행 시 일관성)은 최악이었다 — 하나만 재고 "이 모델 괜찮다"고 판단하면 위험하다.
4. **프롬프트 크기는 숨은 변수다.** minimax-m3는 채점(짧은 프롬프트)과 MEAS-02(전체 코드파일+요구사항, 긴 프롬프트)에서 100%→25%로 극단적으로 갈렸다 — "이 모델 쓸만하다"는 결론이 프롬프트 크기에 따라 뒤집힐 수 있음을 항상 의심할 것.
5. **불안정한 모델의 이력은 누적해서 봐야 한다.** glm-5.2는 SURVEY_RESULTS.md(87모델 서베이, 5/12)부터 이번 채점·MEAS-02 벤치마크(0/9)까지 일관되게 최하위였다 — 한 번의 측정이 아니라 여러 차례 걸친 이력이 신뢰도를 높인다.
6. **"데이터 없음"과 "재시도해도 실패"를 화면에서 구분하지 않으면 오탐성 알림이 생긴다(D82).** 아티팩트 렌더 코드가 "이 모델은 애초에 테스트를 안 했음"과 "테스트했는데 안 됐음"을 똑같이 표시해, 실제로는 단순 누락이었던 mistral-nemotron이 마치 지속적 429처럼 보인 적이 있었다. 새 모델/축을 차트에 추가할 때는 데이터 소스(여기서는 `langBench`, `trackA`, `trackB` 등 여러 객체)에 전부 빠짐없이 추가했는지 항상 재확인할 것.

## 미해결 의문 — glm-5.2는 정말 배제해야 하나

교훈 1(단일 키 재시도 설계 결함)이 deepseek-v4-pro/mistral-large-3의 "접근불가"를 완전히
설명한다면, **glm-5.2도 같은 메커니즘이고 그저 내가 기다린 시간(최대 20분 안팎)이 회복에
필요한 시간창보다 짧았을 가능성**을 배제할 수 없다. 다만 SURVEY_RESULTS.md(다른 시점, 다른
세션)에서도 유독 이 모델만 5/12로 최하위였다는 독립 증거가 있어 "이 모델 자체가 다른
모델보다 근본적으로 느리거나 불안정하다"는 가설도 여전히 유효하다 — **둘 다 부분적으로
맞을 수 있다(원래도 느린 모델 + 재시도 설계 결함이 겹쳐 유독 심하게 나타남)**. 다음에
이 모델을 다시 판단하려면 **1시간 이상 텀을 두고** 격리 단독 호출로 한 번 더 확인해볼 것.

## 팀이 결정해야 할 것

1. **`z-ai/glm-5.2`를 전체 후보군에서 제외할지 공식 확정.** 세 번의 독립 조사(SURVEY_RESULTS.md, grading, MEAS-02)가 일관되게 이 모델을 최하위로 지목했다.
2. **`minimax-m3`를 용도별로 분리해서 쓸지 여부.** 짧은 프롬프트 task엔 쓰고 긴 컨텍스트 task(MEAS-02류)엔 배제하는 정책이 필요해 보인다.
3. **Track A/B와 `benchmarks/` 중 어느 쪽을 팀 공식 벤치마크 인프라로 채택할지.** `benchmarks/`가 더 엄격하고 production 코드(`feedback/llm_interview_grader.py`, `judgment/meas02_decision_point_extractor.py`)와 정합되지만, Track A/B가 실제로는 7모델까지 채워져 있어 커버리지가 더 넓다. 하나로 통일하거나 역할을 나눠 유지할지 결정 필요.
4. **API 키 운영 정책.** 여러 세션·벤치마크가 같은 키를 동시에 쓰면 이번처럼 오판(접근불가 vs 일시적 경합)이 반복될 수 있다 — 팀 키 풀을 늘리거나(nvidia-build의 다중 키 풀링 재사용), 벤치마크 실행 시간대를 조율하는 정책이 필요하다.

## 파일 지도

| 파일 | 내용 |
|---|---|
| [`TRACK_AB_BENCHMARK_RESULTS.md`](./TRACK_AB_BENCHMARK_RESULTS.md) | Track A/B(자체 벤치마크) 상세 결과, 정정 이력(D75) |
| [`benchmarks/grading_benchmark_results.md`](./benchmarks/grading_benchmark_results.md) | 채점(FR-04-01 5축) 벤치마크, production 모듈(`feedback/llm_interview_grader.py`) 기반 |
| [`benchmarks/meas02_results.md`](./benchmarks/meas02_results.md) | MEAS-02(순수 LLM Decision Point 추출) 벤치마크 |
| [`benchmark_track_a.py`](./benchmark_track_a.py) / [`benchmark_track_b.py`](./benchmark_track_b.py) | Track A/B 실행 스크립트(재실행 가능, JS/TS 전용) |
| [`benchmarks/grading_run_benchmark.py`](./benchmarks/grading_run_benchmark.py) / [`benchmarks/meas02_run_benchmark.py`](./benchmarks/meas02_run_benchmark.py) | D77 순차실행 수정 반영된 production 벤치마크 스크립트 |
| [`benchmark_track_ab_multilang.py`](./benchmark_track_ab_multilang.py) | **관련 진행중 작업(D80~D84)** — 4개 언어(Python/Java/JS/C·C++)로 확장한 Track A/B, 이 핸드오프 작성 시점 기준 아직 README에만 정리되고 이 문서엔 통합 안 됨 |
| Artifact | https://claude.ai/code/artifact/46e8d412-a460-4d01-bdfc-3c927ee4af8e — 원래 7모델×3축×2트랙 6패널(이 핸드오프 대상) + 병렬 세션이 추가한 다국어 히트맵(D80~D82, 이 핸드오프 범위 밖) |
| README.md 결정 로그 | D61~D69(`benchmarks/` 원본), D70~D73(Track A/B 최초), D74/D77(순차실행 수정), D75/D78(정정), D79(Artifact 7모델 완성), **D80~D84(다국어 확장, 별도 진행중)**, D85(이 문서) |

## 재현 방법

```bash
export NVIDIA_API_KEY_1=<키>
# Track A/B (자체 벤치마크, 7모델)
python3 benchmark_track_a.py && python3 benchmark_track_b.py
# benchmarks/ (production 정합 벤치마크, D77 순차실행 버전)
python3 benchmarks/grading_run_benchmark.py
python3 benchmarks/meas02_run_benchmark.py
```

원시 호출 로그(`*_results.json`, `*.log`류)는 재현 가능하므로 git에는 커밋하지 않는다(`.gitignore` 참고) — 위 명령으로 언제든 다시 만들 수 있다.

<!-- D85: 이 핸드오프 문서를 신설해 Track A/B + benchmarks/ 두 벤치마크 인프라의 전체 진행사 요약
  WHY: 벤치마크 결과가 3개 문서(TRACK_AB_BENCHMARK_RESULTS.md, grading_benchmark_results.md,
       meas02_results.md)+README D70~D79에 흩어져 있어 "최종적으로 뭘 믿어야 하나"를 한 번에
       파악하기 어려웠다. 특히 진행 중 정정(deepseek-v4-pro)이 있었던 지점은 여러 문서를
       순서대로 읽지 않으면 오래된 결론을 최종으로 오인할 위험이 있었다.
  COST: 상세 근거는 여전히 각 개별 문서에 있어 이 문서만 읽으면 "왜 그런 결론인지"까지는
       알 수 없음 — 의도적으로 인덱스 역할만 하도록 설계(개별 문서 링크로 위임).
  EXIT: 벤치마크가 더 늘어나 이 인덱스도 낡으면, 표 형식은 유지하되 "최종 결론" 표만 최신화하고
       "진행 과정" 절은 압축하거나 별도 히스토리 파일로 분리.
-->
