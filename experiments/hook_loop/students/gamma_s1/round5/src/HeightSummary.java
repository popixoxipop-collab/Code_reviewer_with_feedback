import java.util.List;

/**
 * 키 통계를 등급(우수/평균/미달)으로 판정해 출력하는 클래스.
 *
 * 통계 계산 자체는 HeightAnalyzer에게 위임하고(계산 로직을 두 곳에서
 * 중복 구현하지 않기 위함), 이 클래스는 등급 판정 기준 적용과 출력만 담당한다.
 * HeightAnalyzer의 계산 방식이 바뀌어도 이 클래스는 calculateAverage() 등
 * public 메서드 시그니처만 신경 쓰면 되고 내부 구현을 몰라도 된다.
 */
public class HeightSummary {

    /**
     * [임계값 근거] 이 값은 실측 표본 데이터로 산출한 값이 아니라 학습용 데모 기준이다.
     * "학급 평균 대비 ±5cm"를 우수/미달 경계로 사용하는 상대 기준이며,
     * 특정 연령대의 실제 성장 표준치 같은 절대 기준이 아니다. 학급이 바뀌면
     * average 자체가 바뀌므로 기준선도 함께 이동한다.
     * 실제 서비스에 쓰려면 이 상수를 감으로 정한 값으로 유지하지 말고,
     * 연령대별 실측 키 분포 데이터로 재산정해야 한다.
     */
    private static final double GRADE_MARGIN_CM = 5.0;

    private final List<StudentProfile> profiles;
    private final HeightAnalyzer heightAnalyzer;

    public HeightSummary(List<StudentProfile> profiles, HeightAnalyzer heightAnalyzer) {
        this.profiles = profiles;
        this.heightAnalyzer = heightAnalyzer;
    }

    public void printSummary() {
        if (profiles.isEmpty()) {
            System.out.println("등록된 학생이 없어 키 통계를 계산할 수 없습니다.");
            return;
        }

        double average = heightAnalyzer.calculateAverage();
        double max = heightAnalyzer.findMax();
        double min = heightAnalyzer.findMin();

        System.out.println("===== 키 통계 요약 =====");
        System.out.printf("평균 키: %.1fcm%n", average);
        System.out.printf("최고 키: %.1fcm%n", max);
        System.out.printf("최저 키: %.1fcm%n", min);
        System.out.println();

        System.out.println("----- 학생별 키 등급 -----");
        for (StudentProfile profile : profiles) {
            String grade = gradeOf(profile.getHeight(), average);
            System.out.printf("%-15s %6.1fcm -> %s%n", profile.getName(), profile.getHeight(), grade);
        }
        System.out.println();
    }

    private String gradeOf(double height, double average) {
        if (height >= average + GRADE_MARGIN_CM) {
            return "우수";
        } else if (height <= average - GRADE_MARGIN_CM) {
            return "미달";
        } else {
            return "평균";
        }
    }
}
