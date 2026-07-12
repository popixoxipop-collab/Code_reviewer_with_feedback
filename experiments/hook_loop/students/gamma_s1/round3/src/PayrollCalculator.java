/**
 * 근무 시간과 시급으로 급여를 계산하는 로직을 담당한다.
 *
 * 주 40시간을 초과하는 근무 시간에는 1.5배 시급(초과근무수당)을 적용한다.
 * 세금 공제는 TaxDeduction에 위임한다(fan-in=1: 이 클래스만 TaxDeduction을
 * 직접 사용한다).
 *
 * 설계 메모: TaxDeduction을 생성자 주입(DI)이 아니라 내부에서 직접
 * 생성하는 방식을 택했다. DI가 테스트하기엔 더 유리하지만(다른 세율
 * 구현체로 교체하며 테스트 가능), 이번 과제는 TaxDeduction 구현체가
 * 하나뿐이고 교체될 일이 없어 내부 생성이 더 간단하다고 판단했다.
 */
public class PayrollCalculator {

    private static final double REGULAR_HOURS_LIMIT = 40.0; // 주 40시간 기준
    private static final double OVERTIME_MULTIPLIER = 1.5;

    private final TaxDeduction taxDeduction;

    public PayrollCalculator() {
        this.taxDeduction = new TaxDeduction();
    }

    /**
     * 주 40시간까지는 정상 시급, 초과분은 1.5배 시급을 적용해 총급여를 계산한다.
     */
    public double calculateGrossPay(Employee employee) {
        double hoursWorked = employee.getHoursWorked();
        double hourlyRate = employee.getHourlyRate();

        double grossPay;
        if (hoursWorked > REGULAR_HOURS_LIMIT) {
            double regularPay = REGULAR_HOURS_LIMIT * hourlyRate;
            double overtimeHours = hoursWorked - REGULAR_HOURS_LIMIT;
            double overtimePay = overtimeHours * hourlyRate * OVERTIME_MULTIPLIER;
            grossPay = regularPay + overtimePay;
        } else {
            grossPay = hoursWorked * hourlyRate;
        }
        return grossPay;
    }

    public double calculateTax(double grossPay) {
        return taxDeduction.calculateTax(grossPay);
    }

    public double calculateNetPay(double grossPay, double tax) {
        return grossPay - tax;
    }
}
