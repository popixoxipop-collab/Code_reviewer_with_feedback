/**
 * RepaymentInputHandler가 Scanner로 입력받은 결과(상환방식 + 상환기간)를 담는
 * 불변 DTO.
 *
 * <p>RepaymentType 하나만 반환하지 않고 termMonths까지 묶어서 반환하는 이유:
 * RepaymentSchedule은 상환방식과 상환기간을 항상 함께 알아야 스케줄을 계산할 수
 * 있다(예: 원금균등상환은 loanAmount/termMonths가 있어야 회차별 원금이 나온다).
 * 두 값을 각각 별도 파라미터로 Main → RepaymentSchedule까지 릴레이하는 대신
 * 하나의 DTO로 묶으면, 호출부에서 매개변수 순서를 착각해 엉뚱한 int 값(예:
 * creditScore와 termMonths)을 바꿔 넘기는 실수를 구조적으로 줄일 수 있다.
 */
public class RepaymentInput {

    private final RepaymentType repaymentType;
    private final int termMonths;

    public RepaymentInput(RepaymentType repaymentType, int termMonths) {
        this.repaymentType = repaymentType;
        this.termMonths = termMonths;
    }

    public RepaymentType getRepaymentType() {
        return repaymentType;
    }

    public int getTermMonths() {
        return termMonths;
    }
}
