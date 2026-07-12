import java.util.List;

/**
 * Inventory(재고/총액)와 OrderHistory(주문 내역)의 결과를 보기 좋게 콘솔에 출력하는
 * 역할만 담당한다. 계산 로직은 갖지 않고, 이미 계산된 값을 조회해서 형식만 맞춰
 * 출력한다.
 */
public class InventoryReport {

    private final Inventory inventory;
    private final OrderHistory orderHistory;

    public InventoryReport(Inventory inventory, OrderHistory orderHistory) {
        if (inventory == null) {
            throw new IllegalArgumentException("inventory는 null일 수 없습니다.");
        }
        if (orderHistory == null) {
            throw new IllegalArgumentException("orderHistory는 null일 수 없습니다.");
        }
        this.inventory = inventory;
        this.orderHistory = orderHistory;
    }

    /** 전체 리포트(요약 -> 전체 상품 -> 재고부족 -> 주문내역)를 순서대로 출력한다. */
    public void print() {
        printSummary();
        printAllProducts();
        printLowStock();
        printOrderHistory();
    }

    private void printSummary() {
        long subtotal = inventory.calculateSubtotal();
        long total = inventory.calculateTotalAmount();
        long discountAmount = subtotal - total;

        System.out.println("=======================================");
        System.out.println("            재고 관리 리포트");
        System.out.println("=======================================");
        System.out.println("등록된 상품 종류 수 : " + inventory.getProductCount() + "개");
        System.out.printf("할인 전 합계        : %,d원%n", subtotal);
        System.out.printf("할인 금액           : %,d원%n", discountAmount);
        System.out.printf("최종 총 금액(할인후): %,d원%n", total);
    }

    private void printAllProducts() {
        List<Product> allProducts = inventory.getProducts();

        System.out.println("---------------------------------------");
        System.out.println("전체 등록 상품 목록: " + allProducts.size() + "개");
        if (allProducts.isEmpty()) {
            System.out.println("  - 등록된 상품이 없습니다.");
        } else {
            for (Product product : allProducts) {
                System.out.println("  - " + product);
            }
        }
    }

    private void printLowStock() {
        List<Product> lowStock = inventory.findLowStockProducts();

        System.out.println("---------------------------------------");
        System.out.println("재고 부족 상품 (" + Inventory.LOW_STOCK_THRESHOLD + "개 미만): " + lowStock.size() + "건");
        if (lowStock.isEmpty()) {
            System.out.println("  - 재고 부족 상품이 없습니다.");
        } else {
            for (Product product : lowStock) {
                System.out.println("  - " + product);
            }
        }
    }

    private void printOrderHistory() {
        int orderCount = orderHistory.getOrderCount();
        List<Product> orders = orderHistory.getOrders();

        System.out.println("---------------------------------------");
        System.out.println("이번 실행 주문 내역: " + orderCount + "건");
        if (orders.isEmpty()) {
            System.out.println("  - 입력된 주문이 없습니다.");
        } else {
            int index = 1;
            for (Product product : orders) {
                System.out.printf("  %d. %s - %,d원 x %d개 = %,d원%n",
                        index, product.getName(), product.getPrice(),
                        product.getQuantity(), product.getAmount());
                index++;
            }
        }
        System.out.println("=======================================");
    }
}
