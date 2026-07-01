# 재귀 hook 폐루프 검증 — LMS/src

## 1단계: idiom_hook 주입 — react-query-custom-hook

| Finding | Before | After | 변화 |
|---|---|---|---|
| `architecture-diffusion:useBooksQueries.ts` | 상 | 하 | ✅ 변경됨 |
| `cognition-isolation:Auth.jsx` | 상 | 상 | — |
| `cognition-isolation:BookDetail.jsx` | 상 | 상 | — |
| `cognition-isolation:BookList.jsx` | 상 | 상 | — |
| `cognition-isolation:Header.jsx` | 상 | 상 | — |
| `cognition-isolation:LibraryScene.jsx` | 상 | 상 | — |
| `cognition-isolation:authToken.js` | 상 | 상 | — |
| `tier-b-risk:Bookshelf.jsx:dangerous-html` | 중 | 중 | — |
