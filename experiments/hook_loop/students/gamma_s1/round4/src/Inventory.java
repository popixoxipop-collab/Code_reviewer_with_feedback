import java.util.ArrayList;
import java.util.List;

/**
 * 상품 목록을 보관하고, 반복문으로 순회하며 총액을 계산하거나 재고 부족(5개 미만)
 * 상품을 찾는다. 할인 적용은 DiscountPolicy에 위임한다.
 */
public class Inventory {

    /** 재고 부족 기준 수량(이 값 미만이면 재고 부족). */
    public static final int LOW_STOCK_THRESHOLD = 5;

    // ArrayList<Product>를 선택한 이유 (다른 자료구조와 비교):
    //  1) HashMap<String, Product> 대안: 상품명으로 O(1) 조회가 가능해지지만,
    //     이 클래스 어디에도 "이름으로 상품 하나를 찾는" 연산(get-by-key)이 없다
    //     (calculateTotalAmount/findLowStockProducts 모두 전체 순회만 한다 —
    //     실제 메서드 호출 패턴을 확인한 결과다). 게다가 같은 상품명을 두 번
    //     입력하는 경우(예: 같은 상품을 나눠서 입력) Map은 키가 겹쳐서 덮어쓰거나
    //     병합 로직을 추가로 짜야 하는데, 이 과제는 "입력된 그대로 기록"을
    //     요구하므로 그런 병합 자체가 요구사항과 맞지 않는다.
    //  2) LinkedList<Product> 대안: 중간 삽입/삭제가 O(1)이라는 장점이 있지만,
    //     이 프로그램은 끝에 추가(add)와 전체 순회만 하고 중간 삽입/삭제가 전혀
    //     없어 그 장점을 쓸 데가 없다. 반면 ArrayList는 순회 시 배열 기반이라
    //     캐시 지역성이 더 좋다.
    //  결론: 순서를 보존하면서 전체 순회만 하면 되는 이 요구사항에는 ArrayList가
    //  가장 단순하고 적합하다.
    private final List<Product> products = new ArrayList<>();
    private final DiscountPolicy discountPolicy;

    public Inventory(DiscountPolicy discountPolicy) {
        if (discountPolicy == null) {
            throw new IllegalArgumentException("discountPolicy는 null일 수 없습니다.");
        }
        this.discountPolicy = discountPolicy;
    }

    /**
     * 상품을 재고 목록에 추가한다.
     */
    public void addProduct(Product product) {
        // 여기서 null을 막지 않으면 calculateSubtotal()/calculateTotalAmount()의
        // 반복문에서는 product.getAmount() 호출 시, findLowStockProducts()의
        // 반복문에서는 product.getQuantity() 호출 시 각각 NullPointerException이
        // 발생한다. 순회 메서드마다 null 체크를 반복하는 대신, 리스트로 들어오는
        // 입구인 addProduct 한 곳에서만 막아서 이후 모든 순회를 null-free하게 만든다.
        if (product == null) {
            throw new IllegalArgumentException("product는 null일 수 없습니다.");
        }
        products.add(product);
    }

    /** 등록된 상품 목록의 복사본을 반환한다(내부 리스트를 외부 수정으로부터 보호). */
    public List<Product> getProducts() {
        return new ArrayList<>(products);
    }

    public int getProductCount() {
        return products.size();
    }

    /**
     * 할인 적용 전, 가격×수량의 순수 합계.
     */
    public long calculateSubtotal() {
        long subtotal = 0L;
        for (Product product : products) {
            subtotal += product.getAmount();
        }
        return subtotal;
    }

    /**
     * 할인 정책(DiscountPolicy)을 적용한 뒤의 총 금액.
     */
    public long calculateTotalAmount() {
        long total = 0L;
        for (Product product : products) {
            total += discountPolicy.applyDiscount(product, product.getAmount());
        }
        return total;
    }

    // calculateSubtotal()과 calculateTotalAmount()를 반복문 하나로 합쳐서 순회를
    // 한 번만 돌 수도 있다. 그러나 상품 개수는 사람이 콘솔로 직접 입력하는 수준
    // (많아야 수십~수백 개)이라 순회를 한 번 더 도는 비용은 무시할 수 있고, 각
    // 메서드가 "값 하나만" 책임진다는 게 더 명확해서 가독성 쪽을 택했다.

    /**
     * 재고가 LOW_STOCK_THRESHOLD(5개) 미만인 상품 목록을 찾는다.
     */
    public List<Product> findLowStockProducts() {
        List<Product> lowStock = new ArrayList<>();
        for (Product product : products) {
            if (product.getQuantity() < LOW_STOCK_THRESHOLD) {
                lowStock.add(product);
            }
        }
        return lowStock;
    }
}
