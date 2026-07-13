import java.util.List;

/**
 * 학생 명단을 이름 포맷팅해서 출력하는 클래스.
 *
 * StudentProfile 목록(DTO)만 입력받아 그 public getter만 사용하고,
 * HeightAnalyzer나 HeightSummary의 내부 구현에는 의존하지 않는다.
 * "출력 포맷팅" 책임과 "통계 계산" 책임을 분리해 두어, 출력 형식을
 * 바꾸는 변경이 통계 계산 쪽에 영향을 주지 않도록 한다.
 */
public class ProfileReport {

    private final List<StudentProfile> profiles;

    public ProfileReport(List<StudentProfile> profiles) {
        this.profiles = profiles;
    }

    public void printReport() {
        System.out.println("===== 학생 명단 =====");
        int index = 1;
        for (StudentProfile profile : profiles) {
            System.out.println(index + ". " + formatLine(profile));
            index++;
        }
        System.out.println("총 " + profiles.size() + "명");
        System.out.println();
    }

    private String formatLine(StudentProfile profile) {
        String upperName = profile.getName().toUpperCase();
        String initials = extractInitials(profile.getName());
        String memberTag = profile.isActiveMember() ? "활동" : "휴면";

        return String.format("%-15s (이니셜:%-3s) 키:%6.1fcm 나이:%3d세 [%s]",
                upperName, initials, profile.getHeight(), profile.getAge(), memberTag);
    }

    /**
     * 이름에서 이니셜을 추출한다.
     * - 공백으로 구분된 이름(예: "Kim Younghee")은 각 단어의 첫 글자를 모아 "KY"처럼 만든다.
     * - 공백이 없는 한 단어 이름(예: "김철수")은 첫 글자만 대문자로 반환한다.
     *   한글은 toUpperCase()를 적용해도 원문 그대로 유지되므로 어떤 문자 종류가
     *   와도 안전하게 호출할 수 있다.
     */
    private String extractInitials(String name) {
        if (name == null || name.trim().isEmpty()) {
            return "";
        }
        String[] parts = name.trim().split("\\s+");
        StringBuilder initials = new StringBuilder();
        for (String part : parts) {
            if (!part.isEmpty()) {
                initials.append(Character.toUpperCase(part.charAt(0)));
            }
        }
        return initials.toString();
    }
}
