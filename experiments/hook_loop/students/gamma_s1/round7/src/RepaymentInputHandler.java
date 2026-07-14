import java.util.Scanner;

/**
 * 상환 방식(원리금균등/원금균등/만기일시상환)과 상환기간(개월)을 Scanner로
 * 입력받는 클래스.
 *
 * <p>Scanner 공유 설계: 이 클래스는 자체적으로 new Scanner(System.in)을 만들지
 * 않고, 생성자에서 Main이 만든 Scanner 인스턴스를 주입받는다. System.in을 감싸는
 * Scanner를 프로그램 안에서 여러 개 만들고 그중 하나라도 close()를 호출하면
 * 내부적으로 System.in 스트림 자체가 닫혀버려서, 그 뒤 다른 Scanner로 읽으려는
 * 모든 입력이 NoSuchElementException으로 깨진다. Main과 이 클래스가 인스턴스
 * 하나를 공유하도록 강제하면 그 문제 자체가 발생할 수 없다. 같은 이유로 이
 * 클래스는 끝까지 scanner.close()를 호출하지 않는다 — Scanner를 닫는 책임은
 * Main에도 없다(System.in은 JVM 종료 시 정리되므로 명시적으로 닫지 않아도 안전).
 *
 * <p>모든 입력을 nextInt()/nextLong() 대신 nextLine() + 파싱(Integer.parseInt 등)으로
 * 통일한 이유: nextInt()는 개행 문자를 버퍼에 남겨두기 때문에 바로 다음에
 * nextLine()을 호출하면 빈 문자열을 받는 유명한 함정이 있다. Main의 신청자 정보
 * 입력과 이 클래스의 상환방식 입력이 같은 Scanner를 공유하므로, 두 곳의 입력
 * 방식이 섞이면 그 함정을 밟기 쉽다. nextLine()으로 통일하면 그런 혼선 자체가
 * 생기지 않는다.
 *
 * <p>fan_in=1 기록: 이 클래스는 현재 Main에서만 생성/호출된다. 콘솔 입출력을
 * 이 클래스 하나에 모아두면 InterestReport/RepaymentSchedule 등 계산 로직
 * 클래스들은 I/O를 전혀 몰라도 되므로(Scanner를 파라미터로도 받지 않음),
 * 나중에 단위 테스트를 붙이기 쉬워진다 — 지금 당장 테스트를 작성하진 않았지만
 * 그 여지를 열어두는 선택이다.
 */
public class RepaymentInputHandler {

    private final Scanner scanner;

    public RepaymentInputHandler(Scanner scanner) {
        this.scanner = scanner;
    }

    public RepaymentInput readRepaymentInput() {
        RepaymentType type = readRepaymentType();
        int termMonths = readTermMonths();
        return new RepaymentInput(type, termMonths);
    }

    private RepaymentType readRepaymentType() {
        while (true) {
            System.out.println("상환 방식을 선택하세요.");
            System.out.println("1. 원리금균등상환");
            System.out.println("2. 원금균등상환");
            System.out.println("3. 만기일시상환");
            System.out.print("선택 (1~3): ");

            String line = scanner.nextLine().trim();
            switch (line) {
                case "1":
                    return RepaymentType.EQUAL_PRINCIPAL_INTEREST;
                case "2":
                    return RepaymentType.EQUAL_PRINCIPAL;
                case "3":
                    return RepaymentType.BULLET;
                default:
                    // 잘못된 입력에 대해 null을 반환하는 대신 즉시 재입력을
                    // 요구한다. 만약 여기서 null을 그대로 리턴하면,
                    // RepaymentSchedule.generateRows()의 switch(type)가
                    // NullPointerException으로 죽는데 그 예외 발생 지점은
                    // 입력 시점과 멀리 떨어져 있어 원인 추적이 어려워진다.
                    // 그래서 잘못된 입력의 영향 범위를 이 메서드 안의 재입력
                    // 루프로 가둔다.
                    System.out.println("[오류] 1, 2, 3 중 하나를 입력하세요.");
            }
        }
    }

    private int readTermMonths() {
        while (true) {
            System.out.print("상환기간(개월, 1~480)을 입력하세요: ");
            String line = scanner.nextLine().trim();
            try {
                int months = Integer.parseInt(line);
                if (months < 1 || months > 480) {
                    System.out.println("[오류] 1~480 사이의 값을 입력하세요.");
                    continue;
                }
                return months;
            } catch (NumberFormatException e) {
                // 숫자가 아닌 입력(공백, 문자 등)이 들어와도 프로그램 전체가
                // 죽지 않고 이 메서드 안에서만 재입력을 요구하도록 잡아준다.
                System.out.println("[오류] 숫자만 입력하세요.");
            }
        }
    }
}
