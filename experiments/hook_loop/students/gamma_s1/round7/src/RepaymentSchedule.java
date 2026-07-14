import java.util.ArrayList;
import java.util.List;

/**
 * 입력받은 상환 방식(RepaymentType)에 따라 상환 일정표를 생성/출력하는 클래스.
 *
 * <p>ScheduleRow를 별도 top-level 파일로 빼지 않고 이 클래스 안에 private static
 * nested class로 둔 이유: RateGrade/RepaymentType과 달리 ScheduleRow는 이 클래스
 * 밖으로 절대 나가지 않는다(Main도 List&lt;ScheduleRow&gt;를 직접 받지 않고, 출력까지
 * 이 클래스 안에서 끝낸다). 즉 fan_in=1이면서 "클래스 경계를 아예 넘지 않는" 순수한
 * 내부 구현 세부사항이라, 굳이 public 최상위 타입으로 승격해 캡슐화를 풀 이유가
 * 없다. RateGrade/RepaymentType은 여러 클래스가 소비하기 때문에 top-level public
 * 으로 뽑았던 것과 의도적으로 대비되는 선택이다.
 *
 * <p>회차 리스트 자료구조로 ArrayList&lt;ScheduleRow&gt;를 선택한 이유(대안 비교):
 * - double[][] 같은 2차원 배열: 회차/원금/이자/잔액을 열 인덱스(0,1,2,3)로 구분해야
 *   해서, row[2]가 이자인지 잔액인지 코드만 봐서는 알 수 없다. 필드에 이름이
 *   없다는 게 근본 문제라 이번 설계에서는 배제했다.
 * - LinkedList&lt;ScheduleRow&gt;: 이 클래스는 처음부터 끝까지 순서대로 한 번만
 *   add()로 채우고, 그 다음 순서대로 한 번만 순회해서 출력한다 — 중간 삽입·삭제가
 *   전혀 없다(실제로 generateRows()/buildXxx() 어디에도 리스트 중간 삽입 호출은
 *   없다). LinkedList가 유리해지는 "중간 삽입" 패턴이 코드에 없으므로, 그 이점을
 *   못 쓰면서 노드마다 앞뒤 포인터 오버헤드만 더 지불하는 셈이 되어 ArrayList보다
 *   못한 선택이다.
 * - ArrayList&lt;ScheduleRow&gt;(선택): 끝에 추가하는 add()가 상각(amortized)
 *   O(1)이고, termMonths가 최대 480(40년) 규모라 자동 확장 비용도 무시할 만하며,
 *   연속 메모리 배치 덕분에 마지막에 순회하며 출력할 때도 캐시 지역성이 LinkedList
 *   보다 유리하다.
 *
 * <p>공유 의존: LoanApplication(loanAmount), RateGrade(annualRatePercent),
 * RepaymentInput(repaymentType, termMonths) 3개의 DTO를 파라미터로 받는다. 이
 * DTO들의 필드를 직접 꺼내 쓰지 않고 getter로만 값을 읽으므로, 각 DTO의 내부
 * 구현(필드 저장 방식)이 바뀌어도 getter 시그니처만 유지되면 이 클래스는 영향을
 * 받지 않는다 — getter라는 인터페이스를 통해 의존성을 격리한 것이다.
 */
public class RepaymentSchedule {

    public void printSchedule(LoanApplication loan, RateGrade rateGrade, RepaymentInput repaymentInput) {
        List<ScheduleRow> rows = generateRows(
                loan.getLoanAmount(),
                rateGrade.getAnnualRatePercent(),
                repaymentInput.getRepaymentType(),
                repaymentInput.getTermMonths()
        );

        System.out.println("===== 상환 일정표 (" + repaymentInput.getRepaymentType().getDisplayName() + ") =====");
        System.out.printf("%-6s %15s %15s %15s%n", "회차", "납입원금", "납입이자", "잔액");
        for (ScheduleRow row : rows) {
            System.out.printf("%-6d %,15d %,15d %,15d%n",
                    row.round, row.principalPayment, row.interestPayment, row.remainingBalance);
        }
        System.out.println("==========================================");
    }

    private List<ScheduleRow> generateRows(long loanAmount, double annualRatePercent,
                                            RepaymentType type, int termMonths) {
        switch (type) {
            case EQUAL_PRINCIPAL_INTEREST:
                return buildEqualPrincipalInterest(loanAmount, annualRatePercent, termMonths);
            case EQUAL_PRINCIPAL:
                return buildEqualPrincipal(loanAmount, annualRatePercent, termMonths);
            case BULLET:
                return buildBullet(loanAmount, annualRatePercent, termMonths);
            default:
                // RepaymentType은 enum이라 현재 3개 case가 전부다. default는
                // 컴파일러가 강제하지는 않지만, 향후 enum 상수가 추가됐는데
                // switch에 case를 안 넣고 넘어가는 실수를 조용히 넘기지 않고
                // 즉시 예외로 드러내기 위한 방어 코드다.
                throw new IllegalStateException("처리되지 않은 상환방식: " + type);
        }
    }

