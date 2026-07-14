import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

/**
 * 프로그램 진입점.
 *
 * 흐름: 대출 정보 입력(반복) -> 대출 목록 표시 -> 반납 정보 입력(반복,
 * 건마다 즉시 연체 판정 출력) -> 전체 반납 이력 출력.
 *
 * loans와 returns가 서로 매칭/검증되지 않는 이유:
 * "빠르게 동작하는 것부터 만들고, 클래스 간 통합은 나중에"라는 목표에
 * 맞춰, 이번 라운드는 두 흐름(대출/반납)을 나란히 돌리기만 한다. 반납
 * 시 "이 책이 실제로 대출 목록에 있는지", "중복 반납은 아닌지" 같은
 * 교차 검증은 아직 없다. loans는 지금 화면 출력(사서 육안 대조용) 외
 * 에는 쓰이지 않아 이후 로직에서 참조되지 않지만, 대출 이력 자체를
 * 남겨야 사서가 반납 처리와 비교해볼 수 있어 의도적으로 유지했다 -
 * 다음 라운드에서 반납 시 이 리스트를 실제로 조회하도록 통합할 예정이고,
 * 그때 ReturnInputHandler의 검색 방식(ArrayList 선형 검색 유지 여부)도
 * 다시 검토한다.
 *
 * Scanner를 하나만 만들어 두 입력 클래스에 공유 주입하는 이유:
 * Scanner(System.in)를 여러 개 만들어도 당장은 동작하지만, 어느 한쪽
 * 에서 close()가 추가되는 순간 System.in 자체가 닫혀 버려서 나머지
 * 모든 Scanner가 함께 죽는다. 하나의 Scanner를 생성자로 주입해 공유
 * 하면 이런 사고를 구조적으로 막을 수 있다.
 *
 * 성능/규모 관점: loanCount, returnCount는 사람이 콘솔에서 직접
 * 입력하는 규모(수십 건 이내)를 가정한다. 모든 처리가 O(n) 순차
 * 반복이라 이 규모에서는 별도 인덱싱이나 캐싱이 필요 없다 - 조기
 * 최적화보다 지금은 정확한 동작이 우선이라고 판단했다.
 */
public class Main {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        LoanInputHandler loanInputHandler = new LoanInputHandler(scanner);
        ReturnInputHandler returnInputHandler = new ReturnInputHandler(scanner);
        OverdueChecker overdueChecker = new OverdueChecker();
        LoanHistoryReport loanHistoryReport = new LoanHistoryReport();

        List<BookLoan> loans = new ArrayList<>();
        List<BookLoan> returns = new ArrayList<>();

        System.out.println("===== 대출 정보 입력 =====");
        System.out.print("대출 건수: ");
        int loanCount = readCountSafely(scanner);
        for (int i = 0; i < loanCount; i++) {
            System.out.println("-- 대출 " + (i + 1) + "번째 --");
            loans.add(loanInputHandler.readLoan());
        }

        System.out.println();
        System.out.println("===== 현재까지 등록된 대출 목록 =====");
        if (loans.isEmpty()) {
            System.out.println("(등록된 대출 없음)");
        } else {
            for (BookLoan loan : loans) {
                System.out.println("- " + loan);
            }
        }

        System.out.println();
        System.out.println("===== 반납 정보 입력 =====");
        System.out.print("반납 건수: ");
        int returnCount = readCountSafely(scanner);
        for (int i = 0; i < returnCount; i++) {
            System.out.println("-- 반납 " + (i + 1) + "번째 --");
            BookLoan returned = returnInputHandler.readReturn();
            returns.add(returned);
            overdueChecker.check(returned);
        }

        System.out.println();
        loanHistoryReport.printHistory(returns);

        scanner.close();
    }

    // loanCount/returnCount 입력도 readIntSafely류와 같은 이유로
    // nextLine()+parseInt()로 통일했다. 이 메서드는 LoanInputHandler/
    // ReturnInputHandler의 private readIntSafely()와 로직이 겹치지만,
    // 접근 범위(Main용 vs 각 Handler용)가 달라 지금은 별도로 두었다 -
    // 셋을 하나의 유틸로 합치는 건 클래스 통합 작업 때 함께 처리한다.
    private static int readCountSafely(Scanner scanner) {
        try {
            return Integer.parseInt(scanner.nextLine().trim());
        } catch (NumberFormatException e) {
            System.out.println("숫자가 아닙니다. 0건으로 처리합니다.");
            return 0;
        }
    }
}
