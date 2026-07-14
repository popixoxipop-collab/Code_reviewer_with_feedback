/**
 * 대출 1건의 정보를 담는 모델(DTO) 클래스.
 *
 * 이 클래스는 로직을 거의 갖지 않는 순수 데이터 홀더로 설계했다.
 * OverdueChecker/LoanHistoryReport 같은 소비 측 클래스가 "이 값이
 * Scanner로 들어왔는지, 파일에서 왔는지"를 몰라도 되게 하려는 의도이며,
 * 소비 측은 오직 이 클래스의 getter만 알면 된다. 인터페이스를 따로 뽑지
 * 않은 이유는 구현체가 하나뿐이라 지금은 다형성이 필요 없기 때문이다 -
 * 구현이 여러 개가 될 때(예: 종이 카드 대출 vs 전자 대출) 그때 인터페이스
 * 추출을 고려한다.
 *
 * 필드 타입 선택과 트레이드오프:
 * - bookTitle, borrowerName: String. 산술 연산 대상이 아니고 동등성
 *   비교(추후 검색 기능 추가 시)만 필요하므로 String이면 충분하다.
 * - daysElapsed: int (long/Integer 대신 선택).
 *   1) 오버플로우 관점: 도서관 대출 정책상 경과일수가 int 최댓값
 *      (2,147,483,647일 ≈ 588만 년)에 근접할 시나리오가 없으므로
 *      long은 과설계다.
 *   2) 성능 관점: LoanInputHandler/ReturnInputHandler가 Scanner 입력을
 *      Integer.parseInt()로 바로 파싱해 int를 얻는데, 이걸 다시 Integer로
 *      박싱해서 들고 있으면 대출 건마다 불필요한 객체 생성 오버헤드가
 *      생긴다(대출 수가 많아질수록 GC 압박 증가).
 *   3) 정확도 관점: Integer(래퍼)를 쓰면 null이 허용되어 "경과일수 모름"을
 *      표현할 수 있지만, 이 도메인에서 daysElapsed가 없는 상태는 존재하지
 *      않는다(입력 실패 시 0으로 명시 처리하기로 LoanInputHandler에서 결정).
 *      null 허용은 OverdueChecker의 비교 연산(> 14)에서 언박싱 NPE 위험만
 *      늘리므로 int를 선택했다.
 *
 * 공유 컴포넌트 메모: 이 클래스는 LoanInputHandler/ReturnInputHandler(생성),
 * OverdueChecker/LoanHistoryReport(사용), Main(보관/전달)까지 최소 5곳에서
 * 쓰인다. 자세한 영향 범위 설명은 OverdueChecker 클래스 주석 참고.
 */
public class BookLoan {
    private String bookTitle;
    private String borrowerName;
    private int daysElapsed;

    public BookLoan(String bookTitle, String borrowerName, int daysElapsed) {
        // null 방어: 현재 유일한 생성 경로인 LoanInputHandler/ReturnInputHandler는
        // Scanner.nextLine() 결과를 넘기므로 null이 들어올 일이 거의 없지만
        // (입력 스트림이 끊기면 nextLine()에서 NoSuchElementException이 먼저
        // 터진다), 이 생성자가 테스트 코드나 다른 입력 경로에서 직접 호출될
        // 가능성을 열어두고 있다. 여기서 null을 막지 않으면 LoanHistoryReport의
        // toString() 출력에 "null" 문자열이 섞이거나, 향후 검색 기능에서
        // title.equals(...)를 호출할 때 NullPointerException이 터져 반납 이력
        // 출력 전체가 멈추는 상황이 생길 수 있다 - 그 영향을 여기서 원천 차단한다.
        this.bookTitle = (bookTitle == null) ? "" : bookTitle;
        this.borrowerName = (borrowerName == null) ? "" : borrowerName;
        this.daysElapsed = daysElapsed;
    }

    public String getBookTitle() {
        return bookTitle;
    }

    public void setBookTitle(String bookTitle) {
        this.bookTitle = (bookTitle == null) ? "" : bookTitle;
    }

    public String getBorrowerName() {
        return borrowerName;
    }

    public void setBorrowerName(String borrowerName) {
        this.borrowerName = (borrowerName == null) ? "" : borrowerName;
    }

    public int getDaysElapsed() {
        return daysElapsed;
    }

    public void setDaysElapsed(int daysElapsed) {
        this.daysElapsed = daysElapsed;
    }

    @Override
    public String toString() {
        return bookTitle + " / " + borrowerName + " / " + daysElapsed + "일 경과";
    }
}
