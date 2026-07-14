/**
 * 연체(14일 초과) 여부를 판정해 출력하는 클래스.
 *
 * isOverdue(순수 판정)와 check(판정 + 출력)를 분리한 이유:
 * 판정 로직만 따로 떼어두면 나중에 테스트 코드를 추가할 때 System.out
 * 캡처 없이 boolean 리턴값만으로 정확도를 검증할 수 있다. 지금 당장
 * 테스트 코드는 없지만, 출력과 판정이 한 메서드에 섞여 있으면 나중에
 * 테스트를 추가하기 훨씬 번거로워진다고 판단해 이번엔 미리 분리해뒀다.
 *
 * 경계값(14) 처리 - 정확도 관점:
 * 과제 명세가 "14일 초과"이므로 daysElapsed == 14는 연체가 아니고
 * daysElapsed == 15부터 연체다. 그래서 >= 14가 아니라 반드시 > 14로
 * 비교한다. 이 한 글자 차이가 정확도를 좌우하므로 상수명도
 * OVERDUE_LIMIT_DAYS(한계값)로 지어 "이 값 자체는 연체가 아니고
 * 초과해야 연체"라는 의미가 드러나게 했다. 14를 코드에 리터럴로
 * 흩어놓지 않고 상수 하나로 모아둔 이유이기도 하다 - 정책이 바뀌면
 * (예: 방학 중 21일) 이 한 곳만 고치면 된다.
 *
 * 의존성 격리: 이 클래스는 BookLoan의 getDaysElapsed()/getBookTitle()/
 * getBorrowerName() getter만 사용한다. 그 값이 LoanInputHandler에서
 * 왔는지 ReturnInputHandler에서 왔는지, Scanner를 쓰는지 파일을
 * 쓰는지도 전혀 모른다 - BookLoan이라는 DTO의 getter 집합에만
 * 의존하고 두 입력 클래스의 내부 구현에는 결합되지 않는다. 두 입력
 * 클래스의 readIntSafely() 구현을 나중에 바꾸더라도 이 클래스는
 * 손댈 필요가 없다.
 *
 * 공유 컴포넌트 영향 범위: BookLoan은 LoanInputHandler(생성),
 * ReturnInputHandler(생성), OverdueChecker(여기, 사용), LoanHistoryReport
 * (사용), Main(보관/전달)까지 5곳에서 쓰인다. daysElapsed의 타입이나
 * 의미를 바꾸면(예: int 경과일수 -> LocalDate 대출일 + 계산식) 이 5곳
 * 모두 함께 수정해야 하므로, 필드를 바꿀 땐 이 클래스의 "> 14" 비교식
 * 부터 깨지지 않는지 먼저 확인해야 한다.
 */
public class OverdueChecker {
    private static final int OVERDUE_LIMIT_DAYS = 14;

    public boolean isOverdue(BookLoan loan) {
        // null 방어: 호출부가 반납 안 된 대출을 실수로 넘기면(현재 Main
        // 흐름에서는 발생하지 않지만, check()는 public이라 다른 호출자가
        // 생길 수 있음) NPE 대신 false로 안전하게 처리한다.
        if (loan == null) {
            return false;
        }
        return loan.getDaysElapsed() > OVERDUE_LIMIT_DAYS;
    }

    public void check(BookLoan loan) {
        if (loan == null) {
            System.out.println("[연체 판정] 반납 정보가 없어 판정할 수 없습니다.");
            return;
        }

        boolean overdue = isOverdue(loan);
        System.out.println("[연체 판정] " + loan.getBookTitle() + " (" + loan.getBorrowerName() + ") - "
                + loan.getDaysElapsed() + "일 경과 -> " + (overdue ? "연체입니다 (14일 초과)" : "연체 아님"));
    }
}
