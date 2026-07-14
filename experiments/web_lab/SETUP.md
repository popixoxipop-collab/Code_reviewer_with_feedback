# Pipeline Lab 설정 (docs/lab/)

이 문서의 단계는 전부 계정 소유자(프로젝트 owner)가 직접 해야 한다 — 에이전트가 대신 Supabase/
Cloudflare 계정을 만들거나 배포할 수 없다. 코드는 전부 repo에 이미 있고, 아래는 그걸 실제로
동작시키는 데 필요한 외부 서비스 설정뿐이다.

## 0. 아무것도 설정 안 해도 되는 부분

`docs/lab/index.html`을 열면 **P02(코드 분석)는 바로 동작한다** — API 키도, 프록시도, DB도
필요 없다(LLM을 아예 안 부르는 파이프라인이라서). GitHub PAT도 공개 repo면 선택사항.
나머지 단계는 P01/P03(LLM 호출)과 결과 DB 저장을 켜고 싶을 때만 필요하다.

## 1. NVIDIA 프록시 배포 (P01·P03에 필요) — ✅ 완료 (2026-07-14)

`integrate.api.nvidia.com`은 브라우저 직접 호출을 막는다(CORS 헤더 없음, 2026-07-14 실측
확인) — `worker/nvidia-proxy.js`가 그 우회로다.

사용자가 제공한 Cloudflare API 토큰(Edit Cloudflare Workers 템플릿)으로 `wrangler login`
없이 `CLOUDFLARE_API_TOKEN` 환경변수로 비대화형 배포 완료.

- **배포된 URL**: `https://nvidia-proxy.popixoxipop.workers.dev` — `docs/lab/config.js`의
  `DEFAULT_PROXY_URL`에 기본값으로 미리 채워둠(Supabase와 달리 이 필드는 그대로 편집 가능하게
  남겨둠 — URL이지 자격증명이 아니고, 팀원이 자기 프록시로 바꿔 쓸 수 있어야 하므로).
- 계정에 workers.dev 서브도메인이 아예 없어서(신규 Cloudflare 계정) `popixoxipop`으로 먼저
  등록해야 배포가 됨(Management API `PUT /accounts/{id}/workers/subdomain`).
- 신규 서브도메인이라 TLS 인증서 전파에 몇 분 걸림(첫 요청들은 SSL handshake failure) —
  실제 코드가 문서화한 동작(헤더 없는 POST→401 `"missing x-nvidia-api-key header"`,
  OPTIONS→204+CORS 헤더)까지 맞는지 확인하고서야 완료로 표시.

**팀원 각자 자기 프록시를 쓰고 싶으면**: 같은 `worker/nvidia-proxy.js`를 각자 배포하고 자기
URL로 필드를 덮어쓰면 된다 — owner의 프록시를 거치지 않아도 되도록 설계돼 있다.

```bash
npm install -g wrangler
wrangler login            # Cloudflare 무료 계정으로 로그인 (없으면 가입)
cd worker
wrangler deploy nvidia-proxy.js --compatibility-date <오늘날짜>
```

선택: `worker/nvidia-proxy.js`의 `ALLOWED_ORIGIN`을 `"*"`에서 실제 GitHub Pages 주소
(예: `https://popixoxipop-collab.github.io`)로 좁히면 다른 사이트가 이 프록시를 얹어 쓰는 걸
막을 수 있다(키 자체 유출과는 별개 — 방어층 하나 더). 아직 안 함(스코프 밖).

## 2. Supabase 프로젝트 생성 (DB 저장에 필요) — ✅ 완료 (2026-07-14)

사용자가 제공한 Management API PAT으로 에이전트가 대신 실행 완료(이례적 — 보통은 계정 소유자만
가능한 단계인데, 이번엔 PAT이 직접 제공돼서 진행함).

