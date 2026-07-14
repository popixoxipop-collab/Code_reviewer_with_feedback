import java.util.List;

/**
 * PriceCalculator - CartItem 목록으로부터 소계/부가세(10%)/할인 금액을 연산자
 * (+, -, *, /에 해당하는 +=, *)로 직접 계산한다.
 *
 * <p><b>의존 관계(fan-in=1, 의도된 설계):</b> 이 클래스를 직접 호출하는 곳은 Main
 * 뿐이다. ReceiptPrinter나 CartSummary는 PriceCalculator를 참조하지 않는다 - Main이
 * 계산 결과(long 값 4개: subtotal/vat/discount/total)를 꺼내서 다음 클래스로
 * 넘겨준다. 계산 로직을 입력·출력과 분리해두면, 할인 정책이 바뀌어도(예: 정률에서
 * 정액으로, 또는 쿠폰 조합으로) 이 클래스 내부만 고치면 되고 ReceiptPrinter/
 * CartSummary는 전혀 건드릴 필요가 없다. 반대로 ReceiptPrinter의 출력 포맷이
 * 바뀌어도 이 클래스는 영향받지 않는다. 즉 fan-in=1은 "아직 다른 곳에서 안 써서"가
 * 아니라, 계산 로직을 표시 로직과 결합시키지 않기 위해 의도적으로 좁힌 것이다.
 *
 * <p><b>공유 컴포넌트(CartItem)에 대한 의존 격리:</b> 이 클래스는 CartItem의 필드에
 * 직접 접근하지 않고 getPrice()/getQuantity() getter만 사용한다(=CartItem의 내부
 * 구현이 아니라 getter라는 인터페이스에만 의존). CartItem의 내부 표현이 나중에
 * 바뀌어도(예: price를 long에서 BigDecimal로 바꾸는 큰 리팩터링을 하더라도 getter
 * 시그니처만 유지된다면) 이 클래스는 재컴파일만 하면 되고 계산 로직을 다시 쓸 필요가
 * 없다.
 *
 * <p><b>null/빈 리스트 처리:</b> items가 null이면 정상적인 프로그램 흐름에서는
 * 발생하지 않는다 - CartInputHandler.readCartItems()는 항상 null이 아닌 리스트를
 * 반환하도록 계약되어 있다(CartInputHandler 클래스 주석 참고). 그럼에도 이 클래스를
 * CartInputHandler 없이 단독으로(예: 테스트 코드) 호출할 가능성을 고려해, null이
 * 들어오면 예외를 던지는 대신 0을 반환하는 fail-safe 방식을 택했다.
 * 트레이드오프: fail-fast(NullPointerException을 그대로 던짐)는 버그를 더 빨리,
 * 더 정확한 지점에서 드러내는 장점이 있다. 반면 이 프로그램은 계산 -&gt; 영수증
 * 출력 -&gt; 요약 출력까지 한 번에 이어지는 짧은 흐름이라, 중간에 예외로 죽는 것보다
 * "0원으로 계산되어 화면에 그대로 드러나는" 쪽이 실행 결과를 보면서 바로 이상 여부를
 * 알아채기 쉽다고 판단해 fail-safe를 선택했다. 실무 결제 시스템이었다면 금액 계산이
 * 조용히 0을 반환하는 것은 예외를 삼켜 버그를 숨기는 위험한 선택이므로 fail-fast를
 * 썼을 것이다.
 */
public class PriceCalculator {

    /** 부가세율 10%. */
    private static final double VAT_RATE = 0.10;

    /** 소계 50,000원 이상 구매 시 적용하는 할인율(아래 calculateDiscount 설명 참고). */
    private static final long DISCOUNT_THRESHOLD = 50_000L;
    private static final double DISCOUNT_RATE = 0.05;

    /** 소계 = 모든 항목의 (단가 x 수량)의 합. */
    public long calculateSubtotal(List<CartItem> items) {
        if (items == null || items.isEmpty()) {
            return 0L;
        }
        long subtotal = 0L;
        for (CartItem item : items) {
            subtotal += item.getPrice() * item.getQuantity(); // 연산자(*, +=)로 직접 계산
        }
        return subtotal;
    }

    /**
     * 부가세 = 소계 x 10%. subtotal(long) x VAT_RATE(double) 연산 결과는 double이
     * 되므로, 원 단위로 반올림하기 위해 Math.round()를 사용한다. 절사(내림)나
     * 절상(올림) 대신 반올림을 택한 이유는, 소계가 10원 단위로 딱 나누어떨어지지
     * 않는 경우에도 오차를 ±1원 이내로 최소화하기 위함이다(정확도 우선 - 이 값이
     * 그대로 영수증 합계/결제 금액에 들어가므로 절사로 인해 결제 금액이 실제 세액보다
     * 체계적으로 낮게 나오는 편향을 피하고 싶었다).
     */
    public long calculateVat(long subtotal) {
        return Math.round(subtotal * VAT_RATE);
    }

    /**
     * 할인 금액. 이 과제 지문은 구체적인 할인 정책(정률/정액/쿠폰 등)을 명시하지
     * 않았으므로, 예시로 다음 정책을 가정해 구현했다: 소계 50,000원 이상이면 5%
     * 할인, 미만이면 할인 없음. 이 규칙은 자리표시(placeholder) 성격이 강하다는
     * 점을 명시해 둔다. 이 메서드가 "long을 돌려준다"는 계약만 지키면 호출부인
     * Main과, Main으로부터 결과를 전달받는 ReceiptPrinter는 전혀 수정할 필요가
     * 없으므로, 실제 할인 정책이 정해지면 이 메서드 내부만 교체하면 된다.
     */
    public long calculateDiscount(long subtotal) {
        if (subtotal < DISCOUNT_THRESHOLD) {
            return 0L;
        }
        return Math.round(subtotal * DISCOUNT_RATE);
    }

    /** 최종 결제 금액 = 소계 + 부가세 - 할인. */
    public long calculateTotal(long subtotal, long vat, long discount) {
        return subtotal + vat - discount;
    }
}
