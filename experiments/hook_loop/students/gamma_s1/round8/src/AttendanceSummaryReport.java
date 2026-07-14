import java.util.List;

/**
 * 전체 학생 명단과 출석률을 반복문으로 출력하는 클래스.
 *
 * (이 클래스는 Main만 호출한다 - fan-in 1. LowAttendanceAlert와 마찬가지로
 * "계산이 끝난 뒤 마지막 단계"에서만 쓰이도록 의도적으로 분리했다 - 출력
 * 형식만 바꾸고 싶을 때 경고 로직까지 건드리지 않아도 되게 하기 위해서다.)
 */
public class AttendanceSummaryReport {

    public void printAll(List<AttendanceRecord> records) {
        if (records == null) {
            throw new IllegalArgumentException("records가 null입니다.");
        }

        System.out.println("\n[전체 출석 명단]");
        System.out.printf("%-10s %8s %8s %10s%n", "이름", "출석일", "전체일", "출석률(%)");
        for (AttendanceRecord record : records) {
            System.out.printf("%-10s %8d %8d %9.1f%%%n",
                    record.getName(),
                    record.getDaysAttended(),
                    record.getTotalDays(),
                    record.getAttendanceRate());
        }
    }
}