- 프로젝트: `code-reviewer-pipeline-lab` (org `popixoxipop`, region `ap-northeast-2` Seoul, plan free)
- **Project URL**: `https://oziaeqcvrkrqkhwrybfj.supabase.co`
- **anon key**: 팀 공용 DB라 `docs/lab/config.js`의 `TEAM_SUPABASE_ANON_KEY`에 하드코딩돼
  있음(사용자 지시: "공용으로 사용하는 거라 하드코딩 해놓고 안보이게 가려놔") — 연결 설정
  패널에서 입력받지 않음. Supabase 대시보드 → Settings → API Keys에서도 확인 가능(RLS로
  보호되므로 클라이언트 코드에 박혀 있어도 되는 키, NVIDIA 키/PAT과는 다른 취급).
- `supabase_schema.sql` 실행 완료 — `members`/`runs`/`stage_events`/`artifacts`/`presets` 5개
  테이블 전부 생성 확인, RLS 5개 테이블 전부 활성화 확인(SQL로 직접 조회해 검증, 추측 아님).
- DB 비밀번호는 무작위 생성해 세션 채팅에서 1회 표시함 — 웹 도구 자체는 이 비밀번호를 쓰지
  않음(anon key만 씀), 잃어버리면 대시보드 Settings → Database에서 재설정 가능.

## 3. 인증(매직 링크) 켜기 — ✅ 완료 (2026-07-14)

- `external_email_enabled: true` 확인(기본값, 별도 조치 불필요)
- **Site URL**을 `https://popixoxipop-collab.github.io/Code_reviewer_with_feedback/lab/`로 설정
  완료(Management API로), `uri_allow_list`에 로컬 개발용(`http://localhost:8712/lab/**`)도
  같이 추가
- 팀원 허용 범위(PLAN.md 열린 질문 1)는 **아직 미결정** — 기본값은 "아무나 가입 가능". 특정
  이메일만 받고 싶으면 `handle_new_member()` 함수에 도메인 체크를 추가하는 식으로 SQL 수정
  필요(사용자 결정 필요, 아직 안 함)

## 4. GitHub Pages에 배포

`docs/lab/`은 이미 repo 안에 있다 — `main` 브랜치에 push되면 GitHub Pages가 자동으로 갱신한다
(이 repo가 이미 GitHub Pages를 쓰고 있으므로 추가 설정 불필요). 확인:
`https://popixoxipop-collab.github.io/Code_reviewer_with_feedback/lab/`

## 5. 팀원에게 공유할 때

각 팀원에게 알려줄 것(2026-07-14부터 실제로 이게 전부임 — 프록시 URL도 이미 기본값으로 채워져 있음):
- Pipeline Lab URL
- 자기 NVIDIA API 키(각자 https://build.nvidia.com 에서 발급, 무료)를 상단 "연결 설정"에
  직접 입력할 것 — 이 키는 서버로 전송되지 않고 DB에도 저장되지 않는다(P01/P03 실행에만 씀)
- 로그인용 이메일(매직 링크로 로그인, 비밀번호 없음) — DB는 팀 공용으로 이미 연결돼 있어
  Supabase URL/키는 입력받지 않음, 로그인만 하면 됨
- (선택) 프록시 URL은 owner가 배포한 게 기본값으로 이미 채워져 있음 — 자기 프록시를 쓰고
  싶으면 그 필드를 자기 URL로 덮어쓰면 됨

## 확인 체크리스트

- [ ] P02: repo 하나(owner/repo 형식)로 스캔 → finding이 화면에 나오는지
- [x] 프록시 배포: 실측 완료(2026-07-14) — 헤더 없는 POST가 401 `missing x-nvidia-api-key
      header`, OPTIONS가 204+CORS 헤더 반환 확인
- [ ] 프록시 end-to-end: 실제 NVIDIA 키 입력 후 P01 청크 1개짜리 PDF로 실제 응답이 오는지
      (테스트용 NVIDIA 키가 아직 없어서 이 마지막 연결까지는 미확인)
- [ ] DB: 로그인 후(URL/키 입력 불필요, 이미 하드코딩됨) P02 실행 → Supabase 대시보드
      Table Editor에서 `runs` 테이블에 행이 생겼는지 확인
- [ ] RLS: 다른 계정으로 로그인해서 `runs`가 보이되(읽기 전체 허용), 로그인 안 한 상태에서
      쓰기(insert)가 막히는지 확인
