import java.util.Scanner;

/**
 * 프로그램 진입점. Scanner로 직원 이름/근무 시간/시급을 입력받아
 * 급여를 계산하고 명세서를 출력한다. 여러 명을 연속으로 입력할 수 있다.
 */
public class Main {

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        PayrollCalculator calculator = new PayrollCalculator();
        PayrollReport report = new PayrollReport();

        boolean continueInput = true;
        while (continueInput) {
            String name = readName(scanner);
            double hoursWorked = readNonNegativeDouble(scanner, "이번 주 근무 시간을 입력하세요: ");
            double hourlyRate = readNonNegativeDouble(scanner, "시급을 입력하세요: ");

            Employee employee = new Employee(name, hoursWorked, hourlyRate);

            double grossPay = calculator.calculateGrossPay(employee);
            double tax = calculator.calculateTax(grossPay);
            double netPay = calculator.calculateNetPay(grossPay, tax);

            report.printPayslip(employee, grossPay, tax, netPay);

            System.out.print("다른 직원의 급여도 계산하시겠습니까? (y/n): ");
            String answer = scanner.nextLine().trim();
            continueInput = "y".equalsIgnoreCase(answer);
        }

        report.printAllRecords();
        System.out.println("프로그램을 종료합니다.");
        scanner.close();
    }

    private static String readName(Scanner scanner) {
        while (true) {
            System.out.print("직원 이름을 입력하세요: ");
            String name = scanner.nextLine().trim();
            if (!name.isEmpty()) {
                return name;
            }
            System.out.println("이름은 비어 있을 수 없습니다. 다시 입력해주세요.");
        }
    }

    private static double readNonNegativeDouble(Scanner scanner, String prompt) {
        System.out.print(prompt);
        while (true) {
            String input = scanner.nextLine().trim();
            try {
                double value = Double.parseDouble(input);
                if (value < 0) {
                    System.out.print("음수는 입력할 수 없습니다. 다시 입력해주세요: ");
                    continue;
                }
                return value;
            } catch (NumberFormatException e) {
                System.out.print("숫자로 입력해주세요. 다시 입력해주세요: ");
            }
        }
    }
}
