/**
 * 섭씨/화씨 상호 변환을 담당하는 클래스.
 *
 * <p>내부적으로 UnitValidator를 사용해 변환 전에 입력 단위가 "C" 또는
 * "F"인지 먼저 검사한다. 단위가 유효하지 않으면 IllegalArgumentException을
 * 던져 호출자(Main)가 사용자에게 잘못된 입력임을 알리고 다시 입력받을 수
 * 있게 한다.
 *
 * <p>변환 대상 값의 타입으로 int가 아닌 double을 쓴 이유:
 * <ul>
 *   <li>정확도(accuracy) 제약: F = C * 9/5 + 32 공식에서 9/5를 정수
 *       나눗셈으로 계산하면 1(0.8이 아니라)이 되어 결과가 완전히
 *       틀어진다. 소수점 이하 값을 다루려면 부동소수 타입이 필수다.</li>
 *   <li>입력 자체도 36.5도, -12.3도처럼 정수가 아닌 경우가 흔하므로,
 *       애초에 int로는 사용자의 입력 범위를 다 담을 수 없다.</li>
 *   <li>성능(performance) 관점에서는 이 프로그램이 사용자가 콘솔에서
 *       입력하는 값을 1건씩 처리하는 수준이라 double 연산의 오버헤드는
 *       무시할 수 있다. 즉 정확도를 얻기 위해 int 대비 치러야 하는 성능
 *       비용은 이 시스템 규모에서는 사실상 없다.</li>
 * </ul>
 */
public class TemperatureConverter {

    private static final double CELSIUS_TO_FAHRENHEIT_RATIO = 9.0 / 5.0;
    private static final double FAHRENHEIT_TO_CELSIUS_RATIO = 5.0 / 9.0;
    private static final double FAHRENHEIT_OFFSET = 32.0;

    private final UnitValidator unitValidator;

    public TemperatureConverter() {
        this.unitValidator = new UnitValidator();
    }

    /**
     * 주어진 값을 fromUnit 기준으로 변환한다.
     * fromUnit이 "C"면 섭씨-&gt;화씨, "F"면 화씨-&gt;섭씨로 변환 방향이
     * 자동으로 결정된다.
     *
     * @param value    변환할 온도 값
     * @param fromUnit 입력 값의 단위 ("C" 또는 "F", 대소문자/공백 무관)
     * @return 원본 값/단위와 변환 결과 값/단위를 담은 ConversionRecord
     * @throws IllegalArgumentException fromUnit이 "C"/"F"가 아닐 때
     */
    public ConversionRecord convert(double value, String fromUnit) {
        String unit = unitValidator.normalize(fromUnit);
        if (!unitValidator.isValid(unit)) {
            throw new IllegalArgumentException(
                    "잘못된 단위입니다: \"" + fromUnit + "\" (\"C\" 또는 \"F\"만 허용됩니다)");
        }

        if (unit.equals("C")) {
            double converted = celsiusToFahrenheit(value);
            return new ConversionRecord(value, "C", converted, "F");
        } else {
            double converted = fahrenheitToCelsius(value);
            return new ConversionRecord(value, "F", converted, "C");
        }
    }

    private double celsiusToFahrenheit(double celsius) {
        return celsius * CELSIUS_TO_FAHRENHEIT_RATIO + FAHRENHEIT_OFFSET;
    }

    private double fahrenheitToCelsius(double fahrenheit) {
        return (fahrenheit - FAHRENHEIT_OFFSET) * FAHRENHEIT_TO_CELSIUS_RATIO;
    }
}
