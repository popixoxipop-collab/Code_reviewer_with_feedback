import java.util.Scanner;

/**
 * 대출 정보를 입력받는 클래스 (도서명, 대출자명, 경과일수).
 *
 * fan-in 메모: 현재 Main에서만 생성/호출된다(fan-in=1). 의도된 구조다 -
 * "입력 담당"과 "판정 담당(OverdueChecker)", "출력 담당(LoanHistoryReport)"을
 * 완전히 분리했기 때문에, 지금은 호출자가 Main 하나뿐이더라도 나중에 입력
 * 소스를 콘솔이 아니라 파일/웹 폼으로 바꿀 때 이 클래스만 교체하면 되도록
 * 얇게 유지했다. fan-in=1은 "아직 아무도 안 써서 방치된 모듈"이 아니라
 * "이번 라운드엔 진입점이 Main 하나뿐인 계층형 콘솔 앱"이라는 구조적
 * 특성일 뿐이다.
 *
 * Scanner를 생성자로 주입받는 이유(필드로 새로 만들지 않는 이유):
 * 이 클래스 안에서 매번 새 Scanner(System.in)를 만들면 당장은 동작하지만,
 * ReturnInputHandler도 똑같이 System.in을 감싸는 두 번째 Scanner를 만들게
 * 되고, 한쪽에서 scanner.close()라도 호출하면 System.in 자체가 닫혀
 * 반대쪽 입력까지 죽는 사고가 날 수 있다. Main이 Scanner 하나를 만들어
 * 양쪽에 공유 주입하면 이 문제를 원천적으로 피할 수 있어 이 방식을
 * 택했다(자세한 이유는 Main 클래스 주석 참고).
 */
public class LoanInputHandler {
    private Scanner scanner;

    public LoanInputHandler(Scanner scanner) {
        this.scanner = scanner;
    }

    public BookLoan readLoan() {
        System.out.print("도서명: ");
        String title = scanner.nextLine();

        System.out.print("대출자명: ");
        String borrower = scanner.nextLine();

        System.out.print("대출일로부터 경과일수: ");
        int days = readIntSafely();

        return new BookLoan(title, borrower, days);
    }

    // 정수 입력 검증: nextInt()를 쓰면 숫자 뒤 개행 문자가 버퍼에 남아
    // 바로 다음 nextLine() 호출이 빈 문자열을 읽어버리는 전형적인 버그가
    // 생긴다. 그래서 처음부터 끝까지 nextLine() + parseInt()로 통일했다.
    // 숫자가 아닌 값이 들어오면 NumberFormatException을 잡아 0으로
    // 대체한다 - 프로그램 전체가 죽는 것보다는 "0일 경과"로 기록되고
    // 계속 진행되는 편이 도서관 창구 운영 관점에서 낫다고 판단했다.
    // (이 메서드는 ReturnInputHandler에도 동일하게 복제돼 있다 - 아직
    // 공용 유틸 클래스로 뽑지 않은 의도적 중복이다. 두 클래스가 각자
    // 독립적으로 동작하게 하려고 지금 라운드에서는 굳이 합치지 않았고,
    // 클래스 간 통합 작업 때 같이 정리할 계획이다.)
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
