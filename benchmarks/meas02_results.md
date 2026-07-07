# MEAS-02 순수 LLM Decision Point 추출기 벤치마크 결과

기획명세서_AI기반_프로젝트교육품질관리플랫폼.xlsx(00시트, "확정 설계 결정") 그대로 정적분석 미사용, 코드조각+요구사항→LLM. 정밀도는 reference-set coverage(D66) — 기존 정적분석 4개 finding과 겹치는지 확인하는 것이지 gold standard 대비 recall이 아님. 이 실행 자체가 Qwen 컨텍스트/속도 실측(D69, 00시트 "락 전 실측 필요")도 겸함.

| Model | tool_choice 준수율 | reference-set coverage | 평균 DP 개수 | 평균 속도 | 개수-안정성(재현성 근사) |
|---|---:|---:|---:|---:|---:|
| `qwen/qwen3-next-80b-a3b-instruct` | 100% | 75% | 6.2 | 29.6s | 0.50 |
| `deepseek-ai/deepseek-v4-pro` | 100% | 50% | 10.5 | 67.3s | 0.50 |
| `z-ai/glm-5.2` | 0% | n/a | n/a | n/a | n/a |
| `minimaxai/minimax-m3` | 25% | 100% | 5.0 | 105.0s | 0.00 |
| `nvidia/nemotron-3-ultra-550b-a55b` | 75% | 100% | 7.2 | 76.1s | 0.50 |

## 케이스별 coverage 상세 (한계 포함)

**study_match:firebase.ts** — tier-b-risk:firebase.ts (인증정보 JSON.stringify 유출) — 단일 파일 내 신호, 커버 가능해야 함
- `qwen/qwen3-next-80b-a3b-instruct`: covered
- `deepseek-ai/deepseek-v4-pro`: covered
- `z-ai/glm-5.2`: n/a(실패)
- `minimaxai/minimax-m3`: n/a(실패)
- `nvidia/nemotron-3-ultra-550b-a55b`: covered

**study_match:Competitions.tsx** — cognition-isolation:Competitions.tsx (허브 미연결) — cross-file fan-in 신호라 단일 파일 조각만 보는 이 추출기는 원천적으로 못 잡을 가능성이 높음(한계 실측용)
- `qwen/qwen3-next-80b-a3b-instruct`: NOT covered
- `deepseek-ai/deepseek-v4-pro`: NOT covered
- `z-ai/glm-5.2`: n/a(실패)
- `minimaxai/minimax-m3`: n/a(실패)
- `nvidia/nemotron-3-ultra-550b-a55b`: covered

**lms:Bookshelf.jsx** — tier-b-risk:Bookshelf.jsx:dangerous-html — 단일 파일 내 신호, 커버 가능해야 함
- `qwen/qwen3-next-80b-a3b-instruct`: covered
- `deepseek-ai/deepseek-v4-pro`: covered
- `z-ai/glm-5.2`: n/a(실패)
- `minimaxai/minimax-m3`: n/a(실패)
- `nvidia/nemotron-3-ultra-550b-a55b`: covered

**lms:useBooksQueries.ts** — architecture-diffusion:useBooksQueries.ts (여러 컴포넌트 공유) — 부분적으로 단일 파일에서도 추론 가능(공유 목적의 훅이라는 건 파일 자체에서 보임)
- `qwen/qwen3-next-80b-a3b-instruct`: covered
- `deepseek-ai/deepseek-v4-pro`: NOT covered
- `z-ai/glm-5.2`: n/a(실패)
- `minimaxai/minimax-m3`: covered
- `nvidia/nemotron-3-ultra-550b-a55b`: covered

## 중요한 방법론적 한계 (D77로 재검증 완료, 정직하게 명시)
최초 실행(5모델 동시 제출)의 경합 문제를 D77(모델별 순차 실행)로 고치고 실패 건을 5초 간격으로 순차 재시도한 결과: `qwen3-next-80b`/`deepseek-v4-pro`는 100% 도달. `nvidia/nemotron-3-ultra-550b-a55b`는 75%(잔여 실패는 503/tool_choice 미준수 — 진짜 서비스 이슈로 보임). **`minimaxai/minimax-m3`는 grading 벤치마크(짧은 프롬프트)에서는 100%였는데 이 벤치마크(전체 코드파일+요구사항 전문을 프롬프트에 넣는 훨씬 큰 컨텍스트)에서는 25%에 그쳤다** — 실패 대부분이 120초 타임아웃으로, 경합이 아니라 **이 모델이 큰 컨텍스트 처리에 특히 취약하다는 신호**로 해석하는 게 더 타당하다(작은 프롬프트 task에서는 이 모델을 써도 되지만, MEAS-02처럼 전체 파일을 통째로 넣는 task에는 부적합할 수 있음). `z-ai/glm-5.2`는 이 벤치마크에서도 0% — grading 벤치마크에서 이미 확인한 대로(SURVEY_RESULTS.md의 과거 42% 이력과 달리 이번엔 순차 실행+격리 단독 호출+20초 간격 재시도 전부에서 0/9) 경합이 아니라 모델 자체의 지속적 이용 불가로 판단, 후보에서 제외 권장.

## 알려진 한계
- 이 추출기는 단일 파일 조각만 보므로(스펙의 "DP 단위 처리로 컨텍스트 의존 최소화" 설계), cross-file 구조 신호(예: Competitions.tsx의 허브 미연결 — fan-in 기반)는 원천적으로 탐지 대상이 아니다. 이건 버그가 아니라 스펙이 선택한 아키텍처의 알려진 트레이드오프다.
- reference-set coverage는 키워드 매칭 기반 근사(nvidia-build METHODOLOGY.md의 heuristic screening과 동일한 성격, 정밀 검증 아님).
- 재현성은 decision_points 배열이 자유 텍스트를 포함해 구조화 필드 exact-match(D61 모듈)를 그대로 못 쓰고, 개수 안정성으로 근사했다 — 채점 벤치마크(D63)보다 느슨한 지표.