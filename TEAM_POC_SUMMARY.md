# 노경천 — Code Ownership 검증 파이프라인 (GitHub: Code_reviewer_with_feedback)

> 팀원별 POC 테스트 요약(김만서/박진용/손진원/박종호)과 같은 형식. 다른 3명이 "대화형
> LLM 인터뷰 프롬프트"를 비교했다면, 이쪽은 **"대화 없이 코드만으로 얼마나 갈 수 있고,
> 어디서부터 대화가 반드시 필요한가"**를 실제 5개 방법론(A~E안)으로 검증했다.

## 입력 레포 및 검증 대상 결정 포인트 (실제 스캔 결과, jxxnixx/LMS)

> **입력 레포:** `https://github.com/jxxnixx/LMS` (회귀 검증용 3개 추가: Study-Match-,
> RunPod_Deploy_Agent, Shadowbroker)
>
> **검증 대상 결정 포인트 (Tier A/B 구조+위험 스캔, 총 8건):**
> - `cognition-isolation` × 6 — Auth.jsx / BookDetail.jsx / BookList.jsx / Header.jsx / LibraryScene.jsx / authToken.js (허브 모듈 GenreContext.jsx 미사용)
> - `architecture-diffusion` × 1 — useBooksQueries.ts (여러 컴포넌트가 공유하는 react-query 커스텀 훅)
> - `tier-b-risk` × 1 — Bookshelf.jsx `dangerouslySetInnerHTML` (네이버 도서 API 응답을 그대로 렌더링)

---

## 5개 안 실행 결과 (전부 실제 실행, 사람이 지어낸 답 없음)

| 안 | 방법론 | LMS 실행 결과 |
| --- | --- | --- |
| A안 | Viva 100점 (사람이 직접 대화) | 78/100, 중상. **가장 치명적 지적: "Repository Knowledge(사실 파악)는 측정하지만 Ownership(재설계 시 뭘 바꿀지)은 측정 못함"** |
| B안 | ROAF-B Signal→Rule→Evidence Trace (사람이 직접 대화) | 등급 중상, Downgrade Log 3건. Evidence→Rule 체인으로 "왜 이 등급인가"는 설명 가능하나 Signal Aggregation·Evidence Confidence 약함 |
| C안 | 이 GitHub repo — 코드만으로 구조+위험 스캔, LLM 대화 없음 | 8 findings 100% 코드 실행, 버그 3개 실측·수정(fan-in 이중계산/eval() 오탐/Vite alias 누락), idiom 1건 확정. **API 비용 0, 대화 자체가 없어 Ownership 축은 원천적으로 측정 불가** |
| D안 | C안 finding → B안 Evidence 형식 자동변환(`evidence_bridge.py`) | 8건 중 1건(diffusion)은 코드 Rule만으로 인터뷰 없이 종결 — 사람/LLM 대화가 필요한 나머지 7건에 자동 생성 질문+Evidence 제공 |
| E안 | Reflection Hook Guard — 답변의 자기오류인식 재귀 판정 | Codex(별도 모델) 독립 생성 답변 7건 검증, **0/7 통과**. 단 원인이 갈림(아래 참조) |

## 안별 장단점 (박진용 문서 형식)

| A안 (Viva 100점) | 내용 |
| --- | --- |
| ✅ 장점 | 사람이 직접 대화해 뉘앙스·애매한 답변 포착 우수, follow-up이 자연스러움 |
| ❌ 단점 | 재현 불가(사람마다 채점 편차), **자체적으로 "Ownership은 못 본다"고 인정**, 사람 시간 비용 최고 |

| B안 (ROAF-B Signal Engine) | 내용 |
| --- | --- |
| ✅ 장점 | Evidence→Rule 체인으로 "왜 이 등급인가"를 감사 가능하게 설명, Downgrade Log가 근거로 남음 |
| ❌ 단점 | Signal Aggregation·Evidence Confidence 정량화가 약함(B안 자체 비평에서 인정), 역시 사람이 직접 대화해야 해서 비용 높음 |

| C안 (이 GitHub repo) | 내용 |
| --- | --- |
| ✅ 장점 | API 비용 0, 100% 재현 가능(같은 코드 재실행 시 동일 결과), 발견한 버그를 코드 레벨에서 즉시 수정 가능 |
| ❌ 단점 | 대화 자체가 없어 Ownership 측정이 원천적으로 불가능, 구조 신호(`cognition-isolation`)가 다중 concern 코드베이스에서 과탐지(D19/D38) |

| D안 (evidence_bridge) | 내용 |
| --- | --- |
| ✅ 장점 | 8건 중 1건은 인터뷰 없이 자동 종결(토큰 절약 실증), Evidence를 사람이 매번 재분석할 필요 없이 자동 생성 |
| ❌ 단점 | 자동 생성 질문이 finding 단위로 끊겨 있어 여러 파일을 엮은 서사형 질문보다 부자연스러움(6개 cognition-isolation finding이 전부 같은 템플릿 질문), follow-up 자동생성 로직 아직 없음 |

