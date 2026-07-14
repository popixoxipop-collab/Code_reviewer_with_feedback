import java.util.ArrayList;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.Scanner;

/**
 * CartInputHandler - Scanner로 상품명/가격/수량을 반복 입력받아 CartItem 목록을 만든다.
 *
 * <p><b>자료구조 선택: ArrayList (대안 비교)</b>
 * 이 프로그램에서 장바구니 항목은 "입력한 순서대로 끝에 추가 -> 이후 전체를 앞에서
 * 부터 순회하며 합계 계산/영수증 출력"만 하고, 중간 삽입·삭제나 이름으로 찾는 연산은
 * 실제 코드 어디에도 없다(PriceCalculator/ReceiptPrinter/CartSummary 모두 for-each
 * 순회만 한다). 이 접근 패턴을 기준으로 비교하면:
 * <ul>
 *   <li><b>ArrayList(채택):</b> 끝에 추가(add)는 상각 O(1), 순회도 O(n)으로 저렴하며
 *   내부적으로 배열이라 캐시 지역성도 좋다. 실제 사용 패턴(끝에 추가 + 전체 순회)과
 *   정확히 일치한다.</li>
 *   <li><b>LinkedList:</b> 양끝 삽입/삭제가 O(1)이라는 장점이 있지만, 이 프로그램은
 *   리스트 중간/앞쪽 삽입·삭제를 전혀 하지 않으므로 그 장점을 쓸 일이 없다. 반대로
 *   노드마다 앞/뒤 포인터를 별도로 저장해 원소당 메모리 오버헤드가 ArrayList보다
 *   크고, 나중에 인덱스로 접근하는 코드가 추가되면 O(n)이라 오히려 손해다. 채택 안 함.</li>
 *   <li><b>HashMap&lt;String, CartItem&gt;:</b> 상품명으로 즉시 조회하거나 "같은
 *   이름 재입력 시 수량 합산" 같은 병합이 필요하다면 유리하다. 하지만 (1) 이 과제는
 *   그런 병합 요구사항이 없고, (2) 입력 순서를 보존하려면 LinkedHashMap이 필요하며,
 *   (3) 같은 상품명을 서로 다른 줄로 유지할지 병합할지부터 정책을 정해야 하는데
 *   지금 범위 밖이다. 이름 기반 조회를 실제로 호출하는 코드가 생기면(메서드 호출
 *   패턴에 "이름으로 찾기"가 등장하면) 그때 재검토한다. 채택 안 함.</li>
 * </ul>
 *
 * <p><b>의존 관계(fan-in=1, 의도된 설계):</b> 이 클래스를 직접 호출하는 곳은 Main
 * 하나뿐이다. 입력(이 클래스)을 계산(PriceCalculator)·출력(ReceiptPrinter/
 * CartSummary)과 서로 모르는 상태로 분리해두면, 나중에 입력 방식을 Scanner에서
 * 파일/GUI로 바꾸더라도 반환 타입(List&lt;CartItem&gt;)만 유지하면 PriceCalculator
 * 이하는 손댈 필요가 없다. "클래스 간 통합은 나중에" 방침대로, 지금은 Main이
 * List&lt;CartItem&gt; 하나만 다음 클래스로 넘기는 최소 연결만 되어 있다.
 *
 * <p><b>null/예외적 입력이 다른 메서드에 미치는 영향:</b> readCartItems()의 반환값은
 * 절대 null이 아니다(입력이 하나도 없으면 빈 리스트를 반환) - 이것을 명시적인
 * 계약으로 삼아서, 호출부인 PriceCalculator/ReceiptPrinter/CartSummary가 매번
 * null 체크를 하지 않고도 바로 순회할 수 있게 했다(다만 그 세 클래스는 이 계약이
 * 깨지는 경우까지 대비해 각자 자체적으로 null 방어 코드를 한 번 더 가지고 있다 -
 * 각 클래스 Javadoc 참고). 입력 스트림이 도중에 끝나는 경우(NoSuchElementException)
 * 는 readLineOrNull()에서 null로 변환해 흡수하고, 그 시점까지 모은 항목은 버리지
 * 않고 그대로 반환한다 - 오타 한 번이나 스트림 종료 때문에 이미 입력해 둔 항목들까지
 * 통째로 날아가면 사용자 입장에서 손해가 크기 때문이다.
 */
public class CartInputHandler {

    private final Scanner scanner;

    public CartInputHandler(Scanner scanner) {
        this.scanner = scanner;
    }

