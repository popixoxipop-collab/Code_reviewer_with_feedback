import java.util.List;
import java.util.Scanner;

/**
 * Main - 프로그램 진입점. CartInputHandler -&gt; PriceCalculator -&gt;
 * ReceiptPrinter/CartSummary 순서로 각 클래스를 호출해서 연결한다.
 *
 * <p>이번 단계는 "빠르게 동작하는 것부터" 만드는 것이 목표라, 각 클래스는 서로를
 * 직접 참조하지 않고 Main이 중간에서 값을 꺼내 다음 클래스로 넘겨주는 가장 단순한
 * 절차형 연결만 되어 있다(각 클래스 Javadoc의 "fan-in=1" 설명 참고 - CartInputHandler
 * /PriceCalculator/ReceiptPrinter/CartSummary는 전부 Main에서만 호출되고, 서로는
 * 서로를 모른다). 나중에 통합을 다시 다룰 때는 예를 들어 이 흐름을 CartService 같은
 * 클래스로 한 번 더 감싸서 Main은 CartService.run() 하나만 호출하게 바꾸는 리팩터링을
 * 고려할 수 있다 - 지금은 그렇게 하지 않았다(요구된 6개 클래스 범위를 벗어나는 추가
 * 클래스이기도 하고, 지금 규모에서는 과설계로 판단했다).
 */
public class Main {
    public static void main(String[] args) {
        try (Scanner scanner = new Scanner(System.in)) {
            CartInputHandler inputHandler = new CartInputHandler(scanner);
            List<CartItem> items = inputHandler.readCartItems();

            PriceCalculator calculator = new PriceCalculator();
            long subtotal = calculator.calculateSubtotal(items);
            long vat = calculator.calculateVat(subtotal);
            long discount = calculator.calculateDiscount(subtotal);
            long total = calculator.calculateTotal(subtotal, vat, discount);

            ReceiptPrinter receiptPrinter = new ReceiptPrinter();
            receiptPrinter.printReceipt(items, subtotal, vat, discount, total);

            CartSummary summary = new CartSummary();
            summary.printSummary(items);
        }
        // try-with-resources가 Scanner(System.in)를 닫는다. main()이 끝나면 더 이상
        // 입력을 읽지 않으므로 System.in을 닫아도 이후 로직에 영향이 없다.
    }
}
