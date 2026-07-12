/**
 * 온도 단위 문자열("C" 또는 "F")이 유효한지 검사하는 클래스.
 *
 * <p>TemperatureConverter가 변환을 수행하기 전에 이 클래스를 통해
 * 입력 단위를 먼저 검증한다. 현재 이 프로젝트에서 UnitValidator를
 * 사용하는 곳은 TemperatureConverter 한 곳뿐이라 fan-in(참조하는 곳의 수)은
 * 1이다. 즉 지금은 별도 인터페이스로 분리할 실익이 크지 않지만, 추후
 * 다른 클래스(예: 입력 폼 검증, 배치 파일 파싱 등)에서도 단위 검증이
 * 필요해져 fan-in이 늘어나면 그때는 인터페이스로 추출해
 * TemperatureConverter로부터 분리하는 것을 고려할 만하다.
 */
public class UnitValidator {

    private static final String CELSIUS = "C";
    private static final String FAHRENHEIT = "F";

    /**
     * 입력된 단위 문자열이 "C" 또는 "F"(대소문자, 앞뒤 공백 무관)인지 검사한다.
     *
     * @param unit 검사할 단위 문자열 (null 허용)
     * @return 유효하면 true, 아니면 false
     */
    public boolean isValid(String unit) {
        String normalized = normalize(unit);
        return CELSIUS.equals(normalized) || FAHRENHEIT.equals(normalized);
    }

    /**
     * 단위 문자열의 앞뒤 공백을 제거하고 대문자로 변환한다.
     * null이 들어오면 null을 그대로 반환한다.
     *
     * @param unit 원본 단위 문자열
     * @return 정규화된 단위 문자열 ("C", "F", 또는 그 외 대문자 값)
     */
    public String normalize(String unit) {
        if (unit == null) {
            return null;
        }
        return unit.trim().toUpperCase();
    }
}
