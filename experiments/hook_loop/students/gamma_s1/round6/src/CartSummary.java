import java.util.List;

/**
 * CartSummary - 담긴 상품 항목 수와 총 수량을 요약해서 출력한다.
 *
 * <p><b>"상품 수"의 정의(가정 사항 명시):</b> 이 클래스는 "상품 수"를 리스트에
 * 담긴 CartItem 엔트리(줄) 개수(items.size())로 계산한다. CartInputHandler는
 * 같은 상품명이 두 번 입력돼도 병합하지 않고 별도 항목으로 저장하므로(CartInputHandler
 * 클래스 주석 참고), 여기서도 "상품 수"는 서로 다른 상품명의 개수가 아니라 리스트의
 * 길이로 센다. 만약 "고유 상품명 개수"가 필요하다면 대안으로
 * {@code new java.util.HashSet<>(names).size()} 를 쓸 수 있지만, 그러려면 동일
 * 상품명의 수량을 합칠지/개별 유지할지 정책부터 정해야 하므로(HashSet은 정의상
 * 순서와 개별 라인 구분을 버린다) 이번 과제 범위에서는 다루지 않고 가정 사항으로만
 * 남겨 둔다.
 *
 * <p><b>의존 관계(fan-in=1, 의도된 설계):</b> Main만 이 클래스를 호출한다.
 * PriceCalculator/ReceiptPrinter와는 서로 참조하지 않는다 - 상품 개수·총 수량은
 * 금액 계산과 무관하게 List&lt;CartItem&gt;만 있으면 구할 수 있는 정보이므로, 굳이
 * PriceCalculator를 거치지 않고 CartItem 목록에서 직접 뽑아내도록 분리했다. 이렇게
 * 분리해 두면 "요약 출력 형식만 바꾸고 싶다" 같은 변경이 계산 로직(PriceCalculator)
 * 이나 영수증 출력(ReceiptPrinter)에 전혀 영향을 주지 않는다.
 *
 * <p><b>null 처리:</b> items가 null이면 상품 수/총 수량 모두 0으로 출력한다(예외를
 * 던지지 않음). CartInputHandler 계약상 null이 들어올 일은 없지만, 요약 출력
 * 하나 때문에 프로그램 전체가 죽는 것은 이 클래스의 책임 범위(요약 출력)를 넘어선다고
 * 판단해 방어적으로 처리했다 - PriceCalculator와 동일한 fail-safe 선택이다(그
 * 클래스의 트레이드오프 설명 참고).
 */
public class CartSummary {

    public void printSummary(List<CartItem> items) {
        int itemCount = (items == null) ? 0 : items.size();
        int totalQuantity = 0;

        if (items != null) {
            for (CartItem item : items) {
                totalQuantity += item.getQuantity(); // 연산자(+=)로 직접 누적
            }
        }

        System.out.println();
        System.out.println("=== 장바구니 요약 ===");
        System.out.println("담긴 상품 수(줄 수): " + itemCount + "개");
        System.out.println("총 수량: " + totalQuantity + "개");
    }
}
