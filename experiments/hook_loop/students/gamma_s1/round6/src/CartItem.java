import java.util.Objects;

/**
 * CartItem - 장바구니에 담긴 상품 1건의 정보를 표현하는 모델(값 객체) 클래스.
 *
 * <p><b>공유 범위(fan-in) 기록:</b> 이 클래스는 CartInputHandler(생성),
 * PriceCalculator(price/quantity를 읽어 금액 계산), ReceiptPrinter(name/price/
 * quantity를 읽어 줄 단위로 출력), CartSummary(quantity를 읽어 총 수량 집계) 이렇게
 * 4곳에서 직접 사용된다. 이 6개 클래스짜리 프로그램에서 fan-in이 1보다 큰 사실상
 * 유일한 공유 컴포넌트다. 그래서 필드를 생성자에서만 채우고 외부에는 getter만
 * 공개했다(불변에 가까운 설계) - CartItem 필드 구성을 바꾸면 위 4개 클래스 모두
 * 영향을 받으므로, 아무 데서나 setter로 값을 바꿔 다른 클래스가 이미 읽어간 값과
 * 어긋나는 상태가 생기는 것을 애초에 막기 위함이다. setter가 실제로 필요해지면
 * (예: "수량 변경" 기능 추가) 그때 이 필드를 실제로 읽는 4곳의 호출 패턴을 먼저
 * 다시 확인하고 영향 범위를 검토한 뒤 추가할 것.
 *
 * <p><b>가격 타입 선택 - long vs double vs BigDecimal (트레이드오프):</b>
 * <ul>
 *   <li>double: 이진 부동소수점이라 0.1 같은 값이 정확히 표현되지 않아(예: 0.1+0.2
 *   != 0.3) 여러 상품의 금액을 반복 합산하는 소계/부가세 계산에서 오차가 누적될 수
 *   있다. 원화는 애초에 소수 단위(센트 같은 것)가 없으므로 부동소수점을 쓸 이유
 *   자체가 없다고 판단해 채택하지 않았다.</li>
 *   <li>BigDecimal: 정밀도 면에서는 가장 안전하고 실무 결제 시스템에서는 표준적인
 *   선택이지만, +, -, * 연산자를 그대로 쓸 수 없고 add()/multiply()/setScale()
 *   같은 메서드 호출로 계산해야 한다. 이번 과제 요구사항이 명시적으로 "연산자를
 *   이용해" 계산하는 것이므로 과제 취지와 맞지 않고, 8주차 시점에 반올림 모드까지
 *   다루는 것은 과도한 복잡도라 채택하지 않았다(실무였다면 이 타입을 썼을 것).</li>
 *   <li>int: 정수 연산이라 부동소수점 오차는 없지만 최댓값이 약 21억(2,147,483,647)
 *   이라, 비정상적으로 큰 가격이나 수량이 입력되면(오타 포함) price*quantity 곱셈이
 *   조용히 오버플로우되어 음수로 뒤집힐 위험이 있다.</li>
 *   <li><b>long(채택):</b> 정수 연산이라 부동소수점 오차가 없고, 최댓값이 약
 *   922경(9,223,372,036,854,775,807)으로 int보다 40억 배 이상 커서, 이 프로그램
 *   규모(장바구니 상품 몇~수십 개, 개별 금액 수십~수백만 원 수준)에서는 현실적으로
 *   오버플로우가 발생할 수 없다. int 대비 메모리는 필드당 4바이트 더 쓰지만, 개별
 *   상품 단위 객체 몇 개 수준에서는 무시할 수 있는 비용이라 정확도(오버플로우 방지)
 *   를 위해 이 비용을 지불하는 것이 합리적이라고 판단했다.</li>
 * </ul>
 */
public class CartItem {

    private final String name;
    private final long price;      // 단가(원 단위 정수). 타입 선택 근거는 클래스 상단 Javadoc 참고
    private final int quantity;    // 수량. 현실적인 장바구니 수량 범위에서는 int로 오버플로우 우려 없음

    /**
     * @param name     상품명. null 또는 공백뿐인 문자열이면 IllegalArgumentException을
     *                 던져 즉시 실패(fail-fast)한다. CartInputHandler는 사용자에게
     *                 재입력을 유도하는 방식으로 이 상황을 처리하지만(그 클래스의
     *                 Javadoc 참고), 그것과는 별개로 CartInputHandler를 거치지 않고
     *                 누군가 CartItem을 직접 생성하는 경로(예: 테스트 코드)가 있어도
     *                 "이름 없는 상품"이 존재할 수 없도록 생성자 자체에서 한 번 더 막는다.
     *                 이렇게 두 지점에서 막아두면, 호출 순서와 무관하게 CartItem은 항상
     *                 유효한 상태로만 존재한다.
     * @param price    단가. 음수면 IllegalArgumentException.
     * @param quantity 수량. 0 이하이면 IllegalArgumentException(0개짜리 항목이
     *                 장바구니에 존재할 이유가 없기 때문).
     */
    public CartItem(String name, long price, int quantity) {
        if (name == null || name.trim().isEmpty()) {
            throw new IllegalArgumentException("상품명은 비어 있을 수 없습니다.");
        }
        if (price < 0) {
            throw new IllegalArgumentException("가격은 음수가 될 수 없습니다: " + price);
        }
        if (quantity <= 0) {
            throw new IllegalArgumentException("수량은 1 이상이어야 합니다: " + quantity);
        }
        this.name = name;
        this.price = price;
        this.quantity = quantity;
    }

    public String getName() {
        return name;
    }

    public long getPrice() {
        return price;
    }

    public int getQuantity() {
        return quantity;
    }

    /**
     * 이 항목 한 줄의 소계(단가 x 수량). PriceCalculator가 전체 소계를 낼 때 이
     * 메서드를 그대로 재사용한다(계산식을 두 군데에 중복 작성하지 않기 위함) -
     * ReceiptPrinter도 영수증의 각 줄 금액을 출력할 때 동일하게 재사용한다.
     */
    public long lineTotal() {
        return price * quantity;
    }

    @Override
    public String toString() {
        return name + " x" + quantity + " (" + price + "원)";
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) {
            return true;
        }
        if (!(o instanceof CartItem)) {
            return false;
        }
        CartItem other = (CartItem) o;
        return price == other.price
                && quantity == other.quantity
                && Objects.equals(name, other.name);
    }

    @Override
    public int hashCode() {
        return Objects.hash(name, price, quantity);
    }
}
