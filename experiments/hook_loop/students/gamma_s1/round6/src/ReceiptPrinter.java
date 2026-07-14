import java.util.List;

/**
 * ReceiptPrinter - 계산된 금액과 상품 목록을 받아 영수증 형태로 출력한다.
 *
 * <p><b>의존 관계(fan-in=1, 의도된 설계):</b> Main만 이 클래스를 호출한다. 이
 * 클래스는 PriceCalculator를 필드로 갖거나 직접 호출하지 않는다 - 대신 Main이
 * PriceCalculator로 미리 계산한 subtotal/vat/discount/total 값을 long 파라미터로
 * 그대로 넘겨받는다.
 *
 * <p><b>공유 컴포넌트(PriceCalculator)의 내부 구현에 의존하지 않는 이유:</b> 만약
 * 이 클래스가 PriceCalculator 인스턴스를 들고 있다가 내부에서 calculateVat() 등을
 * 직접 다시 호출하는 방식이었다면, PriceCalculator의 계산 방식이 바뀔 때마다(예:
 * 할인 정책이 정률에서 정액으로 바뀌거나, 세율이 국가별로 달라지는 경우) 이 클래스도
 * 함께 수정되거나 최소한 재검토해야 했을 것이다. 대신 "이미 계산된 숫자 4개"만
 * 데이터로 주고받는 형태로 인터페이스를 좁혀 두면, PriceCalculator 내부 구현이
 * 통째로 바뀌어도(심지어 PriceCalculator가 다른 클래스로 완전히 대체되어도) 이
 * 클래스는 printReceipt(List, long, long, long, long) 시그니처가 유지되는 한 코드를
 * 한 줄도 바꿀 필요가 없다. 계산 로직과 표시 로직 사이의 의존성을 데이터 전달만으로
 * 격리한 것이다.
 *
 * <p><b>알려진 표시상 한계:</b> String.format의 %s/%-20s 같은 폭 지정은 문자
 * "개수" 기준이라, 한글(가변폭 없이 터미널에서 보통 2칸을 차지)이 섞인 상품명이
 * 길어지면 표 정렬이 완벽히 맞지 않을 수 있다. 계산 값 자체에는 영향이 없는
 * 순수 출력 정렬 문제라 이번 범위에서는 감수했다.
 */
public class ReceiptPrinter {

    public void printReceipt(List<CartItem> items, long subtotal, long vat, long discount, long total) {
        System.out.println();
        System.out.println("==================== 영 수 증 ====================");
        System.out.printf("%-20s %8s %6s %12s%n", "상품명", "단가", "수량", "금액");
        System.out.println("----------------------------------------------------");

        if (items == null || items.isEmpty()) {
            System.out.println("담긴 상품이 없습니다.");
        } else {
            for (CartItem item : items) {
                System.out.printf("%-20s %8d %6d %12d%n",
                        item.getName(), item.getPrice(), item.getQuantity(), item.lineTotal());
            }
        }

        System.out.println("----------------------------------------------------");
        System.out.printf("%-20s %20d원%n", "소계", subtotal);
        System.out.printf("%-20s %20d원%n", "부가세(10%)", vat);
        System.out.printf("%-20s %20d원%n", "할인", -discount);
        System.out.println("----------------------------------------------------");
        System.out.printf("%-20s %20d원%n", "결제 금액", total);
        System.out.println("====================================================");
    }
}
