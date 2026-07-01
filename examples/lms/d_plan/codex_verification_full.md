# D안 전체 검증 — LMS 8 findings 중 Codex로 답변 생성 가능한 7건 전부

`architecture-diffusion:useBooksQueries.ts`는 idiom Rule이 이미 상→하로 종결해 인터뷰 대상이
아니다(D36). 나머지 7건 전부에 대해 evidence_bridge.py가 생성한 질문 + 실제 코드 컨텍스트만
Codex(`codex:codex-rescue`, 별도 모델)에 주고 학생 역할극 답변을 독립 생성시킨 뒤,
`feedback/reflection_signal.py`로 실제 판정했다. 7건 모두 병렬 실행, 전부 실제 코드 실행 결과.

## 결과 표

| Finding | Codex 답변 요약 | reflection_present | 실제 원인 분석 |
|---|---|---|---|
| `tier-b-risk:Bookshelf.jsx` | XSS 위험 인정, 원인(태그 이스케이프 문제) 설명, "안일하게 생각했다" 인정, DOMPurify 개선안 제시 | **False (0/4)** | 진짜 오류를 정확히 인정하고 개선안까지 낸 **양질의 reflection**인데 confirmed 패턴 문구와 안 맞아 놓침 — **재현율 문제(가짜 음성)** |
| `cognition-isolation:Auth.jsx` | 인증 페이지라 장르 데이터 불필요, "처음부터 명확히 판단했다기보다 자연스럽게 빠졌다" | False (0/4) | 원래 에러가 아니라 **타당한 설계 근거** — reflection 필요 없는 케이스, False가 오히려 맞는 판정 |
| `cognition-isolation:BookDetail.jsx` | GenreBadge로 이미 충분, "일관성 측면에서 더 고민했어야 하나 싶다" | False (0/4) | 타당한 근거 + 약한 자기성찰 힌트 있으나 "명백한 오류 인정"은 없음 — 경계 사례 |
| `cognition-isolation:BookList.jsx` | GenreSelect에 책임 위임, "확인이 더 필요할 것 같다" | False (0/4) | 타당한 설계 근거 — reflection 불필요 케이스 |
| `cognition-isolation:Header.jsx` | 불필요한 리렌더링 방지 의도, "의존성 관계를 문서화했으면 좋았을 것" | False (0/4) | 타당한 근거 + 경미한 개선 인식 — 경계 사례 |
| `cognition-isolation:LibraryScene.jsx` | 재마운트 성능 문제 회피 목적, "Context 흐름과 이원화된 느낌이라 더 고민 필요" | False (0/4) | 타당한 근거 + 아키텍처 정리 필요성 인식 — 경계 사례 |
| `cognition-isolation:authToken.js` | localStorage 자체가 전역 저장소 역할, "인증 상태 구독 화면이 생기면 대응 못 할 것 같아 더 고민했어야" | False (0/4) | 타당한 근거 + 미래 확장성 우려 인식 — 경계 사례 |

## 해석 — "전부 False"가 전부 같은 의미는 아니다

**1건(Bookshelf.jsx)은 진짜 재현율 실패다.** 명백한 실수를 인정하고 구체적 개선안까지
낸 고품질 답변인데 confirmed 패턴("너무 신뢰했", "그래서", "해야 합니다", "백엔드에서 제한")과
문구가 안 맞아서 통째로 놓쳤다. 이건 D34/D37에서 이미 확정한 한계의 재확인이다.

**나머지 6건은 애초에 "reflection이 필요한 상황"이 아니었을 가능성이 높다.** cognition-isolation
finding 자체가 D19에서 이미 지적한 "형제는 전부 허브를 써야 한다는 가정이 관심사가 여러 개인
코드베이스에서 부분적으로만 맞다"는 한계의 결과물이다 — 6명의 "가상 학생"이 전부 GenreContext를
안 쓴 나름의 타당한 이유(인증 페이지, 자식 위임, 성능 최적화, localStorage 대체 등)를 제시했고,
이건 애초에 "잘못을 수정하는" reflection이 아니라 "설계를 정당화하는" 답변이다. **이 6건에서
False가 나온 건 시스템이 잘못 작동해서가 아니라, 애초에 인지 블록의 isolation 판정 자체가
과탐지였을 가능성을 6번 연속으로 시사하는 것에 가깝다.**

**경계 사례 4건**(BookDetail/Header/LibraryScene/authToken)은 "~더 고민했어야 하나 싶다"류의
약한 자기성찰을 포함하지만, 명백한 "내가 틀렸다"는 인정이 없어 self_error_recognition이
안 걸렸다 — 이건 D34가 의도한 대로(약한 인정만으로는 통과 안 시킴) 작동한 것일 수도, 너무
엄격한 것일 수도 있다. 사람이 직접 봐야 할 지점이다.

## 결론

7건 중 **최소 1건은 확실한 재현율 실패**, 6건은 **애초에 finding 자체가 과탐지였을 가능성이
높음**을 시사한다. D안/E안을 더 개선하기 전에, C안의 `cognition-isolation` 규칙(D19)을
LMS 같은 다중 concern 코드베이스에서 재검토하는 게 우선순위가 더 높을 수 있다 — 이건
"Reflection 판정을 고치는 문제"가 아니라 "애초에 뭘 물어볼지 고르는 인지/판단 블록의
문제"라는 뜻이다.
