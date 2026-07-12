/**
 * 상품 하나의 이름/가격/수량을 담는 데이터 클래스.
 *
 * 계산 로직(총액 합산, 재고부족 판정 등)은 이 클래스에 두지 않고 Inventory /
 * DiscountPolicy 쪽에 둔다 — 과제 명세가 "총액 계산·재고부족 찾기"를 Inventory의
 * 책임으로 명시하고 있기 때문이다. 다만 price*quantity(라인 금액)는 Product
 * 자신의 필드만으로 결정되는 순수 계산이라 getAmount()로 예외적으로 포함했다:
 * 이 계산이 Inventory(총액 계산)와 InventoryReport(주문 내역 출력) 양쪽에서
 * 각각 필요한데, 두 곳에 똑같은 "int 오버플로우 방지용 long 캐스팅" 코드를
 * 중복시키는 것보다 데이터의 출처인 Product 한 곳에 모아두는 편이 낫다고 판단했다.
 *
 * 공유 범위: 이 클래스는 Main(생성) / Inventory(순회·집계) / DiscountPolicy(수량 조회) /
 * OrderHistory(보관) / InventoryReport(출력) 총 5곳에서 사용된다. 필드를 추가·변경할
 * 때는 이 5곳을 모두 확인해야 한다. 필드가 더 늘어나 "출력 포맷"이 복잡해지면
 * 별도의 Formatter 클래스로 분리하는 것도 대안이지만, 현재는 필드가 3개뿐이라
 * 그 정도 분리는 과설계라고 보고 적용하지 않았다.
 */
public class Product {

    private final String name;
    private final int price;
    private final int quantity;

    public Product(String name, int price, int quantity) {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("상품 이름은 비어 있을 수 없습니다.");
        }
        if (price < 0) {
            throw new IllegalArgumentException("가격은 음수가 될 수 없습니다: " + price);
        }
        if (quantity < 0) {
            throw new IllegalArgumentException("수량은 음수가 될 수 없습니다: " + quantity);
        }
        this.name = name;
        this.price = price;
        this.quantity = quantity;
    }

    public String getName() {
        return name;
    }

    /** 상품 1개당 가격. 원화는 소수 단위가 없으므로 double이 아닌 int로 충분하다. */
    public int getPrice() {
        return price;
    }

    public int getQuantity() {
        return quantity;
    }

    /**
     * 이 상품 라인의 금액(가격 x 수량)을 long으로 반환한다.
     *
     * price, quantity는 각각 int이지만 둘을 int 상태로 곱하면 Integer.MAX_VALUE
     * (2,147,483,647)를 넘는 순간 오버플로우가 난다. 예를 들어 가격 3,000,000원짜리
     * 상품을 1,000개 등록하면 실제 값은 30억으로 int 범위를 넘어선다. 그래서 곱하기
     * 전에 먼저 long으로 변환해 오버플로우 없이 계산한다.
     */
    public long getAmount() {
        return (long) price * (long) quantity;
    }

    @Override
    public String toString() {
        return name + " (가격: " + price + "원, 수량: " + quantity + "개)";
    }
}
