import java.util.Scanner;

/**
 * 반납 정보를 입력받는 클래스.
 *
 * 통합 지연에 대한 의도적 기록:
 * 이상적으로는 LoanInputHandler가 쌓아둔 대출 목록(List<BookLoan>)에서
 * 도서명/대출자명으로 검색해 원래 레코드의 경과일수를 그대로 가져와야
 * 한다. 하지만 "빠르게 동작하는 것부터" 만드는 게 이번 라운드 목표라서,
 * 지금은 반납 시점에 경과일수를 사서가 다시 입력하는 방식으로 구현했다.
 * 이 덕분에 ReturnInputHandler는 대출 목록이 어떻게 저장되는지(ArrayList
 * 인지, 몇 건이 쌓였는지) 전혀 몰라도 되고, LoanInputHandler의 내부
 * 구현에는 결합되지 않는다 - 아는 것은 오직 BookLoan이라는 DTO를 만드는
 * 방법뿐이다.
 *
 * 트레이드오프: 사서가 같은 경과일수를 두 번(대출 때, 반납 때) 입력해야
 * 하는 중복 부담이 있다. 다음 라운드에서 "반납 시 대출 목록에서 자동
 * 조회"로 통합할 계획이며, 그때는 도서명 기준 검색이 실제로 필요해지므로
 * ArrayList 선형 검색 O(n) 대신 HashMap<String, BookLoan> 전환을 검토할
 * 것이다. 지금은 검색 연산 자체가 코드 어디에도 없어(대출 목록을 읽는
 * 코드가 이 클래스에 없음을 확인했다) ArrayList로 충분하다고 판단했다 -
 * Map으로 미리 바꿔봤자 지금 당장은 이득이 없고, title이 중복되는 두
 * 대출(같은 책을 두 사람이 각각 빌린 경우)을 키로 어떻게 구분할지까지
 * 미리 설계해야 하는 복잡도만 늘어난다.
 *
 * fan-in 메모: LoanInputHandler와 마찬가지로 Main에서만 호출된다
 * (fan-in=1). 의도된 구조 - 반납 흐름을 대출 흐름과 나란히 두되 서로
 * 직접 호출하지 않게 해서, 한쪽을 고쳐도 다른 쪽 컴파일에 영향이
 * 없게 했다.
 */
public class ReturnInputHandler {
    private Scanner scanner;

    public ReturnInputHandler(Scanner scanner) {
        this.scanner = scanner;
    }

    public BookLoan readReturn() {
        System.out.print("반납할 도서명: ");
        String title = scanner.nextLine();

        System.out.print("대출자명: ");
        String borrower = scanner.nextLine();

        System.out.print("대출일로부터 경과일수(반납 시점 기준): ");
        int days = readIntSafely();

        return new BookLoan(title, borrower, days);
    }

    // LoanInputHandler.readIntSafely()와 동일한 로직의 의도적 중복.
    // 자세한 이유는 LoanInputHandler 쪽 주석 참고.
    private int readIntSafely() {
        int value;
        try {
            value = Integer.parseInt(scanner.nextLine().trim());
        } catch (NumberFormatException e) {
            System.out.println("숫자가 아닙니다. 0으로 처리합니다.");
            value = 0;
        }
        return value;
    }
}