| E안 (Reflection Hook Guard) | 내용 |
| --- | --- |
| ✅ 장점 | 재귀 확인(threshold) 구조라 1회성 판정이 아니라 반복 확인 전엔 신뢰 안 함 — idiom_hook과 동일 원칙으로 성급한 확정을 막음 |
| ❌ 단점 | 실측 재현율 0/7 — 정규식이 정확한 문구만 잡아 자연어 표현 다양성에 취약, Codex의 훌륭한 reflection도 놓침(D37) |

---

## 실제 질문·답변 verbatim (D안 실행, `tier-b-risk:Bookshelf.jsx` 사례)

다른 팀원들처럼 실제 프롬프트와 실제 답변을 그대로 옮긴다. 아래는 지어낸 예시가 아니라
`evidence_bridge.py`가 실제로 생성한 질문과, 그 코드만 보고 별도 모델(Codex)이 독립
생성한 답변, 그리고 `feedback/reflection_signal.py`를 실제로 돌린 출력이다.

> **자동 생성된 질문** (`evidence_bridge.py` 실행 결과 그대로):
> "이 코드에 잠재적 위험 패턴이 있는데, 이 부분이 어떤 위험을 가질 수 있는지, 그리고
> 왜 이렇게 구현했는지 설명해보세요."

> **Codex 독립 생성 답변** (실제 코드 `Bookshelf.jsx`의 `dangerouslySetInnerHTML` 블록만 주고 생성):
>
> "이 부분은 dangerouslySetInnerHTML을 써서 XSS 위험이 있는 게 맞는 것 같습니다.
> item.title이랑 item.author가 네이버 도서 API에서 오는 값인데, 응답에 `<b>` 태그
> 같은 게 섞여 있어서 그냥 렌더링하면 태그가 텍스트로 보이는 문제가 있었고, 그걸
> 해결하려고 급하게 dangerouslySetInnerHTML로 처리했던 것 같습니다. 외부 API 응답이라도
> 신뢰할 수 있는 소스라고 안일하게 생각했던 것 같고, 스크립트 삽입 가능성 같은 건 그
> 당시엔 크게 고려하지 못했습니다. 지금 보니 정규식으로 필요한 태그만 걸러내거나
> DOMPurify 같은 걸로 sanitize하고 렌더링했어야 할 것 같습니다."

```bash
$ python3 feedback/reflection_signal.py "이 부분은 dangerouslySetInnerHTML을 써서 ..."
```
```json
{ "reflection_present": false, "matched_count": 0, "required_ok": false, "optional_matches": 0 }
```