    private List<ScheduleRow> buildEqualPrincipalInterest(long loanAmount, double annualRatePercent, int termMonths) {
        List<ScheduleRow> rows = new ArrayList<>(termMonths);
        double monthlyRate = annualRatePercent / 100.0 / 12.0;

        long monthlyPayment;
        if (monthlyRate == 0.0) {
            // monthlyRate가 0이 되면 아래 일반 공식(factor/(factor-1))이 0으로
            // 나누기가 되어 NaN/Infinity를 만든다. 현재 InterestRateEvaluator가
            // 만드는 금리표에는 0%가 없어(최저 19.9%) 정상 흐름에서는 이
            // 분기에 도달하지 않지만, 향후 "0% 프로모션 금리" 등급이 추가되는
            // 경우에 대비해 원금을 개월 수로 균등 분할하는 안전한 대안을
            // 남겨둔다.
            monthlyPayment = Math.round((double) loanAmount / termMonths);
        } else {
            double factor = Math.pow(1 + monthlyRate, termMonths);
            monthlyPayment = Math.round(loanAmount * monthlyRate * factor / (factor - 1));
        }

        long remainingBalance = loanAmount;
        for (int month = 1; month <= termMonths; month++) {
            long interestPayment = Math.round(remainingBalance * monthlyRate);
            long principalPayment;
            if (month == termMonths) {
                // 반올림이 매 회차 누적되면 마지막 회차에 잔액이 정확히
                // 0원으로 떨어지지 않고 몇 원이 남거나 모자랄 수 있다. 그래서
                // 마지막 회차의 원금은 공식으로 계산하지 않고 "남은 잔액
                // 전체"로 강제해 최종 잔액이 정확히 0이 되도록 보정한다.
                principalPayment = remainingBalance;
            } else {
                principalPayment = monthlyPayment - interestPayment;
            }
            remainingBalance -= principalPayment;
            rows.add(new ScheduleRow(month, principalPayment, interestPayment, remainingBalance));
        }
        return rows;
    }

    private List<ScheduleRow> buildEqualPrincipal(long loanAmount, double annualRatePercent, int termMonths) {
        List<ScheduleRow> rows = new ArrayList<>(termMonths);
        double monthlyRate = annualRatePercent / 100.0 / 12.0;

        // 정수 나눗셈: 몫만 취하고 나머지(최대 termMonths-1원)는 버려진다.
        long baseMonthlyPrincipal = loanAmount / termMonths;
        long remainingBalance = loanAmount;

        for (int month = 1; month <= termMonths; month++) {
            long interestPayment = Math.round(remainingBalance * monthlyRate);
            long principalPayment;
            if (month == termMonths) {
                // loanAmount / termMonths 정수 나눗셈에서 버려진 나머지를
                // 마지막 회차에 몰아줘서, 전체 회차 원금 합계가 loanAmount와
                // 정확히 일치하도록 만든다. 그렇지 않으면 나머지만큼 대출금이
                // "증발"한 것처럼 계산이 안 맞게 된다.
                principalPayment = remainingBalance;
            } else {
                principalPayment = baseMonthlyPrincipal;
            }
            remainingBalance -= principalPayment;
            rows.add(new ScheduleRow(month, principalPayment, interestPayment, remainingBalance));
        }
        return rows;
    }

    private List<ScheduleRow> buildBullet(long loanAmount, double annualRatePercent, int termMonths) {
        List<ScheduleRow> rows = new ArrayList<>(termMonths);
        double monthlyRate = annualRatePercent / 100.0 / 12.0;
        long interestPayment = Math.round(loanAmount * monthlyRate);

        for (int month = 1; month <= termMonths; month++) {
            if (month < termMonths) {
                // 만기 전에는 잔액이 원금 그대로 유지되므로 매달 이자만 낸다.
                rows.add(new ScheduleRow(month, 0L, interestPayment, loanAmount));
            } else {
                // 마지막 회차에 원금 전액을 일시 상환한다.
                rows.add(new ScheduleRow(month, loanAmount, interestPayment, 0L));
            }
        }
        return rows;
    }

    /**
     * 상환 일정표 한 행. RepaymentSchedule 밖으로 절대 노출되지 않는 내부
     * 표현이라 private static nested class로 캡슐화했다(fan_in=1, 클래스
     * 경계 안쪽으로 완전히 한정된 타입).
     */
    private static class ScheduleRow {
        final int round;
        final long principalPayment;
        final long interestPayment;
        final long remainingBalance;

        ScheduleRow(int round, long principalPayment, long interestPayment, long remainingBalance) {
            this.round = round;
            this.principalPayment = principalPayment;
            this.interestPayment = interestPayment;
            this.remainingBalance = remainingBalance;
        }
    }
}