    /**
     * 상품명을 빈 값으로 입력할 때까지(또는 입력 스트림이 끝날 때까지) 반복해서
     * CartItem을 읽어 리스트로 반환한다. 반환값은 절대 null이 아니다.
     */
    public List<CartItem> readCartItems() {
        List<CartItem> items = new ArrayList<>();

        System.out.println("=== 장바구니 상품 입력 (상품명 없이 Enter를 누르면 종료) ===");

        while (true) {
            System.out.print("상품명: ");
            String name = readLineOrNull();

            // null(입력 스트림 종료)과 빈 문자열(사용자가 종료 의사 표시)을 같은
            // "종료 신호"로 취급한다 - 둘 다 "더 담을 상품이 없다"는 의미이기 때문.
            if (name == null || name.trim().isEmpty()) {
                break;
            }

            Long price = readLong("가격: ");
            if (price == null) {
                // 3회 재시도에도 실패했거나 스트림이 끝난 경우. 여기서 현재 항목만
                // 건너뛰고 계속 받을지, 전체를 종료할지는 선택지인데, "빠르게 동작
                // 하는 것부터"라는 이번 과제 방침에 맞춰 상태 기계를 단순하게 유지
                //하기 위해 전체 입력을 종료하는 쪽을 택했다. 더 친절한 대안(이
                // 상품만 건너뛰고 다음 상품명부터 이어서 입력)은 추후 개선 지점으로
                // 남겨둔다.
                System.out.println(" -> 가격을 읽지 못해 입력을 종료합니다.");
                break;
            }

            Integer quantity = readInt("수량: ");
            if (quantity == null) {
                System.out.println(" -> 수량을 읽지 못해 입력을 종료합니다.");
                break;
            }

            try {
                CartItem item = new CartItem(name.trim(), price, quantity);
                items.add(item);
                System.out.println(" -> 담김: " + item);
            } catch (IllegalArgumentException e) {
                // CartItem 생성자의 검증(가격 음수, 수량 0 이하 등)에 걸린 경우.
                // 여기서는 프로그램을 죽이지 않고 같은 상품을 다시 입력받는다 -
                // 지금까지 담은 항목은 items에 그대로 남아 있으므로 영향이 없다.
                System.out.println(" -> 담기 실패: " + e.getMessage() + " 같은 상품을 다시 입력해 주세요.");
            }
        }

        return items;
    }

    /** 가격(정수, 원 단위) 입력을 받되 숫자가 아니면 최대 3회까지 재입력을 받는다. */
    private Long readLong(String prompt) {
        for (int attempt = 0; attempt < 3; attempt++) {
            System.out.print(prompt);
            String line = readLineOrNull();
            if (line == null) {
                return null; // 스트림이 끝났으면 더 재시도해 봐야 소용없으므로 즉시 포기
            }
            try {
                return Long.parseLong(line.trim());
            } catch (NumberFormatException e) {
                System.out.println("숫자로 입력해 주세요.");
            }
        }
        return null;
    }

    /** 수량(정수) 입력을 받되 숫자가 아니면 최대 3회까지 재입력을 받는다. */
    private Integer readInt(String prompt) {
        for (int attempt = 0; attempt < 3; attempt++) {
            System.out.print(prompt);
            String line = readLineOrNull();
            if (line == null) {
                return null;
            }
            try {
                return Integer.parseInt(line.trim());
            } catch (NumberFormatException e) {
                System.out.println("숫자로 입력해 주세요.");
            }
        }
        return null;
    }

    /**
     * Scanner.nextLine()을 감싸서, 입력 스트림이 예기치 않게 끝났을 때
     * (NoSuchElementException) 예외를 밖으로 던지는 대신 null을 반환한다. 호출부
     * (readCartItems/readLong/readInt)는 null을 "더 읽을 입력이 없음" 신호로
     * 해석해서 지금까지 모은 결과를 보존한 채 안전하게 종료한다.
     *
     * <p>nextInt()/nextDouble() 대신 항상 nextLine()으로만 읽고 직접 parseLong/
     * parseInt로 파싱하는 이유: nextInt() 계열은 숫자만 소비하고 그 뒤에 남은
     * 개행 문자를 버리지 않아서, 바로 다음에 호출한 nextLine()이 그 빈 줄을
     * 읽어버리는 전형적인 Scanner 버그(입력이 한 줄씩 밀리는 현상)가 생긴다.
     * nextLine()만 일관되게 쓰면 이 문제가 애초에 발생하지 않는다.
     */
    private String readLineOrNull() {
        try {
            return scanner.nextLine();
        } catch (NoSuchElementException e) {
            return null;
        }
    }
}
