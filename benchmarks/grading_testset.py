# D64: 실제 학생 답변이 전무하므로(README/EVALUATION.md가 이미 인정) 목표레벨을 사람이
# 먼저 정해두고 그 레벨에 맞춰 답변 텍스트를 직접 쓴 시뮬레이션 셋이다.
#
# 한계(반드시 결과 문서에 그대로 옮길 것): 여기서 "target_level"은 "우리가 이 레벨을
# 의도하고 썼다"는 자기참조적 라벨일 뿐, 실제 사람 채점자가 매긴 점수가 아니다. 채점
# 모델이 이 라벨을 복원하는지를 측정하는 것이지, 채점 모델이 "진짜 사람 판단"과 얼마나
# 일치하는지를 측정하는 게 아니다 — README D57 COST("실제 학생 답변으로 자동 초안과
# 사람 판정이 얼마나 어긋나는지 비교 검증은 못 함")와 동일 성격의 한계다.
#
# 5개 finding(최우선 1 / Important 2 / 질문대상 2, study_match+lms 양쪽에서) x 3레벨
# (1=하/3=중/5=상) = 15개 답변. 한 답변이 5축 전부에서 동시에 채점되므로, 레벨이 높을수록
# 답변에 (a)구조 설명 (b)반례 선제 인지 (c)구체적 대안 (d)제약조건과 연결된 설계논리
# (e)자기수정 신호를 전부 담고, 낮을수록 전부 생략한다 — RUBRIC(interview_rubric.py) 레벨
# 설명을 그대로 satisfy하도록 문장 단위로 맞춰 썼다.
from __future__ import annotations

import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = {
    "study_match": "examples/study_match/judgment_output.json",
    "lms": "examples/lms/judgment_output_baseline.json",
}

# (fixture, finding_id) -> 질문 1개(Depth Ladder 스타일, generate_questions.py가 실제로
# 만들 법한 형태를 대표해서 손으로 하나씩 씀 — 이 벤치마크는 채점만 측정하므로 질문 자체는
# 고정해서 변수를 하나 줄인다)
QUESTIONS = {
    ("study_match", "cognition-isolation:Competitions.tsx"):
        "Competitions.tsx는 다른 화면들과 달리 firebase.ts 허브를 거치지 않던데, 이 데이터는 "
        "어디서 오나요? 그리고 왜 다른 화면들과 다른 경로를 택했나요?",
    ("study_match", "tier-b-risk:firebase.ts"):
        "firebase.ts에서 인증 실패 시 uid/email이 담긴 객체를 JSON.stringify해서 Error에 "
        "실어 던지던데, 이 방식을 택한 이유가 뭔가요? 이 에러가 클라이언트 로그나 에러 리포팅 "
        "서비스로 그대로 전달되면 어떻게 되나요?",
    ("lms", "tier-b-risk:Bookshelf.jsx:dangerous-html"):
        "Bookshelf.jsx에서 dangerouslySetInnerHTML을 쓰고 있던데, 이 HTML의 출처가 "
        "어디인가요? 사용자가 직접 입력한 텍스트가 여기 섞여 들어갈 가능성은 없나요?",
    ("study_match", "repeated-pattern:onSnapshot"):
        "onSnapshot 구독 코드가 StudyGroups/Dashboard/ChatRoom/IdeaBoard 네 군데에 "
        "비슷한 형태로 반복되던데, 왜 공용 훅으로 뽑지 않았나요?",
    ("lms", "architecture-diffusion:useBooksQueries.ts"):
        "useBooksQueries.ts를 여러 컴포넌트가 공유해서 쓰던데, 이걸 이렇게 중앙화한 "
        "이유가 뭔가요? React Query를 이렇게 쓰는 게 팀의 의도적 컨벤션인가요, 아니면 "
        "그냥 예제를 따라간 건가요?",
}

