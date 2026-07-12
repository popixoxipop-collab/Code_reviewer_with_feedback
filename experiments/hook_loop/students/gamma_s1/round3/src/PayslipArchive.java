import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 이번 실행에서 계산된 급여명세서 기록을 저장하고 관리한다.
 * PayrollReport가 이 클래스를 사용한다(fan-in=1).
 *
 * 설계 메모: Employee 객체를 그대로 저장하지 않고, 계산이 끝난 숫자 값만
 * 받아 내부 레코드(PayslipRecord)로 저장한다. 저장 형식을 문자열로 합쳐서
 * 저장하는 대안도 있었지만, 그러면 나중에 합계 같은 집계 계산을 할 때
 * 문자열을 다시 파싱해야 해서 숫자 필드를 그대로 들고 있는 구조화된
 * 레코드를 선택했다(실제로 PayrollReport.printAllRecords()가 이 필드들로
 * 실수령액 합계를 계산한다).
 */
public class PayslipArchive {

    private final List<PayslipRecord> records = new ArrayList<>();

    public void addRecord(String name, double hoursWorked, double grossPay, double tax, double netPay) {
        records.add(new PayslipRecord(name, hoursWorked, grossPay, tax, netPay));
    }

    public List<PayslipRecord> getAllRecords() {
        return Collections.unmodifiableList(records);
    }

    public int size() {
        return records.size();
    }

    /** 급여명세서 한 건(이름/근무시간/총급여/세금/실수령액)을 표현하는 내부 레코드. */
    public static class PayslipRecord {
        private final String name;
        private final double hoursWorked;
        private final double grossPay;
        private final double tax;
        private final double netPay;

        public PayslipRecord(String name, double hoursWorked, double grossPay, double tax, double netPay) {
            this.name = name;
            this.hoursWorked = hoursWorked;
            this.grossPay = grossPay;
            this.tax = tax;
            this.netPay = netPay;
        }

        public String getName() {
            return name;
        }

        public double getHoursWorked() {
            return hoursWorked;
        }

        public double getGrossPay() {
            return grossPay;
        }

        public double getTax() {
            return tax;
        }

        public double getNetPay() {
            return netPay;
        }
    }
}
