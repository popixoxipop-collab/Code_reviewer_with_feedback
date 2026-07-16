# Pipeline Lab 서비스 플로우 다이어그램 (P01/P02/P03)

AIVLE EDU 기업표준 서비스플로우 양식(가로 스윔레인, 원/사각형/마름모)을 참고해 P01/P02/P03 각각의 실제 동작을 다이어그램으로 정리한 것. 진짜 AND/OR 논리 결합이 있는 분기는 표준 디지털 논리게이트 도형(AND=D자형, OR=방패형)으로, 단순 임계값 비교 분기는 마름모/일반 노드로 구분해서 그렸다.

**두 버전이 공존한다** — 아래 D1 참고.

- `p01_flow_diagram.html` / `p02_flow_diagram.html` / `p03_flow_diagram.html` — **상세판**(Codex 손제작, 원본 파이프라인의 단계를 전부 개별 노드로 표시)
- `p01_flow_diagram_compact.html` / `p02_flow_diagram_compact.html` / `p03_flow_diagram_compact.html` — **컴팩트판**(archify 스킬, 워크플로우 스윔레인 자동배치 + 손수 AND/OR 게이트 SVG 주입)
- `p0X_compact_source.workflow.json` — 컴팩트판을 archify로 재생성할 때 쓰는 입력 JSON(각 파일 안에 `node bin/archify.mjs render workflow <json> <html>` 커맨드가 재사용 가능하도록 그대로 보존됨)

## D1: 상세판 vs 컴팩트판, 하나로 통일하지 않고 둘 다 보관

- **WHY**: 상세판(Codex)은 원본 코드의 모든 단계를 1:1로 보여주지만 손으로 그린 SVG라 가로 2760~5400px에 스크롤이 필요하고 테마/내보내기 기능이 없다. 컴팩트판(archify)은 archify 자체의 워크플로우 레이아웃 엔진(6컬럼 고정 그리드) 제약 때문에 단계를 노드/카드로 병합해야 했다(P01 17단계→4노드, P02 35노드→7, P03 약30단계→16개) — 대신 네이티브 다크/라이트 테마토글과 PNG/JPEG/WebP/SVG(최대4배) 내보내기 메뉴가 생기고 가로스크롤 없이 한 화면에 들어온다. 둘 다 장단점이 명확히 갈려서 사용자가 "둘 다 보관"으로 결정 — 상세 설명이 필요하면 상세판, 발표/공유용 깔끔한 이미지가 필요하면 컴팩트판.
- **COST**: 같은 내용을 두 파일 세트(6개 HTML + 3개 JSON)로 유지해야 함 — 로직이 바뀌면 두 버전 다 갱신해야 드리프트가 안 생김(자동 동기화 없음, 아래 EXIT 참고). 컴팩트판은 원본만큼 세밀하지 않다는 걸 이미 각 다이어그램 하단 "다이어그램 단순화 메모" 카드에 명시해뒀지만, 그 카드를 안 읽으면 압축 사실을 놓칠 수 있음.
- **EXIT**: 상세판만 남기고 싶으면 `*_compact.html`+`*_compact_source.workflow.json` 6개만 지우면 됨(상세판은 완전히 독립). 컴팩트판만 남기고 싶으면 반대로. 나중에 로직이 바뀌면: 상세판은 같은 Codex 위임 절차(아래 D2) 재사용, 컴팩트판은 `~/.claude/skills/archify`에서 `node bin/archify.mjs render workflow p0X_compact_source.workflow.json <output>.html` 재실행 후 게이트 주입만 다시 하면 됨(D3 기법 재사용).

## D2: 상세판을 만든 방법 (Codex, WHY/COST/EXIT)

- **WHY**: 3개 파이프라인의 실제 코드 로직(특히 AND/OR 분기 조건)을 실제 사용자가 눈으로 검토 가능한 형태로 남기기 위함. Codex 서브에이전트 3개(파이프라인당 1개, 병렬)가 각각 실제 소스(`scripts/java_curriculum_nvidia_pipeline.py`, `docs/lab/{p01,p02,p03}-*.js`, `cognition/`, `judgment/`, `feedback/`)를 직접 읽고 AND/OR 근거를 파일:라인 단위로 검증한 뒤 이 HTML/SVG 문서를 작성했다.
- **COST**: 손으로 그린 SVG라 파이프라인 로직이 바뀌면 이 문서는 자동으로 갱신되지 않는다(원본 코드가 정본, 이 문서는 스냅샷). 다이어그램 폭이 넓어(P01 2760px/P03 5400px) 일반 화면에서 가로 스크롤이 필요하다.
- **EXIT**: 로직이 바뀌면 이 폴더의 해당 HTML만 다시 생성하면 된다(같은 Codex 위임 절차 재사용 가능) — 나머지 `docs/lab/` 실제 도구 코드와는 독립적이라 이 폴더를 통째로 지워도 Pipeline Lab 자체 동작에는 영향 없음.

