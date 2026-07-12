import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 이번 프로그램 실행 동안 입력된 주문 내역을 기록/관리한다.
 * 기록된 내역을 화면에 어떻게 보여줄지는 InventoryReport의 책임이다.
 */
public class OrderHistory {

    // 주문 한 건 = 이번 실행에서 사용자가 입력한 Product 한 개.
    // Product가 이미 name/price/quantity를 모두 가지고 있어서, 이 셋을 그대로
    // 복제하는 OrderRecord류 클래스를 새로 만들면 필드만 중복되고 얻는 게 없다.
    // 과제가 클래스를 6개로 한정했다는 점에서도 별도 클래스 추가보다 Product
    // 재사용이 맞다고 판단했다.
    // 주의: Inventory.products와는 별개의 리스트다. 둘 다 addProduct/record 시점에
    // 각자 채워 넣으며 서로 참조를 공유하지 않는다 — 이후 Inventory 쪽에 재고를
    // 조정하는 기능(예: 판매 후 차감)이 추가되어도 주문 이력 자체는 입력 시점
    // 그대로 남아야 하기 때문이다.
    private final List<Product> orders = new ArrayList<>();

    /**
     * 주문(상품 입력) 한 건을 기록한다.
     */
    public void record(Product product) {
        // InventoryReport가 getOrders()로 순회하며 product.getName() 등을 호출하는데,
        // 여기서 null을 막지 않으면 그 순회에서 NullPointerException이 난다. 기록
        // 시점(record)에서 막아 조회 시점(InventoryReport)을 항상 null-free로
        // 유지한다 — Inventory.addProduct와 동일한 이유의 동일한 패턴이다.
        if (product == null) {
            throw new IllegalArgumentException("product는 null일 수 없습니다.");
        }
        orders.add(product);
    }

    public int getOrderCount() {
        return orders.size();
    }

    /** 기록된 주문 내역(입력 순서 그대로)을 반환한다. 외부에서 수정할 수 없다. */
    public List<Product> getOrders() {
        return Collections.unmodifiableList(orders);
    }
}
