import java.util.List;

/**
 * 출석률이 기준(80%) 미만인 학생을 반복문으로 탐색해 경고를 출력하는 클래스.
 *
 * AttendanceRateCalculator.calculateAll()이 먼저 실행되어 있어야
 * record.getAttendanceRate()가 의미 있는 값이므로, Main에서의 호출 순서
 * (계산 -> 경고)에 의존한다. 이 클래스 자체는 그 순서를 강제하지 않는데,
 * "계산이 안 된 record는 0.0으로 취급되어 오히려 경고 대상에 포함될 뿐"이라
 * 조용히 틀린 결과를 낼 위험은 낮지만, 순서가 바뀌면 의미가 달라진다는 점은
 * Main 쪽 주석에도 남겨 둔다.
 * (이 클래스는 Main만 호출한다 - fan-in 1. LowAttendanceAlert와
 * AttendanceSummaryReport는 둘 다 "계산이 끝난 뒤 마지막 단계에서만" 쓰이므로
 * 의도적으로 별도 클래스로 분리했다 - 기준 미달 탐색 로직이 나중에 바뀌어도
 * 명단 전체 출력 로직에는 영향이 없게 하기 위해서다.)
 */
public class LowAttendanceAlert {
    private static final double THRESHOLD_PERCENT = 80.0;

    public void checkAndWarn(List<AttendanceRecord> records) {
        if (records == null) {
            throw new IllegalArgumentException("records가 null입니다.");
        }

        System.out.println("\n[출석률 미달 경고 - 기준 " + THRESHOLD_PERCENT + "%]");
        boolean anyWarning = false;
        for (AttendanceRecord record : records) {
            if (record.getAttendanceRate() < THRESHOLD_PERCENT) {
                System.out.printf("경고: %s 학생 출석률 %.1f%% (기준 미달)%n",
                        record.getName(), record.getAttendanceRate());
                anyWarning = true;
            }
        }
        if (!anyWarning) {
            System.out.println("기준 미달 학생이 없습니다.");
        }
    }
}
