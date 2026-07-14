import java.util.List;
import java.util.Scanner;

/**
 * 프로그램 진입점. 각 클래스를 순서대로(입력 -> 계산 -> 경고 -> 출력) 호출해 연결한다.
 *
 * 클래스끼리 서로를 직접 참조하지 않고 List&lt;AttendanceRecord&gt; 하나만 주고받게
 * 설계했다 - AttendanceRateCalculator/LowAttendanceAlert/AttendanceSummaryReport는
 * 서로의 존재조차 모르고, 오직 Main이 이 순서로 호출해준다는 것에만 의존한다.
 * 지금은 "시간이 없어서 빠르게 동작하는 것부터" 만드는 단계라 이 정도의 단순한
 * 순차 파이프라인으로 충분하다고 판단했다. 요구사항에서 언급한 대로 클래스 간
 * 더 정교한 통합(예: 각 단계 실패 시 재시도, 이벤트 기반 연결 등)은 지금 범위에서는
 * 다루지 않았다.
 */
public class Main {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        AttendanceInputHandler inputHandler = new AttendanceInputHandler(scanner);
        AttendanceRateCalculator calculator = new AttendanceRateCalculator();
        LowAttendanceAlert alert = new LowAttendanceAlert();
        AttendanceSummaryReport report = new AttendanceSummaryReport();

        List<AttendanceRecord> records = inputHandler.readAll();

        calculator.calculateAll(records);
        alert.checkAndWarn(records);
        report.printAll(records);

        scanner.close();
    }
}
