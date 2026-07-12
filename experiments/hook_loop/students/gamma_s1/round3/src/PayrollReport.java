import java.util.List;

/**
 * 급여 계산 결과를 콘솔에 보기 좋게 출력한다.
 * 출력과 동시에 PayslipArchive에 기록을 남긴다(fan-in=1: 이 클래스만
 * PayslipArchive를 직접 사용한다).
 */
public class PayrollReport {

    private final PayslipArchive archive;

    public PayrollReport() {
        this.archive = new PayslipArchive();
    }

    public void printPayslip(Employee employee, double grossPay, double tax, double netPay) {
        archive.addRecord(employee.getName(), employee.getHoursWorked(), grossPay, tax, netPay);

        System.out.println("============================================");
        System.out.println("                 급여 명세서");
        System.out.println("============================================");
        System.out.printf("이름       : %s%n", employee.getName());
        System.out.printf("근무 시간  : %.1f 시간%n", employee.getHoursWorked());
        System.out.printf("총 급여    : %,.2f 원%n", grossPay);
        System.out.printf("공제 세금  : %,.2f 원%n", tax);
        System.out.printf("실수령액   : %,.2f 원%n", netPay);
        System.out.println("============================================");
        System.out.printf("현재까지 저장된 급여명세서 수: %d건%n%n", archive.size());
    }

    /** 이번 실행 동안 저장된 급여명세서 전체 이력을 요약해서 출력한다. */
    public void printAllRecords() {
        List<PayslipArchive.PayslipRecord> allRecords = archive.getAllRecords();

        if (allRecords.isEmpty()) {
            System.out.println("저장된 급여명세서가 없습니다.");
            return;
        }

        System.out.println("============================================");
        System.out.println("           이번 실행 급여명세서 전체 이력");
        System.out.println("============================================");

        double totalNetPay = 0;
        int index = 1;
        for (PayslipArchive.PayslipRecord record : allRecords) {
            System.out.printf("%d. %-8s | 근무 %5.1f시간 | 실수령액 %,12.2f원%n",
                    index++, record.getName(), record.getHoursWorked(), record.getNetPay());
            totalNetPay += record.getNetPay();
        }

        System.out.println("--------------------------------------------");
        System.out.printf("총 %d건 | 실수령액 합계 %,.2f원%n", allRecords.size(), totalNetPay);
        System.out.println("============================================");
    }
}
