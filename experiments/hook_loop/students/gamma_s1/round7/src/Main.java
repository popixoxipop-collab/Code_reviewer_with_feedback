import java.util.Scanner;

/**
 * 프로그램 진입점. 신청자 정보 입력 → 금리 등급 판정 → 상환 방식 입력 →
 * 월 이자 리포트 출력 → 상환 일정표 출력 순서로 각 클래스를 호출해 연결한다.
 *
 * <p>클래스 간 결합 방식 요약("빠르게 동작하는 버전부터" 만든다는 전제 아래,
 * 통합 지점은 최소화하면서도 다음 원칙은 지키려 했다):
 * - LoanApplication: 입력 검증을 전담하는 불변 모델. 여기서 한 번 걸러지면
 *   이후 어떤 클래스도 null/범위 재검증을 하지 않는다.
 * - InterestRateEvaluator: LoanApplication 전체가 아니라 creditScore
 *   하나만 받는 좁은 의존(필요한 값 하나만 전달).
 * - RepaymentInputHandler: 콘솔 입출력(Scanner)을 전담. 계산 로직 클래스들
 *   (InterestReport, RepaymentSchedule)은 I/O를 전혀 모른다.
 * - InterestReport / RepaymentSchedule: 여러 필드가 동시에 필요할 때는 DTO
 *   (LoanApplication, RateGrade, RepaymentInput)를 통째로 받아 파라미터
 *   목록이 폭발하지 않게 했다.
 *
 * <p>Scanner는 이 메서드에서 딱 한 번만 생성해서 신청자 정보 입력에 직접 쓰고,
 * 그 다음 같은 인스턴스를 RepaymentInputHandler에 주입한다. 여러 Scanner를
 * 만들지 않는 이유와 nextLine()으로 입력 방식을 통일한 이유는
 * RepaymentInputHandler의 클래스 주석에 정리했다 — 이 프로그램 안에서 Scanner는
 * Main과 RepaymentInputHandler 두 곳이 함께 쓰는 공유 자원이므로, 그 사실을
 * 여기서도 다시 기록해둔다.
 */
public class Main {

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        LoanApplication loan = readLoanApplication(scanner);

        InterestRateEvaluator evaluator = new InterestRateEvaluator();
        RateGrade rateGrade = evaluator.evaluate(loan.getCreditScore());

        InterestReport report = new InterestReport();
        report.printReport(loan, rateGrade);

        RepaymentInputHandler inputHandler = new RepaymentInputHandler(scanner);
        RepaymentInput repaymentInput = inputHandler.readRepaymentInput();

        RepaymentSchedule schedule = new RepaymentSchedule();
        schedule.printSchedule(loan, rateGrade, repaymentInput);
    }

    private static LoanApplication readLoanApplication(Scanner scanner) {
        System.out.print("신청자명: ");
        String name = scanner.nextLine().trim();

        int creditScore = readIntInRange(scanner, "신용점수(1~1000): ", 1, 1000);
        long loanAmount = readPositiveLong(scanner, "대출금액(원): ");

        // LoanApplication 생성자가 name/creditScore/loanAmount를 다시 검증한다.
        // 여기서 이미 범위를 걸러 받았지만, 생성자 쪽 검증을 "여기서 걸렀으니
        // 안 해도 된다"고 생략하지 않았다 — LoanApplication이 이 메서드를 거치지
        // 않는 다른 경로(예: 테스트 코드)로도 생성될 수 있으므로, 모델 스스로
        // 불변식을 지키게 하는 편이 더 안전하다는 판단이다.
        return new LoanApplication(name, creditScore, loanAmount);
    }

    private static int readIntInRange(Scanner scanner, String prompt, int min, int max) {
        while (true) {
            System.out.print(prompt);
            String line = scanner.nextLine().trim();
            try {
                int value = Integer.parseInt(line);
                if (value < min || value > max) {
                    System.out.println("[오류] " + min + "~" + max + " 사이의 값을 입력하세요.");
                    continue;
                }
                return value;
            } catch (NumberFormatException e) {
                System.out.println("[오류] 숫자만 입력하세요.");
            }
        }
    }

    private static long readPositiveLong(Scanner scanner, String prompt) {
        while (true) {
            System.out.print(prompt);
            String line = scanner.nextLine().trim();
            try {
                long value = Long.parseLong(line);
                if (value <= 0) {
                    System.out.println("[오류] 0보다 큰 값을 입력하세요.");
                    continue;
                }
                return value;
            } catch (NumberFormatException e) {
                System.out.println("[오류] 숫자만 입력하세요.");
            }
        }
    }
}