# (fixture, finding_id, target_level) -> 답변 텍스트
ANSWERS = {
    # --- Competitions.tsx 고립 (최우선) ---
    ("study_match", "cognition-isolation:Competitions.tsx", 1):
        "그냥 그렇게 짰습니다. 딱히 이유는 없어요.",
    ("study_match", "cognition-isolation:Competitions.tsx", 3):
        "Competitions 데이터는 아마 별도 API나 로컬 state에서 오는 것 같아요. firebase.ts를 "
        "안 거치는 게 문제일 수도 있겠네요, 근데 구체적으로 뭘 어떻게 고쳐야 할지는 잘 모르겠어요.",
    ("study_match", "cognition-isolation:Competitions.tsx", 5):
        "Competitions.tsx는 firebase.ts 허브를 안 거치고 별도의 REST 엔드포인트에서 대회 "
        "일정을 직접 fetch합니다. 처음엔 다른 화면처럼 firebase.ts를 거치려 했는데, 대회 "
        "일정이 실시간 동기화가 필요 없고 캐싱이 더 중요해서 의도적으로 분리했습니다. "
        "트레이드오프는 있습니다 — 데이터 계층이 두 갈래로 나뉘면서 향후 인증 로직이 "
        "바뀌면 이 파일만 따로 챙겨야 하는 유지보수 부담이 생깁니다. 다시 물으신 김에 "
        "생각해보니, 지금처럼 조용히 분리해두는 것보다 firebase.ts에 read-only 어댑터를 "
        "하나 얹어서 이 파일도 같은 진입점을 쓰게 하고 캐싱만 별도로 하는 게 더 나았을 것 "
        "같습니다 — 다음 스프린트에 그렇게 리팩터링하겠습니다.",
    # --- firebase.ts auth leak (Important) ---
    ("study_match", "tier-b-risk:firebase.ts", 1):
        "에러 메시지에 정보를 좀 넣은 것뿐이에요. 문제 없다고 생각합니다.",
    ("study_match", "tier-b-risk:firebase.ts", 3):
        "디버깅할 때 어떤 유저였는지 보려고 넣었어요. 클라이언트로 유출될 수 있다는 건 "
        "듣고 보니 그럴 수도 있겠네요. 근데 지금 당장 어떻게 고쳐야 할지는 잘 모르겠습니다.",
    ("study_match", "tier-b-risk:firebase.ts", 5):
        "인증 실패 원인을 서버 로그에서 추적하려고 uid/email을 Error 메시지에 실었습니다. "
        "다만 이 Error가 그대로 클라이언트 콘솔이나 Sentry 같은 에러 리포팅 서비스로 전파되면 "
        "개인정보가 그대로 노출된다는 문제가 있고, 이건 제가 처음 설계할 때 놓쳤던 부분입니다. "
        "대안은 두 가지입니다 — (1) 서버 사이드에서만 별도 request-id로 로깅하고 클라이언트엔 "
        "일반화된 메시지만 던지거나, (2) 에러 객체를 구조화해서 sensitive 필드를 "
        "리포팅 미들웨어에서 필터링하는 방법. 지금 구조의 트레이드오프는 디버깅 편의성 "
        "대신 정보 유출 위험을 감수한 겁니다. 반례를 듣고 보니 이건 제가 '내부 로그니까 "
        "괜찮다'고 안일하게 판단한 것이었고, request-id 방식으로 다음 커밋에서 바로 "
        "고치겠습니다.",
    # --- Bookshelf.jsx dangerouslySetInnerHTML (Important) ---
    ("lms", "tier-b-risk:Bookshelf.jsx:dangerous-html", 1):
        "책 소개 HTML을 그냥 넣어주는 겁니다. 별문제 없어 보이는데요.",
    ("lms", "tier-b-risk:Bookshelf.jsx:dangerous-html", 3):
        "책 소개글에 마크다운 같은 서식이 필요해서 HTML로 렌더링했어요. 사용자 입력이 "
        "섞일 수 있다는 건 맞는 것 같은데, 지금 당장 sanitize를 어떻게 붙여야 할지는 "
        "구체적으로 모르겠어요.",
    ("lms", "tier-b-risk:Bookshelf.jsx:dangerous-html", 5):
        "책 소개글에 굵게/링크 같은 서식을 지원하려고 dangerouslySetInnerHTML을 썼는데, "
        "이 텍스트는 결국 도서관리자가 마크다운으로 입력한 값을 변환한 겁니다. 문제는 "
        "관리자 계정이 탈취되거나 입력 검증이 뚫리면 그대로 XSS로 이어진다는 점입니다. "
        "DOMPurify로 렌더링 직전에 sanitize하거나, 아예 markdown-to-jsx처럼 HTML을 "
        "안 거치고 컴포넌트 트리로 변환하는 라이브러리로 바꾸는 대안이 있습니다. 지금은 "
        "서식의 자유도를 얻는 대신 보안 검증 지점을 하나 늘린 셈인데, 반례를 듣고 보니 "
        "관리자 입력이라고 신뢰한 전제 자체가 약했다는 걸 인정합니다 — DOMPurify를 "
        "렌더링 직전에 추가하는 걸 이번 주에 바로 적용하겠습니다.",
    # --- onSnapshot 반복 (질문 대상) ---
    ("study_match", "repeated-pattern:onSnapshot", 1):
        "각 화면마다 필요해서 그때그때 짰습니다.",
    ("study_match", "repeated-pattern:onSnapshot", 3):
        "비슷한 코드가 여러 군데 있다는 건 알고 있었어요. 공용 훅으로 뽑을 수 있을 것 "
        "같긴 한데 아직 안 해봤습니다.",
    ("study_match", "repeated-pattern:onSnapshot", 5):
        "네 화면 모두 컬렉션 구독 로직(구독 시작·언마운트 시 해제·에러 핸들링)이 거의 "
        "동일해서, 사실 useCollectionSubscription(path) 같은 공용 훅으로 뽑는 게 맞습니다. "
        "지금처럼 각자 구현해둔 건 초기에 화면을 빠르게 늘리느라 생긴 기술 부채이고, "
        "트레이드오프는 '지금 당장의 속도' 대 '나중의 중복 유지보수 비용'이었습니다. "
        "다시 생각해보니 이미 네 곳이나 반복됐다는 건 부채가 이미 실현된 것이므로, "
        "더 미루지 않고 지금 훅으로 추출해야 한다고 봅니다 — 다음 PR에서 정리하겠습니다.",
    # --- useBooksQueries.ts diffusion (질문 대상, idiom-filtered) ---
    ("lms", "architecture-diffusion:useBooksQueries.ts", 1):
        "다들 이렇게 쓰길래 저도 그렇게 했어요.",
    ("lms", "architecture-diffusion:useBooksQueries.ts", 3):
        "React Query 쓸 때 이런 식으로 리소스별 훅을 만드는 게 흔한 패턴이라고 알고 "
        "있어요. 저희 팀이 의도적으로 정한 컨벤션인지는 확실하지 않습니다.",
    ("lms", "architecture-diffusion:useBooksQueries.ts", 5):
        "useBooksQueries.ts는 @tanstack/react-query 공식 문서가 권장하는 '리소스당 "
        "커스텀 훅' 패턴을 그대로 따른 겁니다 — 캐시 키 관리와 낙관적 업데이트를 훅 "
        "내부에 캡슐화해서 컴포넌트들이 쿼리 세부사항을 몰라도 되게 하려는 의도였습니다. "
        "대안으로는 Context API로 전역 상태를 만드는 방법도 있었지만, 서버 상태(fetch "
        "결과)를 클라이언트 상태처럼 다루면 캐시 무효화 타이밍이 꼬이는 문제가 있어서 "
        "제외했습니다. 다만 이게 프레임워크 관용 패턴에 가깝다는 지적은 맞고, 저희 팀만의 "
        "특수한 설계 판단이라기보다는 라이브러리 컨벤션을 그대로 채택한 것에 가깝다는 걸 "
        "인정합니다.",
}


def build_testset() -> list:
    cases = []
    findings_by_key = {}
    for fixture_name, path in FIXTURES.items():
        with open(os.path.join(REPO, path), encoding="utf-8") as f:
            data = json.load(f)
        for finding in data["findings"]:
            findings_by_key[(fixture_name, finding["id"])] = finding

    for (fixture_name, finding_id, target_level), answer in ANSWERS.items():
        finding = findings_by_key[(fixture_name, finding_id)]
        question = QUESTIONS[(fixture_name, finding_id)]
        cases.append({
            "id": f"{fixture_name}:{finding_id}:L{target_level}",
            "fixture": fixture_name,
            "finding": finding,
            "question": question,
            "answer": answer,
            "target_level": target_level,
        })
    return cases


def main():
    print(json.dumps(build_testset(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
