/**
 * 할인 적용 로직. Inventory가 총액을 계산할 때 이 클래스를 사용한다.
 *
 * 현재 이 클래스를 호출하는 곳은 Inventory 한 곳뿐이라 fan-in=1이다.
 * 이는 실수로 남은 미사용 코드가 아니라, 과제 명세가 "DiscountPolicy는 Inventory가
 * 사용하세요"라고 명시적으로 지정한 구조를 그대로 따른 결과다. 할인 판단 로직을
 * Inventory 안에 인라인으로 두지 않고 별도 클래스로 뺀 이유는
 * (1) 할인 정책이 나중에 바뀌거나(예: 회원 등급 할인 추가) 여러 정책 중 하나를
 *     고르는 구조로 확장될 가능성이 있고,
 * (2) Inventory의 반복문(총액 계산 / 재고부족 탐색)과 할인율 판단을 분리해두면
 *     Inventory 쪽을 수정·테스트할 때 할인 규칙까지 함께 건드릴 필요가 없기
 *     때문이다.
 */
public class DiscountPolicy {

    // 대량 구매 할인 기준. 이 과제는 별도의 실제 판매 데이터가 없는 신규 프로그램이라
    // "10개 이상 구매 시 10% 할인"은 실측치가 아니라 과제 안내("편한 대로 정해도
    // 됩니다")에 따라 정한 예시 정책이다. 실제 서비스라면 판매 데이터를 근거로
    // 재산정해야 한다 — 임의값이라는 점을 그대로 밝혀 둔다.
    private static final int BULK_QUANTITY_THRESHOLD = 10;
    private static final double BULK_DISCOUNT_RATE = 0.10;

    /**
     * amount(할인 전 금액)에 이 상품의 할인율을 적용한 금액을 반환한다.
     */
    public long applyDiscount(Product product, long amount) {
        if (product == null) {
            throw new IllegalArgumentException("product는 null일 수 없습니다.");
        }
        // 현재 유일한 호출부인 Inventory는 항상 product.getAmount()를 그대로 넘기고,
        // Product 생성자가 price/quantity를 0 이상으로 강제하므로 amount가 음수로
        // 들어오는 경로는 지금 코드베이스엔 없다(호출 패턴으로 확인함). 그래도 이
        // 클래스가 나중에 다른 곳에서도 재사용될 수 있으므로 API 차원의 불변식으로
        // 남겨둔다.
        if (amount < 0) {
            throw new IllegalArgumentException("amount는 음수가 될 수 없습니다: " + amount);
        }

        double rate = resolveDiscountRate(product);
        // amount(long)와 rate(double)를 곱하면 double로 승격되어 계산된다.
        // amount가 2^53(약 9,007조)을 넘으면 double 정밀도 손실 가능성이 있지만,
        // 이 프로그램의 입력값(price/quantity 모두 int 범위)으로는 amount가 그
        // 범위에 도달할 수 없어 실질적인 문제는 없다.
        long discount = Math.round(amount * rate);
        return amount - discount;
    }

    private double resolveDiscountRate(Product product) {
        if (product.getQuantity() >= BULK_QUANTITY_THRESHOLD) {
            return BULK_DISCOUNT_RATE;
        }
        return 0.0;
    }
}