## D3: 컴팩트판을 만든 방법 (archify + 수제 게이트 주입, WHY/COST/EXIT)

- **WHY**: `popixoxipop-collab/archify`(fork of `tt-a1i/archify`) 스킬로 상세판을 다시 만들어보라는 요청 → archify의 `workflow` 렌더러가 `common.schema.json`의 `componentType` enum 7종(frontend/backend/database/cloud/security/messagebus/external) 고정 사각형만 지원하고 커스텀 SVG 도형(AND/OR 게이트, 다이아몬드)을 그릴 방법이 스키마에 없음을 확인 — 순수 archify만으로는 "실제 표준 로직게이트 도형" 요구사항을 못 채움. 하이브리드로 절충: archify가 스윔레인 골격을 렌더한 뒤, 렌더된 HTML의 게이트 노드 two-rect 패턴(`<rect class="c-mask">`+`<rect class="c-security">`, 동일 x/y/w/h)을 `<g transform="translate(X,Y) scale(W/66,H/58)">`로 감싼 재사용 gate path(AND: 66×58 박스 `M0 0 L36 0 C66 0 66 58 36 58 L0 58 Z`, OR: 78×58 박스 2-path)로 직접 교체 — 상세판(D2)에서 이미 검증된 geometry를 그대로 재사용, `class="c-mask"`/`class="c-security"`는 유지해 archify 기존 CSS 변수(`var(--security-fill)` 등)로 테마토글이 자동 작동하게 함(하드코딩 색상 금지, archify의 "Cardinal Rule").
- **COST**: archify의 6컬럼 고정 그리드 레이아웃 예산 때문에 원본 단계 수를 그대로 못 옮기고 노드/카드로 압축해야 했음(위 D1 COST 참고) — 이건 archify 자체의 구조적 제약이라 게이트 주입 기법을 더 다듬어도 해결 안 됨, 노드 수를 줄이거나 `groups`/`cards`로 흡수하는 수밖에 없다.
- **EXIT**: archify의 workflow 렌더러가 나중에 커스텀 노드 도형을 지원하게 되면(현재는 미지원) 이 수제 주입 단계 자체가 불필요해짐 — 그 전까지는 `p0X_compact_source.workflow.json`을 고치고 `node bin/archify.mjs render workflow`로 재렌더한 뒤, 이 문서에 적힌 gate path geometry로 다시 주입하는 절차를 반복.

## 검증

**상세판**: Playwright로 실제 렌더링해서 육안 확인 완료(콘솔 에러 없음, 논리게이트 도형/스윔레인/AND-OR 설명표 정상 표시). AND/OR 게이트 설명표의 파일:라인 근거는 Codex가 직접 코드를 읽고 인용한 것.

**컴팩트판**: 3개 fork가 각각 Playwright로 라이트/다크 테마 양쪽 렌더링 후 (a) 콘솔 에러 0건, (b) 게이트 도형이 실제 AND(D자형)/OR(방패형)로 렌더되는지, (c) 테마 전환 시 게이트 색상이 실제로 바뀌는지(computed style 직접 확인)를 검증. 이후 코디네이터가 독립적으로 재검증: 정적 분석으로 하드코딩 색상 부재 확인(grep, 3개 파일 전부 0건), gate path occurrence를 직접 세어 각 다이어그램의 게이트 개수·타입이 자체 보고와 일치하는지 교차검증(P02는 첫 측정에서 불일치로 보였으나 fork가 OR 도형 뒷면 곡선을 별도 stroke로 처리한 정당한 구현 차이였음을 스크린샷으로 재확인), 3개 스크린샷 육안 확인, 그리고 최종 프로덕션 위치(`docs/lab/flow-diagrams/`)로 복사한 뒤 별도 Playwright 스크립트로 콘솔 에러 0건 재확인.
