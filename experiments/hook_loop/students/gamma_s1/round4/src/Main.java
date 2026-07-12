import java.util.Scanner;

/**
 * 프로그램 진입점. Scanner로 상품(이름/가격/수량)을 원하는 만큼 반복 입력받아
 * Inventory/OrderHistory에 기록하고, 입력이 끝나면 InventoryReport로 결과를 출력한다.
 */
public class Main {

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        DiscountPolicy discountPolicy = new DiscountPolicy();
        Inventory inventory = new Inventory(discountPolicy);
        OrderHistory orderHistory = new OrderHistory();

        System.out.println("=== 상품 입력 ===");
        System.out.println("상품을 원하는 만큼 입력하세요. 이름에 '그만'을 입력하면 종료합니다.");

        while (true) {
            System.out.print("\n상품 이름 (종료: 그만): ");
            String name = scanner.nextLine().trim();
            if (name.isEmpty() || name.equalsIgnoreCase("그만")) {
                break;
            }

            int price = readInt(scanner, "가격: ");
            int quantity = readInt(scanner, "수량: ");

            try {
                Product product = new Product(name, price, quantity);
                inventory.addProduct(product);
                orderHistory.record(product);
                System.out.println("-> \"" + name + "\" 등록 완료");
            } catch (IllegalArgumentException e) {
                System.out.println("입력 오류: " + e.getMessage() + " (해당 상품은 등록되지 않았습니다)");
            }
        }

        InventoryReport report = new InventoryReport(inventory, orderHistory);
        report.print();

        scanner.close();
    }

    /**
     * 정수 하나를 읽는다. 정수로 파싱되지 않으면 다시 입력받는다.
     * (음수인지 여부는 여기서 걸러내지 않고 Product 생성자의 검증에 맡긴다 —
     *  "정수 형식인가"와 "값이 유효한가"를 서로 다른 계층의 책임으로 분리했다.)
     */
    private static int readInt(Scanner scanner, String prompt) {
        while (true) {
            System.out.print(prompt);
            String line = scanner.nextLine().trim();
            try {
                return Integer.parseInt(line);
            } catch (NumberFormatException e) {
                System.out.println("숫자로 입력해주세요.");
            }
        }
    }
}
