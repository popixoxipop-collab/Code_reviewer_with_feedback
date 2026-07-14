import java.util.List;

/**
 * 전체 측정 로그를 순서대로 출력하는 클래스.
 *
 * AnomalyReport와 마찬가지로 readings가 null이면 printAll()의 for-each에서
 * NullPointerException이 날 수 있다. 같은 위험을 두 클래스에 각각 길게 적기보다
 * AnomalyReport 쪽 주석에 대표로 자세히 적어뒀다 - 원인과 설계 의도는 동일함.
 */
public class ReadingLog {

    private List<SensorReading> readings;

    public ReadingLog(List<SensorReading> readings) {
        this.readings = readings;
    }

    public void printAll() {
        System.out.println("=== 전체 측정 로그 ===");
        int index = 1;
        for (SensorReading reading : readings) {
            System.out.println(index + ". " + reading);
            index++;
        }
        System.out.println("총 " + readings.size() + "건 기록됨\n");
    }
}
