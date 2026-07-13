import java.util.Objects;

/**
 * 학생 한 명의 신체정보를 담는 모델(DTO) 클래스.
 *
 * [공유 범위 메모] StudentProfile은 ProfileInputHandler(생성 담당)와
 * HeightAnalyzer / ProfileReport / HeightSummary(조회 담당)에서 함께 쓰이는
 * 공유 데이터 구조다 (fan_in >= 4, Main까지 포함하면 더 늘어난다).
 * fan_in이 높은 만큼 이 클래스에는 순수 데이터 보관/조회 책임만 두고,
 * 통계 계산이나 출력 포맷팅 같은 비즈니스 로직은 절대 섞지 않는다.
 * 그런 로직을 여기로 옮기면 여러 클래스가 이 모델의 "내부 구현"에
 * 암묵적으로 의존하게 되어 변경 파급 범위가 커지기 때문이다.
 * 모든 소비 클래스는 반드시 getter로 노출된 값만 사용하고 필드에는
 * 직접 접근하지 않는다 (필드가 private final인 이유).
 */
public class StudentProfile {

    private final String name;
    private final double height; // cm 단위, 소수점 허용 (예: 172.5)
    private final int age;
    private final boolean activeMember;

    public StudentProfile(String name, double height, int age, boolean activeMember) {
        this.name = name;
        this.height = height;
        this.age = age;
        this.activeMember = activeMember;
    }

    public String getName() {
        return name;
    }

    public double getHeight() {
        return height;
    }

    public int getAge() {
        return age;
    }

    public boolean isActiveMember() {
        return activeMember;
    }

    @Override
    public String toString() {
        return "StudentProfile{" +
                "name='" + name + '\'' +
                ", height=" + height +
                ", age=" + age +
                ", activeMember=" + activeMember +
                '}';
    }

    // null-safe 비교: name.equals(that.name) 대신 Objects.equals()를 사용한다.
    // name 필드가 어떤 경로로든 null이 되는 경우에도 NullPointerException 없이
    // false를 반환하도록 하기 위함이다 (한쪽만 null이어도 안전, 둘 다 null이면 true).
    @Override
    public boolean equals(Object o) {
        if (this == o) {
            return true;
        }
        if (!(o instanceof StudentProfile)) {
            return false;
        }
        StudentProfile that = (StudentProfile) o;
        return Double.compare(that.height, height) == 0
                && age == that.age
                && activeMember == that.activeMember
                && Objects.equals(name, that.name);
    }

    @Override
    public int hashCode() {
        return Objects.hash(name, height, age, activeMember);
    }
}
