import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

/**
 * 여러 학생의 출석 정보를 반복 입력받는 클래스 (Scanner 사용).
 *
 * Scanner를 생성자로 주입받아 재사용한다. System.in을 감싸는 Scanner를 클래스마다
 * 새로 만들면 내부 버퍼가 꼬일 수 있어서, Main이 하나만 만들어 전달하는 구조로 했다.
 * (이 클래스는 Main만 사용한다 - fan-in 1. 지금 요구사항에서는 "표준입력으로부터
 * 학생 명단을 만든다"는 역할이 프로그램 시작 지점 한 곳에서만 필요해서, 의도적으로
 * Main 전용으로만 연결했고 별도 인터페이스로 추상화하지는 않았다.)
 */
public class AttendanceInputHandler {
    private final Scanner scanner;

    public AttendanceInputHandler(Scanner scanner) {
        this.scanner = scanner;
    }

    /**
     * 학생 수를 먼저 입력받고, 그 수만큼 반복하여 이름/전체일수/출석일수를 입력받는다.
     * 반환하는 List&lt;AttendanceRecord&gt;는 이후 AttendanceRateCalculator,
     * LowAttendanceAlert, AttendanceSummaryReport가 공통으로 주고받는 데이터
     * 전달 객체(DTO) 역할을 한다 - 각 클래스는 이 리스트와 AttendanceRecord의
     * getter/setter만 알면 되고, 서로의 내부 구현에는 의존하지 않는다.
     */
    public List<AttendanceRecord> readAll() {
        List<AttendanceRecord> records = new ArrayList<>();

        System.out.print("입력할 학생 수: ");
        int studentCount = readPositiveInt("학생 수는 1 이상의 숫자로 입력해주세요: ");

        for (int i = 0; i < studentCount; i++) {
            System.out.println("\n[" + (i + 1) + "번째 학생]");
            records.add(readOneRecord());
        }

        return records;
    }

    private AttendanceRecord readOneRecord() {
        System.out.print("이름: ");
        String name = scanner.nextLine().trim();
        while (name.isEmpty()) {
            // 이름이 빈 문자열이면 AttendanceSummaryReport의 %-10s 출력이 비어 보여
            // 어떤 학생인지 알 수 없게 되므로, 입력 단계에서 미리 막는다.
            System.out.print("이름은 비워둘 수 없습니다. 다시 입력: ");
            name = scanner.nextLine().trim();
        }

        System.out.print("전체일수: ");
        int totalDays = readPositiveInt("전체일수는 1 이상의 숫자로 입력해주세요: ");

        System.out.print("출석일수(0~" + totalDays + "): ");
        int daysAttended = readDaysAttended(totalDays);

        return new AttendanceRecord(name, daysAttended, totalDays);
    }

    /**
     * 1 이상의 정수를 받을 때까지 반복 요청한다.
     * nextInt()만 쓰면 숫자 뒤 개행 문자가 버퍼에 남아 다음 nextLine() 호출이
     * 빈 문자열을 읽어버리는 전형적인 실수가 생기기 때문에, 항상 nextLine()으로
     * 줄 전체를 읽고 직접 파싱하는 방식으로 통일했다.
     */
    private int readPositiveInt(String retryMessage) {
        while (true) {
            String line = scanner.nextLine().trim();
            try {
                int value = Integer.parseInt(line);
                if (value > 0) {
                    return value;
                }
            } catch (NumberFormatException ignored) {
                // 숫자가 아니면 아래 재입력 메시지로 통일 처리
            }
            System.out.print(retryMessage);
        }
    }

    /**
     * 0 이상 totalDays 이하의 정수를 받을 때까지 반복 요청한다.
     * 이 범위를 여기서 강제해두면, AttendanceRateCalculator가 계산하는 출석률은
     * 항상 0~100% 사이 값이 되어 이후 LowAttendanceAlert/AttendanceSummaryReport
     * 쪽에서 범위를 벗어난 값(예: 150%)을 다시 검증할 필요가 없어진다.
     */
    private int readDaysAttended(int totalDays) {
        while (true) {
            String line = scanner.nextLine().trim();
            try {
                int value = Integer.parseInt(line);
                if (value >= 0 && value <= totalDays) {
                    return value;
                }
            } catch (NumberFormatException ignored) {
                // 숫자가 아니면 아래 재입력 메시지로 통일 처리
            }
            System.out.print("출석일수는 0~" + totalDays + " 사이의 숫자로 입력해주세요: ");
        }
    }
}
