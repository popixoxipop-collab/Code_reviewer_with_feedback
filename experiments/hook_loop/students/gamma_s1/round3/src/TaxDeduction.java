/**
 * 급여에서 공제할 세금을 계산한다.
 *
 * 세율은 과제 요구사항에 따라 임의로 10%(고정)를 사용한다. 실제 소득세처럼
 * 누진 구간이 있는 세금 체계는 아니며, 단순 비례 공제로 구현했다.
 * PayrollCalculator가 이 클래스를 사용한다(fan-in=1).
 */
public class TaxDeduction {

    private static final double TAX_RATE = 0.10; // 10% 고정 세율

    public double calculateTax(double grossPay) {
        return grossPay * TAX_RATE;
    }
}
