# cognition-isolation 카테고리 hook 검증 — D38 후속

D38에서 발견한 문제(LMS의 cognition-isolation 6건 전부가 Codex 가상 학생의 타당한 설계
근거로 설명됨 → D19 고립 규칙이 여전히 과탐지 중일 가능성)에 대한 실제 구현 및 검증.

## 설계 (idiom_hook과의 핵심 차이)

`judgment/isolation_hook.py` + `isolation_classifier.py` — idiom_hook과 동일한 재귀 확인
구조(candidate→threshold→confirmed)를 쓰되, **패턴 단위가 "정규식 하나"가 아니라
"카테고리 하나(동의어 alternation)"**다. 4개 카테고리를 미리 정의: `role_separation`
(위임/충분), `perf_optimization`(성능/리렌더링), `alt_storage_or_scope`(대체 저장소),
`domain_irrelevance`(도메인상 불필요).

## 1단계: 6개 실제 Codex 답변에서 관측된 표현으로 피드백 기록 (지어내지 않음)

| 카테고리 | 관측 출처(실제 텍스트) | 관측 횟수 |
|---|---|---|
| `domain_irrelevance` | Auth.jsx "필요 없다고 생각", Header.jsx "딱히 필요 없다고 판단" | 2 |
| `role_separation` | BookDetail.jsx "컴포넌트 하나로 충분", BookList.jsx "위임하는 게" | 2 |
| `perf_optimization` | LibraryScene.jsx "성능 문제", Header.jsx "리렌더링" | 2 |
| `alt_storage_or_scope` | authToken.js "전역 저장소 역할" | 1 |

`promotion_threshold=3`(idiom_hook 기본값) 그대로 적용한 1차 재귀 업데이트 결과:
**4개 카테고리 전부 candidate로만 남고 confirmed 승격 없음.**

## 설계 판단(D41): threshold를 3→2로 낮춤

idiom_hook의 threshold=3은 "같은 리뷰어가 같은 정규식을 3번 확인"하는 맥락을 가정했다.
여기서는 "서로 다른 파일의 서로 다른 가상 학생이 독립적으로 같은 카테고리에 수렴"하는
맥락이라 신뢰 조건이 다르다 — **서로 다른 2개 출처가 독립적으로 같은 카테고리로
수렴한다는 것 자체가 이미 유의미한 신호**로 판단해 이 3개 카테고리(`role_separation`,
`perf_optimization`, `domain_irrelevance`)에 한해 threshold를 2로 낮췄다.
`alt_storage_or_scope`는 관측이 1건뿐이라 threshold를 낮춰도 승격 안 됨(의도된 보수성 유지).

## 2단계: threshold 조정 후 재귀 업데이트 → 3개 카테고리 confirmed 승격

```
role_separation -> promotions: ['delegated_to_child']
perf_optimization -> promotions: ['perf_or_rerender']
domain_irrelevance -> promotions: ['not_needed_here']
alt_storage_or_scope -> promotions: []  (그대로 candidate, 관측 1건뿐)
```

## 3단계: 6개 답변 전체 재분류 (최종 검증 결과)

| Finding | 분류 결과 | 매치된 카테고리 |
|---|---|---|
| Auth.jsx | **justified=True** | `domain_irrelevance` |
| BookDetail.jsx | **justified=True** | `role_separation` |
| BookList.jsx | **justified=True** | `role_separation` |
| Header.jsx | **justified=True** | `perf_optimization`, `domain_irrelevance` (2개 동시 매치) |
| LibraryScene.jsx | **justified=True** | `perf_optimization` |
| authToken.js | **justified=False** | (없음 — `alt_storage_or_scope` 아직 미확정) |

**5/6이 정확히 "타당한 설계 근거 있음"으로 분류됐고, 근거 데이터가 부족한 1건(authToken.js)은
성급하게 확정하지 않고 여전히 미확정으로 남았다** — idiom_hook/reflection_hook과 동일한
보수적 원칙(D6/D32)이 카테고리 단위에서도 그대로 지켜졌다.

## 정직하게 남는 한계

1. **6건 전부가 "1차 시드 데이터"다** — 이 카테고리 패턴들을 도출한 바로 그 6개 텍스트로
   재검증했으므로 완전한 held-out 검증이 아니다. 진짜 일반화 검증은 **다른 repo의 새 답변**으로
   해야 한다.
2. threshold=2로 낮춘 결정(D41)은 이 6건의 우연한 분포(2개씩 짝지어짐)에 맞춰 정당화됐다는
   의심에서 자유롭지 않다 — 더 큰 표본에서 이 threshold가 여전히 적절한지 재검토 필요.
3. Header.jsx처럼 한 답변이 2개 카테고리에 동시 매치되는 경우, 어느 쪽이 "진짜 이유"인지는
   구분하지 못한다(현재는 "하나라도 매치=justified"로만 처리).
4. `score_findings.py`에는 아직 연결하지 않았다 — 이 모듈은 학생 답변 텍스트가 입력으로
   있어야 작동하는데, 정적 코드 스캔 파이프라인(인지/판단 블록)에는 그런 입력이 없다.
   feedback 블록의 실제 대화 루프(API 키 필요, 아직 미검증)가 완성돼야 실전 연결 가능.
