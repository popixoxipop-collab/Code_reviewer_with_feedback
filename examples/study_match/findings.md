# Study-Match- 실행 예시 — 판단 블록 출력에 피드백 블록(Depth Ladder) 적용

대상: `github.com/popixoxipop-collab/Study-Match-` (public, React+Firebase, 소스 10파일/1,598줄)
원본 스캔: [`scan_output.json`](./scan_output.json) · 판단 결과: [`judgment_output.json`](./judgment_output.json)

각 finding은 `feedback/depth_ladder_template.md`의 7단계를 전부 채워야 "완료"로 간주한다.

---

## 최우선 — Competitions.tsx 데이터 계층 단절
> 인지: fan_in=1(정상으로 보임) / 판단: edges 기준 허브(firebase.ts) 미연결 → 최우선 격상

1. **What** — Competitions 화면 데이터는 어디서 오나요?
2. **How** — 다른 화면(Dashboard, IdeaBoard)은 Firestore 실시간 구독인데 여기는 어떻게 구현했나요?
3. **Why** — 여기만 Firestore를 안 쓴 이유는요?
4. **Alternative** — Firestore 컬렉션으로 바꾼다면 스키마를 어떻게 설계하시겠어요?
5. **Trade-off** — 지금 방식(하드코딩)과 Firestore 연동 방식의 장단점은요?
6. **Constraint** — 시간이 부족해 우선 정적 데이터로 뒀던 건가요, 아니면 외부 API 연동을 염두에 두고 자리만 잡아둔 건가요?
7. **Reflection** — `tags` 필드를 배열로 설계한다면 검색 성능 문제는 없을까요?

## Important(🔴) — firebase.ts 인증정보 유출 가능성
> 인지: Tier B 트리거(uid/email + JSON.stringify + throw 동시 등장) / 판단: 위험도 상으로 격상

1. **What** — `handleFirestoreError`가 에러 발생 시 무엇을 하나요?
2. **How** — `authInfo`(uid, email 등)를 담아 `JSON.stringify`한 뒤 새 `Error`를 던지는 흐름을 설명해보세요.
3. **Why** — 에러 메시지에 uid/email을 굳이 포함시킨 이유는요?
4. **Alternative** — 인증정보를 노출하지 않으면서 디버깅 컨텍스트를 남기는 다른 방법이 있을까요?
5. **Trade-off** — 지금 방식은 디버깅에 뭐가 편하고, 대신 어떤 위험이 있나요?
6. **Constraint** — 이 Error가 최종적으로 어디서 잡히나요? UI에 `error.message`를 그대로 보여주는 곳이 있나요?
7. **Reflection** — `authInfo`는 로그에만 남기고, `throw`엔 최소 정보만 담는 방식으로 지금 바로 리팩토링할 수 있을까요?

## 검토 대상(자동 신뢰 금지) — Competitions.tsx 시크릿 패턴
> 인지: Tier B `sk-` 정규식 매치 / 판단: 자동 확정하지 않고 "확인 필요"로만 표시

실측 결과 오탐(캐글 URL 문자열 `"...credit-risk-model-stability"` 안의 `risk-s`가 `sk-`와 우연히 매치). **판단 블록이 이 신호를 그대로 위험으로 승격하지 않고 별도 등급으로 격리한 것 자체가 설계 포인트** — 신뢰도 낮은 트리거는 자동 확정 대신 사람 확인 대기열로 보내야 한다는 실증 사례.

## 질문 대상 — onSnapshot 반복 등장 (Dashboard×3, ChatRoom×2, StudyGroups×2, IdeaBoard×2)
1. **What** — 4개 파일에 각각 몇 번이나 직접 작성했나요?
2. **How** — 각 콜백 내부에서 상태를 업데이트하는 로직을 설명해보세요.
3. **Why** — 이 로직을 공용 훅(`useFirestoreQuery` 등)으로 뽑지 않은 이유는요?
4. **Alternative** — 커스텀 훅으로 추출한다면 어떤 인자를 받도록 설계하시겠어요?
5. **Trade-off** — 지금처럼 각자 작성하면 뭐가 편하고, 훅으로 뽑으면 뭐가 편해지나요?
6. **Constraint** — 화면마다 정렬 기준/limit이 달라서 공통화가 어려웠던 건가요?
7. **Reflection** — 리팩토링 시간이 30분 주어진다면 어느 파일부터 손대시겠어요?
