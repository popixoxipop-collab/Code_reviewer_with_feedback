/**
 * 대출 신청자 1명의 정보를 담는 불변(immutable) 모델 클래스.
 *
 * <p>설계 의도: 신청자명 / 신용점수 / 대출금액 3개 필드는 생성자에서 한 번만 검증한다.
 * InterestRateEvaluator, InterestReport, RepaymentSchedule 등 이 객체를 소비하는
 * 모든 클래스는 "이미 유효한 값"이라는 불변식(invariant)을 신뢰하고 별도의 null/범위
 * 재검증 없이 바로 사용할 수 있다. 검증 로직을 한 곳(생성자)에 모아두지 않으면
 * 소비자마다 같은 null/범위 체크를 중복 작성하게 되고, 그중 한 곳이라도 빠뜨리면
 * NullPointerException이나 잘못된 금리 산정으로 이어진다 — "fail fast를 생성 시점
 * 하나로 모은다"는 것이 이 클래스의 핵심 설계 의도다.
 *
 * <p>공유 범위(fan-in 기록): 이 클래스는 InterestRateEvaluator(creditScore만 사용),
 * InterestReport(applicantName·loanAmount 사용), RepaymentSchedule(loanAmount 사용)
 * 총 3곳 이상에서 소비되는 공유 컴포넌트다. 필드를 추가/삭제하면 이 3개 클래스의
 * getter 호출부를 모두 확인해야 한다. 다만 각 소비자는 필요한 필드만 골라 쓰고
 * (InterestRateEvaluator는 creditScore 하나만 primitive로 전달받음) 이 객체를
 * 통째로 넘기지 않기 때문에, LoanApplication의 내부 구현 변경이 InterestRateEvaluator의
 * 메서드 시그니처까지 전파되지는 않는다 — getter 인터페이스로 의존을 격리한 결과다.
 */
public class LoanApplication {

    private final String applicantName;
    private final int creditScore;
    private final long loanAmount;

    /**
     * @param applicantName 신청자명. null/공백 문자열은 허용하지 않는다. InterestReport가
     *                      보고서 헤더에 이름을 그대로 출력하는데, null이 여기까지 흘러오면
     *                      문자열 결합 시 "null"이라는 글자가 그대로 출력되어 오류를 오히려
     *                      숨기게 된다. 그래서 여기서 즉시 IllegalArgumentException으로
     *                      막아 호출부(Main)에서 바로 원인을 알 수 있게 한다.
     * @param creditScore   신용점수. 국내 개인신용평점(NICE/KCB, 1~1000점, 높을수록 우량)
     *                      체계를 기준으로 1~1000 범위만 허용한다. 범위를 벗어난 값이
     *                      들어오면 InterestRateEvaluator의 if/else if 등급 분기 중
     *                      어디에도 안전하게 걸리지 않을 수 있으므로 여기서 미리 차단한다.
     * @param loanAmount    대출금액(원 단위). double 대신 long을 선택한 이유:
     *                      - double(이진 부동소수점)은 소수 자리 오차가 누적되는 자료형이라,
     *                        RepaymentSchedule처럼 같은 값을 반복해서 가감산하는 루프에
     *                        쓰이면 마지막 회차 잔액이 정확히 0으로 떨어지지 않는 문제가
     *                        생긴다 — 화폐 계산에는 근본적으로 부적합하다.
     *                      - BigDecimal은 정밀도 면에서 가장 안전하지만 scale/RoundingMode를
     *                        매번 명시해야 해서, "빠르게 동작하는 버전부터" 만든다는 이번
     *                        과제 범위에는 과한 복잡도라고 판단했다.
     *                      - long은 원 단위 정수를 오차 없이 표현하고, 실제 대출금액이
     *                        long의 최댓값(약 9.22×10^18원)에 근접할 일은 현실적으로
     *                        없어 오버플로우 위험은 사실상 0에 가깝다. 다만 금리 계산의
     *                        중간값(월이자 등)은 double로 잠깐 계산한 뒤 화면에 쓰기 직전
     *                        Math.round로 즉시 long에 반올림해 되돌리는 방식을
     *                        InterestReport와 RepaymentSchedule 양쪽에서 동일하게 적용해,
     *                        오차가 자료형 경계를 넘어 누적되지 않도록 했다.
     */
    public LoanApplication(String applicantName, int creditScore, long loanAmount) {
        if (applicantName == null || applicantName.trim().isEmpty()) {
            throw new IllegalArgumentException("신청자명은 비어 있을 수 없습니다.");
        }
        if (creditScore < 1 || creditScore > 1000) {
            throw new IllegalArgumentException("신용점수는 1~1000 사이여야 합니다. 입력값=" + creditScore);
        }
        if (loanAmount <= 0) {
            throw new IllegalArgumentException("대출금액은 0보다 커야 합니다. 입력값=" + loanAmount);
        }
        this.applicantName = applicantName;
        this.creditScore = creditScore;
        this.loanAmount = loanAmount;
    }

    public String getApplicantName() {
        return applicantName;
    }

    public int getCreditScore() {
        return creditScore;
    }

    public long getLoanAmount() {
        return loanAmount;
    }

    @Override
    public String toString() {
        return "LoanApplication{applicantName='" + applicantName + "', creditScore=" + creditScore
                + ", loanAmount=" + loanAmount + '}';
    }
}
