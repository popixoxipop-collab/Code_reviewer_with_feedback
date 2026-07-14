# Pipeline Lab 설정 (docs/lab/)

이 문서의 단계는 전부 계정 소유자(프로젝트 owner)가 직접 해야 한다 — 에이전트가 대신 Supabase/
Cloudflare 계정을 만들거나 배포할 수 없다. 코드는 전부 repo에 이미 있고, 아래는 그걸 실제로
동작시키는 데 필요한 외부 서비스 설정뿐이다.

## 0. 아무것도 설정 안 해도 되는 부분

`docs/lab/index.html`을 열면 **P02(코드 분석)는 바로 동작한다** — API 키도, 프록시도, DB도
필요 없다(LLM을 아예 안 부르는 파이프라인이라서). GitHub PAT도 공개 repo면 선택사항.
나머지 단계는 P01/P03(LLM 호출)과 결과 DB 저장을 켜고 싶을 때만 필요하다.

## 1. NVIDIA 프록시 배포 (P01·P03에 필요)

`integrate.api.nvidia.com`은 브라우저 직접 호출을 막는다(CORS 헤더 없음, 2026-07-14 실측
확인) — `worker/nvidia-proxy.js`가 그 우회로다. 코드를 그대로 공개해뒀으니 배포 전에 읽어보고
뭘 하는지(키를 한 헤더에서 다음 요청으로 넘기기만 함, 로깅/저장 없음) 확인해도 된다.

```bash
npm install -g wrangler   # 최초 1회
wrangler login            # Cloudflare 무료 계정으로 로그인 (없으면 가입)
cd worker
wrangler deploy nvidia-proxy.js
```

배포가 끝나면 `https://nvidia-proxy.<your-subdomain>.workers.dev` 같은 URL이 나온다 — 이걸
Pipeline Lab 상단 "연결 설정"의 **LLM 프록시 URL**에 넣는다.

**팀원 각자 자기 프록시를 쓰고 싶으면**: 같은 `worker/nvidia-proxy.js`를 각자 배포하고 자기
URL을 넣으면 된다 — owner의 프록시를 거치지 않아도 되도록 설계돼 있다.

선택: `worker/nvidia-proxy.js`의 `ALLOWED_ORIGIN`을 `"*"`에서 실제 GitHub Pages 주소
(예: `https://popixoxipop-collab.github.io`)로 좁히면 다른 사이트가 이 프록시를 얹어 쓰는 걸
막을 수 있다(키 자체 유출과는 별개 — 방어층 하나 더).

## 2. Supabase 프로젝트 생성 (DB 저장에 필요)

1. https://supabase.com → 무료 프로젝트 생성 (region: Seoul 권장, 팀이 한국이면)
2. 프로젝트 대시보드 → SQL Editor → `experiments/web_lab/supabase_schema.sql` 전체 내용 붙여넣고 Run
3. 프로젝트 Settings → API → **Project URL**과 **anon public key** 복사
   → Pipeline Lab 상단 "연결 설정"의 Supabase URL / anon key에 입력

## 3. 인증(매직 링크) 켜기

1. Supabase 대시보드 → Authentication → Providers → Email이 기본으로 켜져 있는지 확인
2. Authentication → URL Configuration → **Site URL**을 GitHub Pages 주소로 설정
   (예: `https://popixoxipop-collab.github.io/Code_reviewer_with_feedback/lab/`)
   — 매직 링크 이메일의 리디렉션이 이 주소로 온다.
3. 팀원 허용 범위를 정한다(PLAN.md 열린 질문 1):
   - 아무나 가입 가능하게 둘 거면 이 단계는 생략
   - 특정 이메일만 받고 싶으면 Authentication → Auth Hooks 또는 Authentication → Policies에서
     이메일 도메인/allowlist 체크를 추가(Supabase 대시보드에서 UI로 가능한 범위 밖이면
     `handle_new_member()` 함수에 도메인 체크를 추가하는 식으로 SQL을 수정)

## 4. GitHub Pages에 배포

`docs/lab/`은 이미 repo 안에 있다 — `main` 브랜치에 push되면 GitHub Pages가 자동으로 갱신한다
(이 repo가 이미 GitHub Pages를 쓰고 있으므로 추가 설정 불필요). 확인:
`https://popixoxipop-collab.github.io/Code_reviewer_with_feedback/lab/`

## 5. 팀원에게 공유할 때

각 팀원에게 알려줄 것:
- Pipeline Lab URL
- 자기 NVIDIA API 키(각자 https://build.nvidia.com 에서 발급, 무료)를 상단 "연결 설정"에
  직접 입력할 것 — 이 키는 서버로 전송되지 않고 DB에도 저장되지 않는다(P01/P03 실행에만 씀)
- 프록시 URL(owner가 배포한 것을 쓰거나, 원하면 자기 것 배포)
- 로그인용 이메일(매직 링크로 로그인, 비밀번호 없음)

## 확인 체크리스트

- [ ] P02: repo 하나(owner/repo 형식)로 스캔 → finding이 화면에 나오는지
- [ ] 프록시: NVIDIA 키 + 프록시 URL 입력 후 P01 청크 1개짜리 PDF로 실제 응답이 오는지
- [ ] DB: Supabase URL/키 입력 + 로그인 후 P02 실행 → Supabase 대시보드 Table Editor에서
      `runs` 테이블에 행이 생겼는지 확인
- [ ] RLS: 다른 계정으로 로그인해서 `runs`가 보이되(읽기 전체 허용), 로그인 안 한 상태에서
      쓰기(insert)가 막히는지 확인
