import java.util.List;

/**
 * 학생 리스트를 반복문으로 순회하며 각자의 출석률(%)을 계산해
 * AttendanceRecord에 채워 넣는 클래스.
 *
 * List&lt;AttendanceRecord&gt;라는 데이터 전달 객체를 통해서만 AttendanceRecord와
 * 상호작용하고, AttendanceInputHandler가 이 리스트를 어떻게 만들었는지,
 * LowAttendanceAlert/AttendanceSummaryReport가 이 리스트를 어떻게 쓰는지는
 * 전혀 몰라도 동작한다 - 그래야 그쪽 구현이 바뀌어도 이 클래스는 안 바뀐다.
 * (Main만 이 클래스를 호출한다 - fan-in 1. 지금 요구사항엔 계산 로직이 이
 * 파이프라인 밖에서 재사용될 일이 없어서 의도적으로 Main 전용으로만 연결했다.)
 */
public class AttendanceRateCalculator {

    /**
     * records를 순회하며 각 AttendanceRecord의 attendanceRate 필드를 채운다.
     * (in-place로 값을 채워 넣는 방식을 택했다 - 새 리스트를 만들어 반환하면
     * 호출부에서 "원본 records"와 "결과 records" 두 개를 헷갈릴 위험이 있고,
     * 학생 수만큼 객체를 복제하는 비용도 없앨 수 있기 때문이다.)
     */
    public void calculateAll(List<AttendanceRecord> records) {
        if (records == null) {
            // 아래 for-each에서 NullPointerException으로 터지면 원인 파악이 어려우므로
            // null이 들어온 시점에 바로 명확한 예외로 알린다.
            throw new IllegalArgumentException("records가 null입니다.");
        }

        for (AttendanceRecord record : records) {
            record.setAttendanceRate(calculateRate(record));
        }
    }

    private double calculateRate(AttendanceRecord record) {
        int totalDays = record.getTotalDays();
        if (totalDays <= 0) {
            // AttendanceInputHandler를 거친 정상 입력에서는 totalDays가 항상 1 이상이라
            // 이 분기는 지금 경로에서는 실행되지 않는다. 다만 이 클래스는 어떤
            // records가 들어와도 나눗셈 자체가 안전해야 하므로(0으로 나누면
            // ArithmeticException 대신 Double.NaN/Infinity가 조용히 퍼질 수 있음),
            // 방어적으로 0%를 반환해 잘못된 값이 이후 경고/출력 단계로 전파되지 않게 한다.
            return 0.0;
        }
        return (record.getDaysAttended() / (double) totalDays) * 100.0;
    }
}
