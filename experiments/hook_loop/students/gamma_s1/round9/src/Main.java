import java.util.List;

/**
 * 프로그램 진입점.
 *
 * 클래스 간 통합은 최소한으로만 해뒀다 (인터페이스나 별도 컨트롤러 없이 Main에서
 * 순서대로 직접 호출). ReadingInputHandler -> ReadingLog -> AnomalyReport 순서로
 * List<SensorReading> 값 자체만 넘기고, 클래스끼리 서로 상속하거나 내부 필드에
 * 직접 접근하는 구조는 아니다(SensorReading이라는 DTO만 공유).
 * 시간이 없어서 이 이상의 통합(예: 공통 컨트롤러/서비스 클래스로 묶기,
 * 인터페이스로 추상화하기)은 지금 단계에서는 하지 않고 나중으로 미룬다.
 */
public class Main {
    public static void main(String[] args) {
        ReadingInputHandler inputHandler = new ReadingInputHandler();
        List<SensorReading> readings = inputHandler.collectReadings();

        ReadingLog log = new ReadingLog(readings);
        log.printAll();

        AnomalyReport report = new AnomalyReport(readings);
        report.printAnomalies();
    }
}
