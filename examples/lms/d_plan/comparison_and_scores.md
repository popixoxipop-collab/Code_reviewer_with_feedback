# jxxnixx/LMS 전용 — A~E안 비교 및 6-루브릭 채점

## 1. 안건별 실행 결과 요약 (LMS만)

| 안 | 실행 여부 | LMS 실행 결과 |
|---|---|---|
| A안 (Viva 100점) | ✅ | 78/100, 중상, 3문항+follow-up 실시간 대화 |
| B안 (ROAF-B) | ✅ | 등급 중상, Downgrade Log 3건, **자체 발견: Signals After Filter 불일치** |
| 김만서님 방향 | (비전) | A/B/C/D/E 전부 이 방향의 서로 다른 구현 시도 — 단독 실행 결과 없음 |
| C안 (이 저장소) | ✅ | 8 findings, 버그 3개 발견·수정(D18~D20), idiom 1건 확정 |
| **D안 (B안+C안, 이번에 구현)** | ✅ | evidence_bridge.py로 8 findings→Evidence 자동변환, **8건 중 1건 인터뷰 생략**, 인터뷰 1건(dangerous-html) 진행 |
| E안 (Reflection Hook) | ✅(D안 안에서 Codex 독립 생성 답변으로 검증, D37) | **정성적으로 우수한 진짜 reflection조차 0/4로 완전히 놓침** — 직접 쓴 답변이 아니라 별도 모델(Codex) 생성 답변이라 재현율 문제가 진짜임이 확정됨. 새 후보 패턴 3개는 1/3만 기록, 성급히 승격 안 함 |

D안 실행 상세: [`d_plan/simulation.md`](./d_plan/simulation.md), [`d_plan/evidence_packets.json`](./d_plan/evidence_packets.json)

## 2. 토큰 경제성 6-기준 채점 (LMS 기준, 0~10, 높을수록 경제적)

| 기준 | A안 | B안 | C안 | D안 | E안 |
|---|---|---|---|---|---|
| 인지 단계 비용(repo 분석) | 2 | 2 | 10 | 10 | 10 |
| 판단 단계 비용 | 2 | 3 | 10 | 8 | 9 |
| 질문 생성 비용 | 3 | 4 | 10(해당없음) | 7 | 10(해당없음) |
| 반복 실행 비용 | 1 | 1 | 10 | 6 | 9 |
| 사람 개입 비용 | 3 | 3 | 6 | 5 | 5 |
| 확장성(다른 repo) | 2 | 2 | 9 | 6 | 8 |
| **평균** | **2.17** | **2.50** | **9.17** | **7.00** | **8.50** |

**근거 요약**: A/B안은 매 대화가 Repository 전체를 컨텍스트에 새로 태워야 해서(ROAF 프롬프트 Step1) 어느 축에서도 경제적이지 않다. C안은 LLM 호출이 아예 없어(cost_saved_ratio 0.9+, 실측) 압도적으로 economical. D안은 C안의 저비용 인지/판단에 편승하되 인터뷰가 필요한 잔여 finding(7/8)에는 여전히 대화 비용이 남아 중간. E안은 순수 정규식이라 저렴하지만 사람이 패턴을 계속 확인해줘야 하는 비용이 있다.

## 3. 답안 품질 6-axis 채점 (PaperOrchestra 루브릭 재사용: scientific_depth×0.20 + technical_execution×0.20 + logical_flow×0.15 + writing_clarity×0.15 + evidence_presentation×0.20 + academic_style×0.10)

| Axis | A안 | B안 | C안 | D안 | E안 |
|---|---|---|---|---|---|
| scientific_depth | 60 | 75 | 55 | 65 | 50 |
| technical_execution | 70 | 75 | 90 | 70 | 45 |
| logical_flow | 55 | 65 | 80 | 70 | 75 |
| writing_clarity | 80 | 65 | 60 | 65 | 55 |
| evidence_presentation | 50 | 80 | 85 | 85 | 70 |
| academic_style | 40 | 70 | 90 | 80 | 85 |
| **가중 평균** | **60.25** | **72.50** | **76.00** | **72.25** | **61.00** |

**근거 요약**:
- **A안**이 가장 낮은 이유: 점수 근거가 스스로 "왜 17점인지 모른다"고 인정할 만큼 약하고(logical_flow, evidence_presentation 낮음), 재현성이 없음(academic_style 최저). 대신 사람이 읽기엔 가장 편함(writing_clarity 최고).
- **C안**이 가장 높은 이유: 실제 코드 실행·버그 수정·4 repo 재현으로 technical_execution·academic_style이 가장 강함. 다만 LLM 논증 없이 규칙만 쓰므로 scientific_depth는 중간.
- **D안**은 C안의 근거 강점을 계승하면서 실제 인터뷰까지 진행했지만, follow-up 자동생성과 답변평가(E안)가 아직 완성 전이라 C안보다는 낮음.
- **B안**은 Rule 기반 설계 의도는 좋으나(logical_flow, evidence_presentation 상위권) 자체 실행에서 Signal↔Final 불일치를 스스로 드러내 감점.
- **E안**의 technical_execution을 60→45로 재하향: 직접 쓴 시뮬레이션이 아니라 **Codex가 독립 생성한, 정성적으로 우수한 진짜 reflection조차 0/4로 놓쳤다**(D37) — 개념(logical_flow, academic_style)은 탄탄하지만 실행 재현율이 실측으로 더 나쁘게 확정됨.

## 4. 종합 포지셔닝

```
                답안 품질 →
        낮음                          높음
비용 ↑  A안(60.25, 2.17)
높음
        B안(72.50, 2.50)
비용 ↓                    E안(61.00, 8.50)   D안(72.25, 7.00)   C안(76.00, 9.17)
낮음
```
C안이 유일하게 "저비용·고품질" 사분면에 있다 — 단, C안은 애초에 대화(Ownership 검증)를
하지 않는다는 근본적 범위 제한이 있다(POC_TEST.md 문제6). D안은 그 제한을 풀려는
시도로서 비용을 조금 더 쓰고 A/B안보다 훨씬 싸게 비슷하거나 더 나은 품질을 냈다 —
**다음 우선순위는 D안의 follow-up 자동생성과 E안의 패턴 재현율을 올리는 것.**
