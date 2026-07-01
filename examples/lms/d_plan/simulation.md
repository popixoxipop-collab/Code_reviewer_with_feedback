# D안 실행 로그 — jxxnixx/LMS

`pipeline/evidence_bridge.py`로 C안(judgment_output.json, 8 findings)을 실제로 B안 형식
Evidence Packet 8개로 변환했다(전부 실제 실행, [`evidence_packets.json`](./evidence_packets.json) 참고).
**학생 답변 부분은 API 키가 없어 실제 LLM 호출 대신 시뮬레이션(가상 답변)으로 대체했다 —
아래는 명시적으로 시뮬레이션임을 표시한다.**

## 자동 필터링 (실제 결과) — 8건 중 1건은 인터뷰 없이 이미 종결

```
idiom_or_risk_status 분포: unresolved_signal=6, confirmed_idiom=1, tier_b_risk=1
```
`architecture-diffusion:useBooksQueries.ts`는 코드 레벨 Rule(react-query-custom-hook idiom
confirmed)이 이미 적용돼 질문가치가 상→하로 확정됐다 — **이 finding은 인터뷰 없이 종결**된다.
이게 D안이 순수 B안 대비 갖는 토큰 경제성 이점의 실체다: 8건 중 1건(12.5%)은 LLM 호출
자체가 필요 없다.

## 인터뷰 — tier-b-risk:Bookshelf.jsx:dangerous-html

**자동 생성된 질문** (evidence_bridge.py 출력 그대로):
> 이 코드에 잠재적 위험 패턴이 있는데, 이 부분이 어떤 위험을 가질 수 있는지, 그리고
> 왜 이렇게 구현했는지 설명해보세요.

**[Codex 독립 생성 답변]** — 직접 작성하지 않고 별도 모델(codex:codex-rescue)에 실제
코드(`Bookshelf.jsx`의 `dangerouslySetInnerHTML` 블록)와 질문만 주고 학생 역할극으로
생성시켰다(보안연구/교육 목적, 실제 학생 데이터 아님):

> 이 부분은 dangerouslySetInnerHTML을 써서 XSS 위험이 있는 게 맞는 것 같습니다.
> item.title이랑 item.author가 네이버 도서 API에서 오는 값인데, 응답에 `<b>` 태그
> 같은 게 섞여 있어서 그냥 렌더링하면 태그가 텍스트로 보이는 문제가 있었고, 그걸
> 해결하려고 급하게 dangerouslySetInnerHTML로 처리했던 것 같습니다. 외부 API 응답이라도
> 신뢰할 수 있는 소스라고 안일하게 생각했던 것 같고, 스크립트 삽입 가능성 같은 건 그
> 당시엔 크게 고려하지 못했습니다. 지금 보니 정규식으로 필요한 태그만 걸러내거나
> DOMPurify 같은 걸로 sanitize하고 렌더링했어야 할 것 같습니다.

**Rule 적용**: 이 답변은 실제로 상당히 질 높은 응답이다 — 원래 왜 그렇게 짰는지(이유),
당시 놓친 것(자기오류인식), 지금이라면 어떻게 할지(새판단+구체적 개선안)를 전부 담고 있다.

**Reflection 판정(실제 코드 실행, 사람이 답을 미리 안 보고 그대로 넣음)**:
```bash
python3 feedback/reflection_signal.py "이 부분은 dangerouslySetInnerHTML을 써서 XSS 위험이 있는 게 맞는 것 같습니다. ..."
```
```json
{ "reflection_present": false, "matched_count": 0, "required_ok": false, "optional_matches": 0 }
```

**실측으로 드러난 훨씬 심각한 한계**: 이 답변은 정성적으로 이번 세션에서 나온 어떤 예시보다도
완성도 높은 진짜 reflection인데(원래 시드 예시인 B안 문서 자체의 "아 맞네요. 너무
신뢰했습니다"보다도 서사가 풍부함), 정규식이 정확한 문구만 잡다 보니 **0/4로 완전히
놓쳤다.** 직접 쓴 시뮬레이션 답변이 아니라 완전히 독립된 모델이 생성한 답변으로 검증했기
때문에 이 결과는 "내가 패턴에 맞춰 답을 썼다"는 의심에서 자유롭다 — 재현율 문제가
가짜가 아니라 진짜라는 뜻이다.

**후속 조치(신중하게, 성급히 승격 안 함)**: 이 답변에서 확인된 3개 표현("안일하게 생각",
"지금 보니", "sanitize/DOMPurify")을 새 후보 패턴으로 각각 1/3 confirmations만 기록했다
(`feedback reflection_hook.py feedback ... genuine_signal`). D32~D34 설계 원칙대로
**단 1건의 압도적인 예시만으로 즉시 confirmed 승격하지 않았다** — threshold=3을 그대로
지켜 재확인 후 promotions=[]로 남아있음을 확인했다. 앞으로 2건이 더 쌓여야 이 표현들이
자동 인식된다.

## 종합

D안은 "Evidence 자동 생성 + 코드 레벨 Rule 선(先)적용"까지는 실제로 작동하고 토큰을
절약한다(8건 중 1건 인터뷰 생략). 그러나 이어지는 학생 답변 평가(Reflection 판정)는
**독립 모델이 생성한 고품질 답변조차 못 잡을 만큼 재현율이 낮다**는 게 이번 실측으로
분명해졌다 — "완성된 파이프라인"이 아니라 "인지/판단은 검증됐고 피드백 평가는 아직
정밀도만 높고 재현율은 매우 낮은 상태"임을 정직하게 기록한다.