이 답변은 XSS 실수를 정확히 인정하고("안일하게 생각했다"), 원인을 설명하고("태그가
텍스트로 보이는 문제"), 개선안까지 낸("DOMPurify로 sanitize") **정성적으로 훌륭한
reflection**인데, 우리 판정기는 0/4로 완전히 놓쳤다. 이게 아래 "가장 중요한 발견"
섹션의 근거다.

---

## 재귀 hook 자기수정 메커니즘 — 이 방법론만의 차별점

다른 방법론(A/B/C 3안 모두 박진용 문서 기준)은 "판정을 한 번 내리면 끝"인데, 이쪽은
**idiom_hook / tier_b_hook / reflection_hook / isolation_hook** 4개의 재귀 확인 구조를
붙였다 — 같은 신호가 threshold(3회, 또는 근거에 따라 2회로 조정)만큼 반복 확인되기 전엔
"미확정"으로 남기고 자동 적용하지 않는다(B안의 "채점 일관성" 문제, 박진용이 지적한
"B안 키워드 암기 취약점"을 코드로 방어하는 접근).

## 답안 품질/토큰 경제성 6-axis 채점 (PaperOrchestra 루브릭 재사용)

| 기준 | A안 | B안 | C안 | D안 | E안 |
| --- | --- | --- | --- | --- | --- |
| 토큰 경제성 평균(0~10) | 2.17 | 2.50 | **9.17** | 7.00 | 8.50 |
| 답안 품질 가중평균(0~100) | 60.25 | 72.50 | **76.00** | 72.25 | 61.00 |

C안이 "저비용·고품질" 사분면에 유일하게 위치하지만, **애초에 대화(Ownership 검증)를
하지 않는다는 근본적 범위 제한**이 있다 — 이건 박진용의 B안("빠르지만 판별력 없음")과
정확히 같은 구조의 트레이드오프다.

---

## 실측으로 드러난 가장 중요한 발견: "재현율 실패"와 "과탐지"는 다르다

E안(Reflection Hook)이 Codex 독립 생성 답변 7건 전부에서 통과 실패(0/7)했지만, fact-check
결과 원인이 두 갈래로 갈렸다.

1. **1건(Bookshelf.jsx, tier-b-risk)은 진짜 재현율 실패다** — XSS 실수를 정확히 인정하고
   DOMPurify 개선안까지 낸 고품질 reflection인데 confirmed 패턴 문구와 표현이 달라 놓쳤다.
2. **6건(cognition-isolation)은 원래 "오류 정정"이 필요한 상황 자체가 아니었다** —
   Codex 6명 전부가 GenreContext 미사용에 대해 각자 다른 타당한 설계 근거(역할 위임/
   성능 최적화/대체 저장소/도메인 무관)를 제시했다. 이건 **C안의 cognition-isolation
   판정 규칙(다중 concern 코드베이스에서 "형제는 다 허브를 써야 한다"는 가정) 자체가
   여전히 과탐지 중이라는 6번째 독립 증거**다.

이에 대응해 `isolation_hook.py`를 별도로 구현했다 — idiom_hook처럼 "정규식 하나=패턴
하나"가 아니라 "카테고리 하나(동의어 alternation)=패턴 하나"로 설계해 자연어 표현
다양성 문제를 완화했고, 실측 결과 6건 중 5건을 정확히 "타당한 근거 있음"으로 분류,
근거가 부족한 1건은 성급히 확정하지 않고 그대로 미확정으로 남겼다.

---

## 팀 공통 병목과의 수렴

김만서 문서의 결론 — **"Repository Knowledge와 Ownership을 구분해야 한다"** — 는 이쪽
결과와 정확히 같은 지점에서 재확인된다. C안은 코드만으로 "무엇이 이상한가"는 정확히
찾아내지만(Repository Knowledge), "왜 그렇게 설계했는가/재설계한다면 뭘 바꿀 것인가"
(Ownership)는 대화 없이는 원천적으로 측정할 수 없다. D안이 이 간극을 메우려 evidence
기반 질문을 자동 생성했지만, 여전히 **단발 질문**이고 손진원 문서처럼 follow-up으로
점점 깊이 들어가는 멀티턴 Socratic 루프는 구현·검증하지 못했다(API 키 미보유로
실제 대화 세션 자체가 미검증 상태).

## 결론 및 추천

**순수 C안(무료·빠름)만으로는 Ownership 검증이 불가능하다** — 박진용의 "B안만으론
부족하다"와 동일한 결론. 다만 C안+재귀 hook이 제공하는 **감사 가능한 근거(Evidence
Trace)**는 A안(LLM-as-Judge)의 블랙박스 채점 문제를 보완하는 방향으로 결합할 수 있다.
이건 박진용의 최종 권장 전략("B안으로 골격 구축 → A안으로 채점엔진 교체")과 같은
결의 결론이다 — **C안을 저비용 1차 필터로 두고, 남은 finding에 A/B안류의 실제 대화형
Ownership 인터뷰를 붙이는 하이브리드**가 다음 단계다.

## 다음 과제 3가지

1. **Reflection 재현율** — 자연어 표현이 매번 달라 정규식 하나로는 못 잡는다.
   `isolation_hook`처럼 "카테고리 단위 동의어 alternation"으로 일반화했지만, 이 설계가
   held-out(다른 repo) 데이터에서도 통하는지는 아직 미검증.
2. **cognition-isolation 과탐지** — 다중 concern 코드베이스에서 구조 신호만으로는
   "타당한 설계"와 "방치"를 구분 못한다. `isolation_hook`이 1차 완화책이지만 카테고리
   경계를 사람이 미리 정해야 하는 한계가 남는다.
3. **멀티턴 라이브 대화 미검증** — API 키 부재로 실제 세션(질문 생성 지연, 히스토리
   압축, 세션당 비용)을 전혀 측정하지 못했다. 박진용 문서의 실측치(세션당 $0.05~0.15,
   질문 생성 3~5초 지연, SSE 스트리밍 필요)를 그대로 설계 기준으로 참고해야 한다.

## 제 의견

1. **C안 자체를 "Ownership 판정 엔진"으로 팔면 안 된다고 생각합니다.** C안의 진짜
   가치는 정확도가 아니라 "비용을 0으로 만들어서, 그 다음 단계인 대화형 검증에 예산을
   몰아줄 수 있게 하는 1차 필터"라는 데 있습니다. 포지셔닝을 "채점기"가 아니라
   "트리거"로 잡아야 한다고 봅니다.
2. **Reflection Hook의 재현율 문제는 정규식 기반 접근의 근본적 한계라고 봅니다.**
   `isolation_hook`처럼 카테고리 단위로 넓혀도 결국 사람이 카테고리를 미리 정의해야
   하는 한계가 남습니다. 다음 단계로 소형 분류 모델이나 임베딩 유사도를 검토할
   가치가 있다고 생각하지만, 이건 "규칙기반의 장점(비용 0, 완전 재현)"을 일부
   포기하는 트레이드오프라 신중하게 결정해야 합니다.
3. **`cognition-isolation` 같은 구조 규칙의 "허브 하나에 다 모여야 한다"는 가정 자체가
   틀렸다는 게 이번 검증(LMS 6/6)에서 명확해졌습니다.** 패치보다 근본적으로,
   "여러 개의 국소 허브(concern별로 하나씩)를 허용"하는 방향으로 판단 블록을 다시
   설계하는 걸 다음 스프린트에서 논의해보고 싶습니다.
