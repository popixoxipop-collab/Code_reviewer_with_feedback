/**
 * 입력 문자열을 실제 자료형(double/int)으로 변환하고, 그 값이 유효한 범위인지
 * 검증하는 클래스.
 *
 * [fan-in 안내]
 * 현재 이 클래스를 호출하는 곳은 ReadingInputHandler 하나뿐이다 (fan-in = 1).
 * 그래도 검증 로직을 ReadingInputHandler 안에 인라인으로 두지 않고 별도 클래스로 뺀 이유는,
 * "입력을 어떻게 받을지"와 "받은 값이 유효한지 판단하는 규칙"을 처음부터 분리해두기 위함.
 * 나중에 입력 경로가 늘어나면(예: 파일에서 읽기, 테스트 코드에서 직접 검증만 호출) 이 클래스를
 * 그대로 재사용할 수 있게 하려는 의도이고, 지금 당장 재사용되지 않는다고 해서
 * 우연히 fan-in=1이 된 것은 아니다.
 */
public class ReadingValidator {

    /**
     * 습도 문자열 -> int 형변환 + 0~100 범위 검증.
     *
     * Integer.parseInt는 "23.5"처럼 소수점이 섞인 문자열이나, int 표현 범위를 넘는
     * 큰 수(예: "99999999999")에 대해서도 NumberFormatException을 던진다.
     * 즉 "형변환 자체가 실패하는 경우"와 "형변환은 되지만 범위(0~100)를 벗어나는 경우"를
     * 이 메서드 하나에서 함께 처리해서, 호출하는 쪽(ReadingInputHandler)이 두 번 나눠
     * 검사하지 않아도 되게 만들었다.
     *
     * 참고로 여기서는 소수점이 섞인 습도(예: "55.5")를 반올림/절삭해서 받아주지 않고
     * 그냥 무효 처리한다. Double로 먼저 파싱한 뒤 (int)로 캐스팅해서 받아주는 방법도
     * 있었지만, 그러면 습도가 소수점까지 정밀하게 들어왔다는 신호를 자른 채로 조용히
     * 정수로 뭉개버리게 되어(형변환 과정에서 정보 손실이 드러나지 않음) 오히려 값을
     * 신뢰하기 어려워진다고 판단해서, 정수 형식이 아니면 아예 거부하는 쪽을 택했다.
     */
    public static boolean isValidHumidity(String rawHumidity) {
        if (rawHumidity == null) {
            // ReadingInputHandler는 Scanner.nextLine() 결과에 .trim()만 해서 넘기기 때문에
            // 현재 호출 경로에서 null이 들어올 일은 없다. 다만 이 메서드가 다른 입력 경로
            // (예: 파일에서 읽은 값)에서도 재사용될 가능성을 열어뒀기 때문에 방어적으로 처리해둠.
            return false;
        }
        int humidity;
        try {
            humidity = Integer.parseInt(rawHumidity);
        } catch (NumberFormatException e) {
            return false;
        }
        return humidity >= 0 && humidity <= 100;
    }

    /**
     * 온도 문자열 -> double 형변환 + 물리적으로 가능한 범위 검증.
     *
     * 여기서 말하는 범위(-273 ~ 1000)는 "자료형/물리적으로 있을 수 있는 값"인지만
     * 걸러내는 용도다. "실험실 환경에서 정상적인 값"인지는 별도 기준(AnomalyReport)이
     * 다시 판단한다. 두 검증을 한 메서드에 합치지 않은 이유: 이 클래스는 "입력이
     * 자료형으로서 유효한 값인가"만 책임지고, "유효하지만 통계적으로 이상한 값인가"는
     * AnomalyReport의 책임으로 나눠서, 나중에 이상치 판정 기준만 바뀌어도 이 클래스는
     * 건드릴 필요가 없게 하기 위함이다.
     */
    public static boolean isValidTemperature(String rawTemperature) {
        if (rawTemperature == null) {
            return false;
        }
        double temperature;
        try {
            temperature = Double.parseDouble(rawTemperature);
        } catch (NumberFormatException e) {
            return false;
        }
        return temperature >= -273.0 && temperature <= 1000.0;
    }
}
