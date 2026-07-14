import java.util.List;

/**
 * 이상치로 판정된 측정값만 골라 출력하는 클래스.
 */
public class AnomalyReport {

    // 아래 임계값은 실측 데이터로 산출한 게 아니라 "실험실이면 이 정도가 정상 범위겠지"라는
    // 가정치다. 데이터 기반으로 다시 잡아야 하는 값이라 TODO로 남겨둠(지금은 시간이 없어서
    // 임의값으로 진행하되, 이게 임의값이라는 사실 자체는 숨기지 않고 주석에 명시).
    //
    // ReadingValidator의 -273~1000(온도) / 0~100(습도) 범위와는 기준이 다르다:
    // 그쪽은 "자료형/물리적으로 있을 수 있는 값"인지를 보고, 여기는 그 중에서도
    // "실험실 환경에서 정상으로 볼 값"인지를 다시 본다. 기준의 성격이 달라서
    // 클래스도 ReadingValidator와 분리해뒀다(하나의 메서드에서 두 기준을 같이
    // 검사하면 나중에 이상치 기준만 바뀔 때 ReadingValidator까지 손대야 하기 때문).
    private static final double TEMP_MIN = 15.0;
    private static final double TEMP_MAX = 30.0;
    private static final int HUMIDITY_MIN = 20;
    private static final int HUMIDITY_MAX = 80;

    private List<SensorReading> readings;

    public AnomalyReport(List<SensorReading> readings) {
        // readings가 null로 들어오면 printAnomalies()의 for-each에서 바로
        // NullPointerException이 난다. 지금 흐름(Main -> ReadingInputHandler.collectReadings()
        // -> 항상 빈 ArrayList 이상을 반환)에서는 null이 들어올 경로가 없어서 당장은
        // 문제가 안 되지만, 이 생성자만 따로 떼어 다른 곳(예: 나중에 추가할 테스트 코드)에서
        // 호출하면 위험할 수 있다. 방어 코드(null 체크)는 아직 넣지 않았고, 클래스 통합을
        // 다시 볼 때 ReadingLog와 함께 같이 보강할 계획이다.
        this.readings = readings;
    }

    public void printAnomalies() {
        System.out.println("=== 이상치 판정 결과 ===");

        boolean found = false;
        for (SensorReading reading : readings) {
            if (isAnomaly(reading)) {
                System.out.println("[이상치] " + reading);
                found = true;
            }
        }

        if (!found) {
            System.out.println("이상치가 발견되지 않았습니다.");
        }
        System.out.println();
    }

    private boolean isAnomaly(SensorReading reading) {
        double temp = reading.getTemperature();
        int humidity = reading.getHumidity();
        return temp < TEMP_MIN || temp > TEMP_MAX || humidity < HUMIDITY_MIN || humidity > HUMIDITY_MAX;
    }
}
