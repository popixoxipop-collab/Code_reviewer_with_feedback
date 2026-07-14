/**
 * 산정된 금리(RateGrade)로 월 이자를 계산해 출력하는 클래스.
 *
 * <p>LoanApplication과 RateGrade 두 DTO를 통째로 받는 이유: 이 클래스가 실제로
 * 쓰는 값이 applicantName·loanAmount·creditScore(LoanApplication)와 gradeLabel·
 * annualRatePercent(RateGrade) 5개라서, InterestRateEvaluator처럼 primitive
 * 하나로 좁힐 수 없다. 이 5개를 그대로 늘어놓은 파라미터 목록(String, long, int,
 * String, double)을 쓰면 호출부에서 인자 순서를 착각하기 쉽고(특히 String이 두
 * 개라 컴파일러가 순서 실수를 잡아주지 못한다), 어차피 LoanApplication과
 * RateGrade는 각각 이미 의미 있는 단위로 묶여 있는 객체이므로 그대로 전달하는
 * 편이 더 안전하고 읽기도 쉽다.
 *
 * <p>월 이자 계산: loanAmount(long, 원) * annualRatePercent(double, %) / 100 / 12.
 * 이 계산은 double 중간값을 거치지만, 화면에 출력하기 직전 calculateMonthlyInterest()
 * 안에서 Math.round로 즉시 long(원 단위)으로 되돌린다. double을 오래 들고 있지
 * 않고 "계산 후 즉시 반올림" 패턴을 쓰는 이유는, 이 값이 RepaymentSchedule처럼
 * 반복적으로 누적 재사용되지 않고 이 리포트 안에서 한 번 계산되어 출력되고 끝나기
 * 때문이다 — 누적 오차를 걱정할 필요가 없는 위치라 double 사용이 안전하다.
 *
 * <p>fan_in=1 기록: 현재 Main에서만 호출된다. 출력 채널(콘솔 System.out)이
 * 나중에 바뀌는 경우(예: 파일 저장, 웹 응답)를 대비해 인터페이스로 미리 뽑아두는
 * 것도 고려했지만, 호출자가 하나뿐인 지금 시점에는 실제 요구가 없는 확장이라
 * 판단해 보류했다.
 */
public class InterestReport {

    public void printReport(LoanApplication loan, RateGrade rateGrade) {
        long monthlyInterest = calculateMonthlyInterest(loan.getLoanAmount(), rateGrade.getAnnualRatePercent());

        System.out.println("===== 금리 산정 리포트 =====");
        System.out.println("신청자명    : " + loan.getApplicantName());
        System.out.println("대출금액    : " + loan.getLoanAmount() + "원");
        System.out.println("신용점수    : " + loan.getCreditScore() + "점");
        System.out.println("산정등급    : " + rateGrade.getGradeLabel());
        System.out.println("적용 연이율  : " + rateGrade.getAnnualRatePercent() + "%");
        System.out.println("월 이자(1개월차 기준) : " + monthlyInterest + "원");
        System.out.println("============================");
    }

    private long calculateMonthlyInterest(long loanAmount, double annualRatePercent) {
        double monthlyInterest = loanAmount * (annualRatePercent / 100.0) / 12.0;
        return Math.round(monthlyInterest);
    }
}
