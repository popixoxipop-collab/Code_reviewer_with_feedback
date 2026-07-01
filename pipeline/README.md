# 파이프라인 오케스트레이터 — 재귀 hook 폐루프를 한 번에 검증

`run_pipeline.py`는 인지→판단을 실행하고, `injections.json`에 명시된 재귀 hook 피드백을
**순차적으로** 주입하면서 단계마다 즉시 before/after 비교표를 만든다.

```bash
python3 pipeline/run_pipeline.py <target_src> <injections.json> [output.md]
```

## injections.json이 자동 추론이 아니라 사람이 채우는 입력인 이유 (D22)

이 오케스트레이터는 "이 finding이 관용 패턴/오탐인지"를 스스로 판단하지 않는다. 실제로
`jxxnixx/LMS`를 검증하며 `dangerouslySetInnerHTML`(Bookshelf.jsx) finding이 나왔는데, 코드를
직접 열어보니 네이버 도서 API 응답을 그대로 렌더링하는 **진짜 XSS 위험**이었다 — 만약
오케스트레이터가 "Tier B 히트는 다 오탐으로 간주하고 주입"하는 식으로 자동화됐다면 이 진짜
위험 신호까지 억제 대상으로 오염시켰을 것이다. 그래서 각 injection은 사람이 실제 코드를 읽고
`note`(왜 그렇게 판단했는지)를 채운 뒤 파일로 넘기는 구조로 만들었다.

## 예시

- [`examples/lms_injections.json`](./examples/lms_injections.json) — `jxxnixx/LMS`용. `useBooksQueries.ts`가
  fan_in=6으로 확산 지점 후보에 올랐는데, 실제로는 `@tanstack/react-query` 공식 문서가 권장하는
  "리소스당 커스텀 훅" 컨벤션이라 관용 패턴으로 판단해 주입함. 결과: [`../examples/lms/pipeline_result.md`](../examples/lms/pipeline_result.md)
- [`examples/study_match_injections.json`](./examples/study_match_injections.json) — `Study-Match-`용 회귀 테스트.
  이미 confirmed 상태라 재실행해도 전부 "변화 없음"으로 나오는 것 자체가 idempotency 검증

## 왜 `dangerouslySetInnerHTML`은 injections.json에 없는가

주입하지 않았다. 실제 코드(`Bookshelf.jsx:157,161`)를 확인한 결과 외부 API(네이버 도서) 응답을
그대로 HTML로 렌더링하고 있어 진짜 위험 신호였다 — "폐루프가 닫히는지"를 보여주기 위해 억지로
오탐 처리하면 판단 블록의 신뢰도 자체가 오염된다. 닫을 수 없는 루프는 안 닫는 게 맞는 결과다.
