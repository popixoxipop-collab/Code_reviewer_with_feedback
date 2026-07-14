/**
 * InterestRateEvaluator가 산정한 "금리 등급 + 연이율" 쌍을 담는 불변 DTO.
 *
 * <p>공유 범위(fan-in 기록): InterestRateEvaluator가 생성하고, InterestReport와
 * RepaymentSchedule 두 곳이 소비하며, Main이 그 사이를 중개한다 — 총 3곳 이상에서
 * 참조되는 공유 컴포넌트다. 등급명(gradeLabel)과 연이율(annualRatePercent)을 각각
 * 별도 메서드로 나눠(getGrade(), getRate()처럼) 두 번 호출하게 하지 않고 하나의
 * 불변 객체로 묶은 이유: 두 값은 항상 같은 판정 시점에 함께 결정되는 한 쌍이다.
 * 만약 두 값을 따로 조회하게 만들면, 그 사이에 신용점수가 다시 평가되는 경로가
 * 코드에 추가될 때 "같은 판정에서 나온 값"이라는 보장이 타입만 봐서는 드러나지
 * 않는다. 하나의 객체로 묶으면 InterestReport와 RepaymentSchedule은 항상 서로
 * 짝이 맞는 등급/이율 값만 받는다는 것이 구조적으로 보장된다.
 *
 * <p>변경 영향 범위: gradeLabel/annualRatePercent 필드명이나 타입을 바꾸면
 * InterestReport.printReport()와 RepaymentSchedule의 월별 이자 계산 로직 양쪽을
 * 함께 확인해야 한다.
 */
public class RateGrade {

    private final String gradeLabel;
    private final double annualRatePercent;

    public RateGrade(String gradeLabel, double annualRatePercent) {
        this.gradeLabel = gradeLabel;
        this.annualRatePercent = annualRatePercent;
    }

    public String getGradeLabel() {
        return gradeLabel;
    }

    public double getAnnualRatePercent() {
        return annualRatePercent;
    }

    @Override
    public String toString() {
        return gradeLabel + " (연 " + annualRatePercent + "%)";
    }
}
