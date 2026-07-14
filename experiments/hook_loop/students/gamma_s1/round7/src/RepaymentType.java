/**
 * 상환 방식을 표현하는 열거형(enum).
 *
 * <p>자료구조 대안 비교 (String 대 int 코드 대 enum):
 * - String("원리금균등"): 사용자가 직접 문자열을 입력하게 하면 "원리금 균등" /
 *   "원리금균등상환" 같은 표기 흔들림·오타에 취약하고, RepaymentSchedule에서
 *   문자열로 분기할 때 오타가 있어도 컴파일 타임에는 절대 잡히지 않는다(런타임에
 *   default로 조용히 빠질 위험).
 * - int 코드(1/2/3): 메뉴 선택 자체는 간단하지만, RepaymentSchedule 안에서
 *   "case 1"이 어떤 상환방식인지 코드만 봐서는 알 수 없는 매직넘버가 된다.
 * - enum(현재 선택): RepaymentInputHandler가 메뉴 번호를 파싱해 이 enum 값
 *   하나로 변환해두면, 이후 이 값을 넘겨받는 모든 코드(RepaymentSchedule의 switch)는
 *   컴파일러/IDE가 처리 누락 case를 잡아줄 수 있고,애초에 존재하지 않는 상환방식
 *   값 자체가 표현 불가능해진다(illegal state unrepresentable). 메뉴 파싱이라는
 *   한 번의 변환 비용을 RepaymentInputHandler가 떠안는 대신, 그 뒤로는 유효성
 *   재검증이 필요 없다.
 *
 * <p>공유 범위(fan-in 기록): RepaymentInputHandler(생성) → Main(중개) →
 * RepaymentSchedule(소비) 3곳에서 쓰이는 공유 타입이다. 새 상환방식을 추가하려면
 * 이 enum에 상수를 추가한 뒤 RepaymentInputHandler의 메뉴 매핑과
 * RepaymentSchedule.generateRows()의 switch 양쪽에 case를 추가해야 한다.
 */
public enum RepaymentType {
    EQUAL_PRINCIPAL_INTEREST("원리금균등상환"),
    EQUAL_PRINCIPAL("원금균등상환"),
    BULLET("만기일시상환");

    private final String displayName;

    RepaymentType(String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() {
        return displayName;
    }
}
