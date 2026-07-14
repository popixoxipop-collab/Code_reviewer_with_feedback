/**
 * 학생 한 명의 출석 정보를 담는 모델 클래스.
 *
 * AttendanceInputHandler가 생성하고, AttendanceRateCalculator / LowAttendanceAlert /
 * AttendanceSummaryReport / Main까지 총 5개 클래스가 함께 참조하는 공유 데이터 구조다.
 * 여러 곳에서 쓰이는 만큼 필드를 직접 노출하지 않고 getter/setter로만 접근하게 했다.
 * 나중에 내부 표현(예: 필드 타입, 저장 방식)이 바뀌어도 이 getter/setter 시그니처만
 * 유지하면 사용하는 4개 클래스를 고치지 않아도 된다.
 */
public class AttendanceRecord {
    private final String name;
    private final int daysAttended;
    private final int totalDays;

    // 계산 전에는 0.0으로 비워두고, AttendanceRateCalculator.calculateAll()이 채운다.
    // (calculateAll을 호출하기 전에 getAttendanceRate()를 부르면 0.0이 나온다는 뜻이므로,
    // Main에서의 호출 순서 - 계산 후 조회 - 가 지켜져야 의미 있는 값이 된다.)
    private double attendanceRate;

    /**
     * @param name         학생 이름 (null/빈 문자열 여부는 AttendanceInputHandler가 입력 단계에서 걸러준다.
     *                     이 생성자 자체는 방어 코드를 넣지 않고 신뢰할 수 있는 값이 들어온다고 가정한다 -
     *                     단순 데이터 보관 클래스에 검증 로직까지 넣으면 책임이 섞이기 때문)
     * @param daysAttended 출석일수 (0 이상, totalDays 이하를 가정)
     * @param totalDays    전체일수 (1 이상을 가정)
     *
     *                     daysAttended/totalDays를 int로 둔 이유: 한 학기 수업일수는 많아야
     *                     수백 일 수준이라 int(약 ±21억) 범위 안에서 오버플로우가 날 수 없다.
     *                     long으로 하면 안전 여유는 커지지만 학생 수 x 필드 수만큼 메모리만
     *                     더 쓰고 가독성만 떨어지므로, 이 도메인에서는 int가 더 적절한 선택이다.
     */
    public AttendanceRecord(String name, int daysAttended, int totalDays) {
        this.name = name;
        this.daysAttended = daysAttended;
        this.totalDays = totalDays;
    }

    public String getName() {
        return name;
    }

    public int getDaysAttended() {
        return daysAttended;
    }

    public int getTotalDays() {
        return totalDays;
    }

    public double getAttendanceRate() {
        return attendanceRate;
    }

    public void setAttendanceRate(double attendanceRate) {
        this.attendanceRate = attendanceRate;
    }
}
