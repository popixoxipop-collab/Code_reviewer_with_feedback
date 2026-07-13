import java.util.List;

/**
 * 학생 목록의 키 평균/최고/최저를 계산하는 클래스.
 *
 * HeightSummary와 Main에서 함께 쓰이는 소규모 공유 컴포넌트다(fan_in=2).
 * 통계 계산 로직을 이 클래스 하나로 모아 두어, HeightSummary 같은 소비 클래스가
 * 평균/최댓값/최솟값 계산 방식을 각자 재구현하지 않도록 한다. 공유 지점이
 * 늘어날수록(fan_in 증가) 계산 규칙 변경이 여러 곳에 영향을 주므로,
 * 계산 규칙을 바꿔야 한다면 반드시 이 클래스 안에서만 바꾼다.
 */
public class HeightAnalyzer {

    private final List<StudentProfile> profiles;

    public HeightAnalyzer(List<StudentProfile> profiles) {
        this.profiles = profiles;
    }

    /**
     * 평균 키를 계산한다.
     *
     * [타입 선택 근거] 누적 변수 total은 int가 아니라 double을 사용한다.
     * - StudentProfile.height가 double(예: 172.5cm처럼 소수점을 가질 수 있음)이므로
     *   total을 int로 선언하면 더할 때마다 소수부가 잘려나가 평균이 부정확해진다.
     *   즉 여기서 double을 쓰는 근본 이유는 "오버플로우 회피"가 아니라
     *   "소수 정밀도 보존"이다 — 이 두 근거를 섞어서 설명하지 않도록 주의한다.
     * - 오버플로우만 놓고 보면, 이 프로그램이 다루는 입력 규모(학급 단위,
     *   많아야 수백 명 * 키 250cm 이하)에서는 int로 누적해도 int 범위
     *   (약 ±21억)에 전혀 근접하지 않는다. 즉 정수 오버플로우는 이 프로그램에서
     *   double을 선택한 실질적 근거가 아니며, "정수 범위 제약과 연결된다"고
     *   말하려면 학생 수나 키 값이 지금과는 비교가 안 될 정도로 커야 한다.
     *   지금은 그런 조건이 아니라는 점을 분명히 해 둔다.
     * - 성능 측면에서는 int 누적이 double 누적보다 근소하게 빠를 수 있지만,
     *   이 프로그램 규모(학급 단위 리스트 순회)에서는 체감 차이가 없고,
     *   그 미세한 이득이 소수점 정밀도 손실이라는 더 큰 비용을 정당화하지 못한다.
     *   따라서 정확도를 우선해 double을 선택한다.
     */
    public double calculateAverage() {
        if (profiles.isEmpty()) {
            return 0.0;
        }
        double total = 0.0;
        for (StudentProfile profile : profiles) {
            total += profile.getHeight();
        }
        return total / profiles.size();
    }

    public double findMax() {
        if (profiles.isEmpty()) {
            return 0.0;
        }
        double max = profiles.get(0).getHeight();
        for (StudentProfile profile : profiles) {
            if (profile.getHeight() > max) {
                max = profile.getHeight();
            }
        }
        return max;
    }

    public double findMin() {
        if (profiles.isEmpty()) {
            return 0.0;
        }
        double min = profiles.get(0).getHeight();
        for (StudentProfile profile : profiles) {
            if (profile.getHeight() < min) {
                min = profile.getHeight();
            }
        }
        return min;
    }
}
