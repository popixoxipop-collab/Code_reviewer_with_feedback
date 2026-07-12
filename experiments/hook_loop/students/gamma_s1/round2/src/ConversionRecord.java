/**
 * 변환 1건의 결과를 담는 불변(immutable) 데이터 클래스.
 *
 * <p>원본 값/단위와 결과 값/단위를 함께 저장한다. 필드를 모두 final로
 * 선언하고 setter를 두지 않은 이유는, ConversionHistory가 쌓아 두는
 * 이력(로그)은 한 번 기록되면 이후 바뀌면 안 되는 값이기 때문이다.
 * 만약 가변(mutable) 객체로 만들면 ConversionHistory 밖에서 record를
 * 참조하는 코드가 실수로 과거 이력의 값을 바꿔버릴 위험이 있다 —
 * 이력의 정확성(accuracy)을 지키기 위한 설계다.
 *
 * <p>값 타입으로 double을 쓰는 이유는 TemperatureConverter와 동일하다:
 * 온도는 본질적으로 소수 값이고, 변환 공식(9/5, 5/9)이 정수 나눗셈으로는
 * 정확히 표현되지 않기 때문이다.
 */
public final class ConversionRecord {

    private final double originalValue;
    private final String originalUnit;
    private final double convertedValue;
    private final String convertedUnit;

    public ConversionRecord(double originalValue, String originalUnit,
                             double convertedValue, String convertedUnit) {
        this.originalValue = originalValue;
        this.originalUnit = originalUnit;
        this.convertedValue = convertedValue;
        this.convertedUnit = convertedUnit;
    }

    public double getOriginalValue() {
        return originalValue;
    }

    public String getOriginalUnit() {
        return originalUnit;
    }

    public double getConvertedValue() {
        return convertedValue;
    }

    public String getConvertedUnit() {
        return convertedUnit;
    }

    @Override
    public String toString() {
        return String.format("%.2f%s -> %.2f%s",
                originalValue, originalUnit, convertedValue, convertedUnit);
    }
}
